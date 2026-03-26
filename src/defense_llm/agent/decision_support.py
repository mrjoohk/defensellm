"""
decision_support.py — Phase 3: Decision Support Tools

4개 의사결정 지원 핸들러 (executor.py에서 호출):
  coa_generate  — COA(행동 방책) 생성기     [Hybrid: 규칙 골격 + LLM 내용]
  ipb_summary   — 전장 정보 준비(IPB)       [Hybrid: OCOKA 규칙 + LLM 위협 서술]
  roe_check     — ROE 준수 검증기           [Pure Rule-Based — LLM 미사용]
  fires_plan    — 화력 지원 계획 수립기     [Rule-Based + 가중치]

설계 원칙:
  - ROE 검증(roe_check)은 LLM을 전혀 사용하지 않는다 (법적 판단은 비결정론 불가).
  - COA·IPB는 구조(스키마)를 규칙으로 고정하고, 자연어 서술만 LLM에 위임한다.
  - 모든 함수는 순수 함수 또는 llm_adapter를 인자로 받는 함수로 작성한다.
    Executor 인스턴스에 의존하지 않으므로 독립적으로 테스트 가능하다.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# ===========================================================================
# A. coa_generate — Course of Action 생성기
#    산업 근거: CPOF, Palantir Gotham, US Army MDMP
# ===========================================================================

# COA 원형 테이블: threat_level → [(name, resource_demand, advantages, disadvantages)]
# 각 위협 수준에 대해 최소 3개 원형 제공 (num_coas=3 기본값 대응)
_COA_ARCHETYPES: Dict[str, List[tuple]] = {
    "CRITICAL": [
        ("긴급 방어 거점 확보",
         "HIGH",
         ["지형 이점 최대 활용", "집중 화력으로 위협 저지"],
         ["병력 분산 위험", "기동성 제한"]),
        ("지연 전술 + 긴급 증원 요청",
         "MEDIUM",
         ["병력 보존", "시간 획득을 통한 전력 재편"],
         ["지역 일시 포기 필요", "증원 도착 전 취약 구간 발생"]),
        ("측면 기동 반격",
         "HIGH",
         ["주도권 탈환 가능성", "기습 효과로 적 위협 무력화"],
         ["높은 위험도", "상세 정보 요구 수준 높음"]),
    ],
    "HIGH": [
        ("적극 방어 + 화력 집중",
         "HIGH",
         ["적 진격 조기 저지", "아군 진지 유지"],
         ["자산 소모율 증가", "장기전 지속 어려움"]),
        ("기동 방어 + 예비대 운용",
         "MEDIUM",
         ["유연성 확보", "예비 전력 보존"],
         ["일부 지역 노출 허용 필요"]),
        ("화력 차단 + 지연 기동",
         "MEDIUM",
         ["병력 보존 최적화", "화력 효율 극대화"],
         ["시간 소요 많음", "지역 통제력 일시 약화"]),
    ],
    "MEDIUM": [
        ("경계 강화 + 준비 진지 점령",
         "LOW",
         ["선제 대응 준비 완료", "병력 보존"],
         ["수동적 대응으로 주도권 미확보"]),
        ("한정적 공세 행동",
         "MEDIUM",
         ["적 기선 제압", "전장 정보 획득"],
         ["위험 부담 증가", "전력 소모 가능"]),
        ("감시 강화 + 화력 준비",
         "LOW",
         ["최소 위험으로 대응 준비", "전력 보존"],
         ["주도권 미확보", "상황 악화 시 전환 지연"]),
    ],
    "LOW": [
        ("현 진지 유지 + 감시 강화",
         "LOW",
         ["전력 보존", "유연한 대응 옵션 유지"],
         ["소극적 대응으로 상황 변화 대응 지연 우려"]),
        ("경계 순찰 강화 + 정보 수집",
         "LOW",
         ["능동적 정보 획득", "조기 경보 체계 강화"],
         ["소규모 분산 위험 증가"]),
        ("예비대 준비 + 경보 체계 점검",
         "LOW",
         ["신속 반응 준비 태세 완비"],
         ["자원 소모 소량", "직접 전투 효과 없음"]),
    ],
    "MINIMAL": [
        ("감시 유지 + 정상 작전 지속",
         "LOW",
         ["전력 보존", "작전 지속성 유지"],
         ["상황 급변 시 대응 지연 가능성"]),
        ("정기 순찰 강화",
         "LOW",
         ["예방적 경계 강화"],
         ["소량 자원 소모"]),
        ("경보 체계 점검 및 유지",
         "LOW",
         ["대응 준비 태세 확인"],
         ["직접 전투 효과 없음"]),
    ],
}

# 위협 수준별 기본 성공 확률
_LEVEL_BASE_PROB: Dict[str, float] = {
    "CRITICAL": 0.45, "HIGH": 0.58, "MEDIUM": 0.70, "LOW": 0.80, "MINIMAL": 0.88,
}

# 자원 소요 → 성공 확률 보정
_RESOURCE_MOD: Dict[str, float] = {"HIGH": -0.06, "MEDIUM": 0.00, "LOW": 0.06}


def coa_generate(arguments: dict, llm_adapter) -> dict:
    """COA(행동 방책) 생성기.

    Args:
        arguments: tool call 인자 dict
        llm_adapter: AbstractLLMAdapter 인스턴스 (개념 생성에 사용)

    Returns:
        {"coas": [...], "recommended_coa": str, "decision_rationale": str, ...}
    """
    threat_type = str(arguments.get("threat_type", "MIXED")).upper()
    threat_level = str(arguments.get("threat_level", "MEDIUM")).upper()
    roe_level = str(arguments.get("roe_level", "RETURN_FIRE")).upper()
    friendly_strength = str(arguments.get("friendly_strength", ""))
    terrain = str(arguments.get("terrain", ""))
    ttl_minutes: Optional[int] = arguments.get("ttl_minutes")
    priority_factors: List[str] = list(arguments.get("priority_factors", []))
    num_coas = min(max(int(arguments.get("num_coas", 3)), 1), 5)

    archetypes = _COA_ARCHETYPES.get(threat_level, _COA_ARCHETYPES["MEDIUM"])
    # 요청 수만큼 선택 (부족 시 순환 반복)
    selected = [archetypes[i % len(archetypes)] for i in range(num_coas)]

    base_prob = _LEVEL_BASE_PROB.get(threat_level, 0.65)
    roe_prob_bonus = 0.05 if roe_level in ("FIRE_AT_WILL", "WEAPONS_FREE") else 0.0
    coa_letters = "ABCDE"
    coas = []

    for i, (name, resource_demand, advantages, disadvantages) in enumerate(selected):
        resource_mod = _RESOURCE_MOD.get(resource_demand, 0.0)
        prob = round(min(0.95, max(0.20, base_prob + resource_mod + roe_prob_bonus)), 2)

        # ROE compliance: HOLD ROE 에서 공세적 행동은 비준수
        roe_compliant = not (
            roe_level == "HOLD"
            and any(kw in name for kw in ("공세", "반격", "타격", "사격"))
        )

        # LLM 으로 전술 개념 서술 생성 (3문장)
        prompt = [
            {
                "role": "system",
                "content": (
                    "당신은 방산 전술 참모입니다. "
                    "주어진 방책명과 전술 상황에 맞는 개념 설명을 정확히 3문장으로 작성하십시오. "
                    "한국어로만 답하십시오."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"방책: {name}\n"
                    f"위협: {threat_type} ({threat_level})\n"
                    f"아군: {friendly_strength or '정보 없음'}\n"
                    f"지형: {terrain or '정보 없음'}\n"
                    f"ROE: {roe_level}\n"
                    f"우선요소: {', '.join(priority_factors) or '없음'}"
                ),
            },
        ]
        llm_resp = llm_adapter.chat(prompt)
        concept = (llm_resp.get("content") or "").strip()
        if not concept:
            concept = (
                f"{name} 방책은 {threat_type} 위협에 대응하여 "
                f"{advantages[0]}을(를) 달성하는 것을 목표로 한다. "
                f"이 방책은 {resource_demand} 수준의 자원을 요구한다."
            )

        coas.append({
            "coa_id": f"COA-{coa_letters[i]}",
            "name": name,
            "concept": concept,
            "advantages": advantages,
            "disadvantages": disadvantages,
            "success_probability": prob,
            "resource_demand": resource_demand,
            "roe_compliant": roe_compliant,
        })

    # ROE 준수 COA 중 성공 확률 최고를 권고
    compliant = [c for c in coas if c["roe_compliant"]]
    recommended = max(compliant, key=lambda c: c["success_probability"]) if compliant else coas[0]

    rationale = (
        f"위협수준 {threat_level} 상황에서 ROE({roe_level}) 준수 조건 하에 "
        f"성공확률 {recommended['success_probability']:.0%}로 "
        f"'{recommended['name']}'({recommended['coa_id']})를 권고합니다."
    )
    if ttl_minutes is not None:
        rationale += f" 결심 가능 시간: {ttl_minutes}분 이내."
    if priority_factors:
        rationale += f" 우선 고려: {', '.join(priority_factors)}."

    return {
        "coas": coas,
        "recommended_coa": recommended["coa_id"],
        "decision_rationale": rationale,
        "num_coas_generated": len(coas),
    }


# ===========================================================================
# B. ipb_summary — Intelligence Preparation of the Battlefield (IPB)
#    산업 근거: DCGS-A 4단계 IPB, NATO APP-6
#    OCOKA: Observation, Cover&Concealment, Obstacles, Key Terrain, Avenues of Approach
# ===========================================================================

_TERRAIN_OBSERVATION: Dict[str, str] = {
    "URBAN":   "시가지로 관측 거리 500m 이내 제한. 고층 건물이 관측 거점 제공 가능.",
    "MOUNTAIN":"능선·고지대에서 원거리 관측 가능. 계곡·사면 사각지대 다수 존재.",
    "FOREST":  "수목으로 관측 100~300m로 극도 제한. 열상 장비 필수.",
    "OPEN":    "개활지로 장거리 상호 관측 가능. 피아 동시 노출.",
    "COASTAL": "해안선 따라 양방향 관측. 수면 반사로 야간 관측 유리.",
    "DESERT":  "개활지와 유사. 신기루·모래폭풍이 광학 장비 효과 저하.",
    "MIXED":   "지형에 따라 관측 조건 상이. 핵심 지형 확보가 관측 우위 결정.",
}
_WEATHER_OBS_MOD: Dict[str, str] = {
    "CLEAR":  "기상 양호, 광학 장비 최대 효과.",
    "CLOUDY": "항공 자산 효과 일부 감소. 지상 관측 영향 없음.",
    "RAIN":   "가시거리 50% 감소, 소음이 청각 감지 저하.",
    "FOG":    "가시거리 200m 이하. 열상 장비가 유일한 관측 수단.",
    "SNOW":   "가시거리 및 기동 동시 제한. 백색 위장 효과 증가.",
    "STORM":  "모든 관측 자산 효과 극감. 작전 일시 제한.",
}
_TERRAIN_COVER: Dict[str, str] = {
    "URBAN":   "건물·지하 구조물이 우수한 엄폐 제공. 전차 기동로에는 불리.",
    "MOUNTAIN":"암반·능선 역사면이 포병 사계 제한하며 엄폐 제공.",
    "FOREST":  "수목이 관측·직사에 대한 은폐 제공. 간접 화력 효과 감소.",
    "OPEN":    "엄폐·은폐 거의 없음. 분산 기동·연막이 유일한 보호 수단.",
    "COASTAL": "해안 사구·방파제가 제한적 엄폐 제공.",
    "DESERT":  "사구가 이동식 은폐 제공. 고정 엄폐물 부족.",
    "MIXED":   "지형별 차등. 산림·능선 지역 적극 활용 필요.",
}
_KEY_TERRAIN: Dict[str, str] = {
    "ARMOR":    "주요 도로·교량·개활지가 기갑 기동 핵심 지형. 통제 여부가 전투 승패 결정.",
    "INFANTRY": "고지대·건물·숲이 보병 핵심 지형. 저격·매복 거점으로 활용.",
    "AIR":      "레이더 사각지대·저고도 접근로 핵심. 방공 배치 지형이 결정적.",
    "MISSILE":  "은폐된 평지·능선 역사면이 발사 거점 후보.",
    "NAVAL":    "항구·해안 돌출부·좁은 수로가 핵심 지형.",
    "DRONE":    "전파 중계 가능 고지대, 충전·재보급 가능 은폐 지점.",
    "CYBER":    "통신 중계소·지휘소 위치가 핵심 지형.",
    "MIXED":    "각 위협 유형별 핵심 지형 복합 분석 필요.",
}
_AVENUES: Dict[str, List[str]] = {
    "URBAN":   ["주요 간선도로", "지하 통로·하수도", "건물 루프탑 접근로"],
    "MOUNTAIN":["계곡 진입로", "능선 횡단로", "하천 유역 기동로"],
    "FOREST":  ["임도·벌목로", "하천 유역", "수림 차단선 돌파구"],
    "OPEN":    ["전방 직선 기동축", "우회 기동로 다수", "광정면 차량 기동 가능"],
    "COASTAL": ["해안 도로", "상륙 가능 해안선", "항만 접근로"],
    "DESERT":  ["오아시스 연결로", "주요 도로", "모래길"],
    "MIXED":   ["지형별 주 기동로 복합 분석 필요"],
}
_THREAT_CAPABILITIES: Dict[str, List[str]] = {
    "ARMOR":    ["장거리 직사 화력", "돌파 기동", "공병 지뢰 제거 능력"],
    "INFANTRY": ["은폐 침투", "근접 전투", "시가전 특화"],
    "AIR":      ["장거리 정밀 타격", "전장 종심 공격", "저고도 침투"],
    "MISSILE":  ["장거리 정밀 타격", "다수 동시 발사"],
    "NAVAL":    ["해상 화력 지원", "상륙 기동"],
    "DRONE":    ["정찰·감시", "자폭 공격", "전자 방해"],
    "CYBER":    ["통신 마비", "지휘망 교란"],
    "MIXED":    ["복합 다차원 위협"],
}
_THREAT_VULNERABILITIES: Dict[str, List[str]] = {
    "ARMOR":    ["AT 미사일에 취약", "도심·산림 기동 제한", "공중 화력 취약"],
    "INFANTRY": ["화력 지원 없으면 취약", "야간 열상 장비에 노출"],
    "AIR":      ["방공망에 취약", "기상 제한", "재보급 필요"],
    "MISSILE":  ["발사 진지 노출 위험", "이동식 표적 추적 필요"],
    "NAVAL":    ["상륙 지점 제한", "해안 방어에 취약"],
    "DRONE":    ["전자 방해(EW)에 취약", "짧은 체공 시간"],
    "CYBER":    ["물리 공격에 무방비", "네트워크 차단 시 효과 없음"],
    "MIXED":    ["복합 취약점 — 개별 위협 유형 분석 필요"],
}
_NATO_REL: Dict[str, str] = {
    "A": "완전 신뢰", "B": "통상 신뢰", "C": "불특정 신뢰",
    "D": "통상 불신", "E": "신뢰 불가", "F": "출처 불명",
}
_NATO_CRED: Dict[str, str] = {
    "1": "확인됨", "2": "아마도 사실", "3": "가능한 사실",
    "4": "의심스러움", "5": "불가능", "6": "진위 불명",
}


def ipb_summary(arguments: dict, llm_adapter) -> dict:
    """전장 정보 준비(IPB) — OCOKA 분석 포함.

    Step 1+2: 전장 환경 정의 + OCOKA 효과 (Rule-Based)
    Step 3:   위협 능력·취약점 (Rule-Based) + 위협 의도 (LLM)
    Step 4:   가장 가능한/위험한 적 행동방침 (LLM)
    """
    threat_type = str(arguments.get("threat_type", "MIXED")).upper()
    terrain_type = str(arguments.get("terrain_type", "OPEN")).upper()
    weather = str(arguments.get("weather", "CLEAR")).upper()
    time_of_day = str(arguments.get("time_of_day", "DAY")).upper()
    visibility_km = float(arguments.get("visibility_km", 5.0))
    source_rel = str(arguments.get("intel_source_reliability", "C"))
    credibility = str(arguments.get("intel_credibility", "3"))
    known_gaps: List[str] = list(arguments.get("known_gaps", []))

    # ── OCOKA Step 1/2 ────────────────────────────────────────────────────

    # Observation
    obs_terrain = _TERRAIN_OBSERVATION.get(terrain_type, "지형별 관측 조건 확인 필요.")
    obs_weather = _WEATHER_OBS_MOD.get(weather, "기상 영향 보통.")
    obs_time = (
        "야간 — 열상·NVG 필수. 적 야간 기동도 동일하게 제한됨."
        if time_of_day in ("NIGHT", "DUSK")
        else "주간 — 광학 장비 최적 효과."
    )
    vis_note = f"현재 가시거리 {visibility_km}km 기준."
    observation = f"{obs_terrain} {obs_weather} {obs_time} {vis_note}"

    # Cover & Concealment
    cover_concealment = _TERRAIN_COVER.get(terrain_type, "지형별 차등 엄폐 조건.")

    # Obstacles (terrain-derived rule)
    _TERRAIN_OBSTACLES: Dict[str, str] = {
        "URBAN":   "건물 잔해·방벽·좁은 골목이 기동 장애물. 공병 개척 필요.",
        "MOUNTAIN":"급사면·암반·계곡이 기동 제한. 주 기동로 통제 용이.",
        "FOREST":  "수목 밀집 구역이 차량 기동 제한. 보병 침투는 용이.",
        "OPEN":    "자연 장애물 최소. 인공 장애물(지뢰·철조망) 효과 극대화.",
        "COASTAL": "해안 방어 시설·조류·수심이 상륙 장애물.",
        "DESERT":  "모래 언덕·협곡이 차량 기동 제한 구역.",
        "MIXED":   "지형별 차등 장애물 분포. 현장 공병 정찰 필요.",
    }
    obstacles = _TERRAIN_OBSTACLES.get(terrain_type, "장애물 분석 필요.")

    key_terrain = _KEY_TERRAIN.get(threat_type, "위협 유형에 따른 핵심 지형 분석 필요.")
    avenues = _AVENUES.get(terrain_type, ["주 접근로 분석 필요"])

    # ── OCOKA 결합 ─────────────────────────────────────────────────────────
    ocoka = {
        "observation": observation,
        "cover_concealment": cover_concealment,
        "obstacles": obstacles,
        "key_terrain": key_terrain,
        "avenues_of_approach": avenues,
    }

    # ── Step 3: Threat Evaluation ──────────────────────────────────────────
    threat_caps = _THREAT_CAPABILITIES.get(threat_type, ["위협 능력 분석 필요"])
    threat_vulns = _THREAT_VULNERABILITIES.get(threat_type, ["취약점 분석 필요"])

    # LLM: 위협 의도 + 행동방침 서술
    ipb_prompt = [
        {
            "role": "system",
            "content": (
                "당신은 전술 정보 참모입니다. "
                "주어진 전투 상황에서 적의 의도를 1문장으로 분석하고, "
                "가장 가능한 적 행동방침(MLCOA)과 가장 위험한 적 행동방침(MDCOA)을 "
                "각각 1~2문장으로 서술하십시오. 한국어로만 답하십시오."
            ),
        },
        {
            "role": "user",
            "content": (
                f"위협: {threat_type} / 지형: {terrain_type} / 기상: {weather} / "
                f"시간대: {time_of_day} / 정보신뢰도: {source_rel}/{credibility}\n"
                f"정보공백: {', '.join(known_gaps) or '없음'}"
            ),
        },
    ]
    llm_resp = llm_adapter.chat(ipb_prompt)
    llm_text = (llm_resp.get("content") or "").strip()

    if llm_text and len(llm_text) > 15:
        # 간단한 파싱: LLM 응답 전체를 의도로, 앞부분을 MLCOA, 뒷부분을 MDCOA로
        lines = [l.strip() for l in llm_text.split("\n") if l.strip()]
        threat_intent = lines[0] if lines else llm_text[:120]
        most_likely = lines[1] if len(lines) > 1 else f"{threat_type}의 주 접근로를 이용한 정면 공격"
        most_dangerous = lines[2] if len(lines) > 2 else f"{threat_type}의 측면 우회 기동 후 후방 타격"
    else:
        threat_intent = f"{threat_type} 위협의 주 의도는 아군 방어선 돌파 및 핵심 지형 탈취로 판단됨."
        most_likely = f"현 접근로를 이용한 {threat_type}의 정면 압박"
        most_dangerous = f"{threat_type}의 측면 우회 기동 후 아군 후방 타격"

    # ── 정보 신뢰도 주석 ───────────────────────────────────────────────────
    rel_label = _NATO_REL.get(source_rel, "미지정")
    cred_label = _NATO_CRED.get(credibility, "미지정")
    reliability_note = (
        f"정보 신뢰도 [{source_rel}/{credibility}]: 출처={rel_label}, 내용={cred_label}. "
        + ("정보 신뢰도 낮음 — 판단 결과 상향 대비 필요." if source_rel in ("D", "E", "F") or credibility in ("4", "5", "6") else "판단 결과 신뢰 가능.")
    )

    gaps_priority = known_gaps[:5] if known_gaps else ["정보 공백 없음 또는 미입력"]

    return {
        "battlefield_effects": ocoka,
        "threat_evaluation": {
            "threat_capabilities": threat_caps,
            "threat_vulnerabilities": threat_vulns,
            "threat_intent": threat_intent,
        },
        "threat_coas": {
            "most_likely_coa": most_likely,
            "most_dangerous_coa": most_dangerous,
        },
        "intel_gaps_priority": gaps_priority,
        "reliability_note": reliability_note,
    }


# ===========================================================================
# C. roe_check — ROE 준수 검증기
#    산업 근거: Anduril JADC2 Lattice ROE 게이팅 엔진
#    설계: Pure Rule-Based — LLM 미사용 (법적 판단에 비결정론 불가)
# ===========================================================================

# 공격 의미 키워드 (한국어 + 영어)
_OFFENSIVE_KEYWORDS = frozenset([
    "공격", "사격", "타격", "포격", "발사", "폭격", "strike", "fire",
    "attack", "shoot", "engage", "bomb",
])

_ROE_LEGAL_BASIS: Dict[str, str] = {
    "HOLD":         "ROE HOLD: 교전 금지. 자위를 위한 최소한의 물리력 행사만 허용.",
    "RETURN_FIRE":  "ROE RETURN_FIRE: 적 선제 행위에 대한 반격만 허용. 민간인 표적 금지.",
    "FIRE_AT_WILL": "ROE FIRE_AT_WILL: 적 식별 후 즉시 교전 가능. 민간인·NFA 제외.",
    "WEAPONS_FREE": "ROE WEAPONS_FREE: 무제한 화력 사용. 민간인 표적 절대 금지.",
}


def roe_check(arguments: dict) -> dict:
    """ROE 준수 검증기 — Pure Rule-Based.

    3차원 규칙 테이블 (ROE level × target_type × hostile_act_confirmed)
    에 collateral_risk 보정을 적용하여 compliance_level을 결정한다.
    """
    proposed_action = str(arguments.get("proposed_action", ""))
    roe_level = str(arguments.get("roe_level", "RETURN_FIRE")).upper()
    target_type = str(arguments.get("target_type", "MILITARY")).upper()
    collateral_risk = str(arguments.get("collateral_risk", "LOW")).upper()
    hostile_act_confirmed = bool(arguments.get("hostile_act_confirmed", False))

    violations: List[str] = []
    conditions: List[str] = []
    action_lower = proposed_action.lower()
    is_offensive = any(kw in action_lower for kw in _OFFENSIVE_KEYWORDS)

    # ── Rule Table ─────────────────────────────────────────────────────────

    if roe_level == "HOLD":
        if is_offensive:
            violations.append("ROE HOLD: 능동적 공격·사격 행동 불가.")
        conditions.append("회피·방어 기동만 허용. 자위 최소 물리력만 가능.")

    elif roe_level == "RETURN_FIRE":
        if is_offensive and not hostile_act_confirmed:
            violations.append("선제 행위 미확인 상태에서 반격 조건 미충족.")
            conditions.append("적 선제 공격 확인 후 반격 가능.")
        if target_type == "CIVILIAN":
            violations.append("민간인 표적 — 모든 ROE에서 금지.")
        if collateral_risk == "HIGH" and target_type in ("DUAL_USE", "CIVILIAN"):
            violations.append("고위험 민간 피해 구역 — 화력 운용 전 법무 검토 필요.")
            conditions.append("민간 피해 최소화 조치(비례성 원칙) 적용 필요.")

    elif roe_level == "FIRE_AT_WILL":
        if target_type == "CIVILIAN":
            violations.append("민간인 표적 — 모든 ROE에서 금지.")
        if collateral_risk == "HIGH":
            conditions.append("민간 피해 최소화 조치 적용 — 비례성 원칙 준수.")
        if collateral_risk == "HIGH" and target_type == "DUAL_USE":
            conditions.append("군사·민간 겸용 시설 타격 전 상급부대 승인 요망.")

    elif roe_level == "WEAPONS_FREE":
        if target_type == "CIVILIAN":
            violations.append("민간인 표적 — ROE WEAPONS_FREE에서도 절대 금지.")
        if collateral_risk == "HIGH":
            conditions.append("민간 피해 최소화 원칙은 WEAPONS_FREE에서도 적용됨.")

    else:
        violations.append(f"ROE '{roe_level}' 미정의 — 상급부대 확인 후 행동.")

    # ── Compliance Level ────────────────────────────────────────────────────
    if violations:
        compliance_level = "NON_COMPLIANT"
    elif conditions:
        compliance_level = "CONDITIONALLY"
    else:
        compliance_level = "FULLY"

    roe_compliant = compliance_level == "FULLY"
    legal_basis = _ROE_LEGAL_BASIS.get(roe_level, f"ROE '{roe_level}': 법적 근거 미정의.")

    action_excerpt = (proposed_action[:60] + "…") if len(proposed_action) > 60 else proposed_action
    if violations:
        verdict = f"[{compliance_level}] '{action_excerpt}' — 위반: {'; '.join(violations)}"
    elif conditions:
        verdict = f"[{compliance_level}] '{action_excerpt}' — 조건부 허용: {'; '.join(conditions)}"
    else:
        verdict = f"[{compliance_level}] '{action_excerpt}' — ROE 완전 준수 확인됨."

    return {
        "roe_compliant": roe_compliant,
        "compliance_level": compliance_level,
        "violations": violations,
        "conditions": conditions,
        "legal_basis": legal_basis,
        "recommendation": verdict,
    }


# ===========================================================================
# D. fires_plan — 화력 지원 계획 수립기
#    산업 근거: BAE AIDED, US Army AFATDS, JFIRE
#    설계: Rule-Based + 효과도 가중치 (LLM 미사용)
# ===========================================================================

# 화력 자산 × 위협 유형 효과도 (0.0~1.0)
_ASSET_EFFECTIVENESS: Dict[str, Dict[str, float]] = {
    "155mm":  {"ARMOR": 0.85, "INFANTRY": 0.75, "AIR": 0.10, "MISSILE": 0.55, "DRONE": 0.20, "NAVAL": 0.40, "CYBER": 0.00, "MIXED": 0.65},
    "MLRS":   {"ARMOR": 0.90, "INFANTRY": 0.70, "AIR": 0.15, "MISSILE": 0.65, "DRONE": 0.25, "NAVAL": 0.50, "CYBER": 0.00, "MIXED": 0.72},
    "AT":     {"ARMOR": 0.95, "INFANTRY": 0.40, "AIR": 0.05, "MISSILE": 0.30, "DRONE": 0.15, "NAVAL": 0.10, "CYBER": 0.00, "MIXED": 0.60},
    "CAS":    {"ARMOR": 0.88, "INFANTRY": 0.80, "AIR": 0.35, "MISSILE": 0.60, "DRONE": 0.45, "NAVAL": 0.75, "CYBER": 0.00, "MIXED": 0.75},
    "MORTAR": {"ARMOR": 0.35, "INFANTRY": 0.80, "AIR": 0.05, "MISSILE": 0.20, "DRONE": 0.30, "NAVAL": 0.15, "CYBER": 0.00, "MIXED": 0.50},
}

_PRIORITY_MISSION: Dict[str, str] = {
    "DESTRUCTION":    "파괴 사격",
    "SUPPRESSION":    "제압 사격",
    "NEUTRALIZATION": "무력화 사격",
    "DELAY":          "지연 사격",
}

_ROE_FRATRICIDE: Dict[str, str] = {
    "HOLD":         "N/A",
    "RETURN_FIRE":  "LOW",
    "FIRE_AT_WILL": "MEDIUM",
    "WEAPONS_FREE": "HIGH",
}


def _asset_to_key(asset_name: str) -> str:
    """화력 자산 이름을 효과도 테이블 키로 매핑."""
    a = asset_name.upper()
    if "155" in a or "SPH" in a or "HOWITZER" in a or "자주포" in a:
        return "155mm"
    if "MLRS" in a or "ROCKET" in a or "로켓" in a:
        return "MLRS"
    if ("AT " in a or a.startswith("AT") or "MISSILE" in a
            or "TOW" in a or "JAVELIN" in a or "현무" in a or "미사일" in a):
        return "AT"
    if "CAS" in a or "AIR SUPPORT" in a or "항공" in a or "F-" in a or "A-" in a:
        return "CAS"
    if "MORTAR" in a or "박격" in a:
        return "MORTAR"
    return "155mm"  # 기본값


def fires_plan(arguments: dict) -> dict:
    """화력 지원 계획 수립기 — Rule-Based + 효과도 가중치."""
    threat_type = str(arguments.get("threat_type", "MIXED")).upper()
    threat_location = str(arguments.get("threat_location", "미지정"))
    threat_count = max(1, int(arguments.get("threat_count", 1)))
    available_fires: List[str] = list(arguments.get("available_fires", []))
    roe_level = str(arguments.get("roe_level", "RETURN_FIRE")).upper()
    no_fire_areas: List[str] = list(arguments.get("no_fire_areas", []))
    priority = str(arguments.get("priority", "SUPPRESSION")).upper()

    if not available_fires:
        return {
            "error": "가용 화력 자산이 없습니다. available_fires를 제공하십시오.",
            "fire_mission": None,
        }

    if roe_level == "HOLD":
        return {
            "fire_mission": None,
            "assets_allocated": {},
            "nfa_compliance": True,
            "effectiveness_estimate": "교전 불가 — ROE HOLD 상태",
            "risk_of_fratricide": "N/A",
            "note": "ROE HOLD: 화력 운용 불가. 방어 태세 유지.",
        }

    # 자산 효과도 점수화 및 정렬
    scored: List[tuple] = []
    for asset in available_fires:
        key = _asset_to_key(asset)
        eff = _ASSET_EFFECTIVENESS.get(key, {}).get(threat_type, 0.50)
        scored.append((asset, key, eff))
    scored.sort(key=lambda x: x[2], reverse=True)

    mission_type = _PRIORITY_MISSION.get(priority, "제압 사격")

    # 순차 사격 임무 배분 (상위 3개 자산)
    sequences = []
    assets_allocated: Dict[str, str] = {}
    for seq_i, (asset, key, eff) in enumerate(scored[:3], 1):
        seq_mission = mission_type if seq_i == 1 else f"지속 {mission_type}"
        sequences.append({
            "sequence": seq_i,
            "asset": asset,
            "mission_type": seq_mission,
            "effectiveness_vs_threat": f"{eff:.0%}",
            "rationale": f"대{threat_type} 효과도 {eff:.0%} — {'최우선' if seq_i == 1 else '후속'} 임무",
        })
        assets_allocated[asset] = seq_mission

    primary_asset = scored[0][0]
    top_eff = scored[0][2]

    if top_eff >= 0.80:
        eff_estimate = f"높음 (주력 자산 '{primary_asset}' 대{threat_type} 효과도 {top_eff:.0%})"
    elif top_eff >= 0.60:
        eff_estimate = f"보통 ('{primary_asset}' 효과도 {top_eff:.0%} — 충분하나 최적 아님)"
    else:
        eff_estimate = f"낮음 (효과도 {top_eff:.0%} — 추가 화력 지원 요청 권고)"

    # 아군 오사 위험
    fratricide = _ROE_FRATRICIDE.get(roe_level, "MEDIUM")
    if threat_count <= 3:
        fratricide = "LOW"  # 소규모 표적은 오사 위험 낮음

    result: Dict[str, Any] = {
        "fire_mission": {
            "primary_asset": primary_asset,
            "method_of_engagement": mission_type,
            "priority_targets": [f"{threat_type} 주력 ({threat_count}개) @ {threat_location}"],
            "fire_sequences": sequences,
        },
        "assets_allocated": assets_allocated,
        "nfa_compliance": True,
        "effectiveness_estimate": eff_estimate,
        "risk_of_fratricide": fratricide,
    }
    if no_fire_areas:
        result["nfa_note"] = (
            f"사격금지구역 {len(no_fire_areas)}개 확인 요망: {', '.join(no_fire_areas)}. "
            "각 사격 임무 전 NFA 좌표 검증 필수."
        )
    return result
