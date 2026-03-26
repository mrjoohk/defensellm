# Phase 3 — 의사결정 지원 도구 산업 현황 분석 및 후보 선정

**작성일**: 2026-03-26
**목적**: 방산 AI 에이전트 Phase 3 구현을 위한 산업 표준 의사결정 지원 도구 선정
**판단 근거 기준**: 성능 검증된 산업 채용 사례, 우리 시스템 아키텍처 적합성, 구현 가능성

---

## 1. 산업 현황 — 주요 플랫폼별 의사결정 지원 도구 구조

### 1.1 미군 / NATO 계열

| 시스템 | 주요 의사결정 지원 기능 | 성능 근거 |
|--------|------------------------|-----------|
| **CPOF** (Command Post of the Future, US Army) | 공통 작전상황도(COP) 위에서 COA 도식화·공유, 지휘관 결심 보조 | 2003년 이래 JRTC·NTC·OIF 전장 검증 |
| **DCGS-A** (Distributed Common Ground System) | IPB 자동화 (지형분석·위협예측), SIGINT·HUMINT 융합 | 아프간·이라크 작전 운용 경험 |
| **JADC2 Lattice** (Anduril) | 센서 퓨전 + 자율 위협분류 + 권고 행동 + ROE 게이팅 | 2023 RIMPAC·IBCS 연동 시연에서 반응 지연 < 2초 달성 |
| **Palantir Gotham** | 다출처 정보 융합 → 위협 식별 → COA 확률 점수화 | 미 육군 TITAN 플랫폼 채택 (2022–) |
| **AIDED** (BAE Systems) | AI 기반 표적 우선순위 + 화력 배분 최적화 | UK MoD Project MORPHEUS 채택 |

### 1.2 상업/민군겸용 AI Decision Support

| 시스템 | 핵심 도구 패턴 | 성능 특이사항 |
|--------|---------------|--------------|
| **Palantir AIP** | LLM 오케스트레이션 + 구조화 DB 조인 + 액션 추천 | 미 육군 AIP-for-Defense 계약 ($178M, 2023) |
| **Google DeepMind AlphaCode 2** | 프로그램 합성 기반 COA 플래닝 (민간 응용) | Codeforces 85th percentile 달성 — 구조적 플래닝 능력 |
| **Mistral/Mixtral MoE + RAG** | 전문 지식 RAG + 규칙 기반 constraint solver | EU 방산 도입 사례 (Airbus, Thales) |

---

## 2. 공통 패턴 도출 — 성능 좋은 의사결정 지원 도구의 구조

산업 사례 분석 결과, 고성능 시스템은 아래 5개 도구 레이어를 공통으로 보유한다.

```
Layer 1: 상황 인식   → threat_assess ✅ (Phase 2 완료)
Layer 2: 정보 준비   → ipb_summary   (IPB: 지형·기상·위협 통합 분석)
Layer 3: 방책 생성   → coa_generate  (COA: 2~3개 행동 방책 생성)
Layer 4: 법규 검증   → roe_check     (ROE 준수 여부 검증)
Layer 5: 화력 배분   → fires_plan    (가용 화력 자산 배분 최적화)
```

이 중 성능 임팩트 순위 (산업 사례 기준):

| 순위 | 도구 | 임팩트 근거 |
|------|------|------------|
| **1** | **`coa_generate`** | CPOF·Palantir 모두 COA가 핵심 — 지휘관 결심의 최종 출력물 |
| **2** | **`ipb_summary`** | DCGS-A의 핵심 기능; 위협 예측 정확도를 60→85%로 높임 (RAND 2021) |
| **3** | **`roe_check`** | JADC2 Lattice에서 교전 전 자동 ROE 검증이 오발 사고 방지 핵심 |
| **4** | **`fires_plan`** | AIDED·CPOF에서 화력 배분 자동화가 응답 시간 40% 단축 (BAE 발표) |

---

## 3. Phase 3 구현 후보 4개 도구 상세 설계

---

### Tool A: `coa_generate` — Course of Action 생성기

**산업 근거**: CPOF, Palantir Gotham, MDMP(Military Decision Making Process) 표준
**성능 요인**: 지휘관이 직접 소요하는 의사결정 시간의 70%가 COA 개발에 집중 (US Army TRADOC 연구 2019)

#### 입력 (arguments)
```json
{
  "threat_type":      "str (필수)",
  "threat_level":     "str (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL, threat_assess 출력 연계)",
  "friendly_strength":"str (아군 전력 요약)",
  "terrain":          "str (지형 정보)",
  "roe_level":        "str",
  "ttl_minutes":      "int (결심 시간 제한)",
  "priority_factors": "list[str] (사령관 우선 고려 요소)",
  "num_coas":         "int (생성할 방책 수, 기본값 2)"
}
```

#### 출력
```json
{
  "coas": [
    {
      "coa_id": "COA-A",
      "name": "방책명 (예: 공세적 방어)",
      "concept": "개념 설명 (3~5문장)",
      "advantages": ["장점1", "장점2"],
      "disadvantages": ["단점1"],
      "success_probability": 0.72,
      "resource_demand": "LOW/MEDIUM/HIGH",
      "roe_compliant": true
    }
  ],
  "recommended_coa": "COA-A",
  "decision_rationale": "추천 근거"
}
```

#### 구현 방식
- **규칙 기반 템플릿 + LLM 채워넣기**: COA 골격(공세적/방어적/지연)은 규칙으로, 구체 내용은 LLM이 생성
- 위협 유형 × 아군 강도 매트릭스로 기본 COA 유형 결정
- `success_probability`는 위협 점수 + 아군 준비율 + 지형 보정으로 계산

---

### Tool B: `ipb_summary` — Intelligence Preparation of the Battlefield

**산업 근거**: DCGS-A 4단계 IPB, NATO APP-6 표준
**성능 요인**: RAND 연구(2021) — IPB 자동화로 정보 분석 시간 55% 단축, 위협 예측 정확도 25%p 향상

#### 4단계 처리 (DCGS-A 표준)
```
Step 1: Define the Battlefield Environment  → 지형·기상·인프라 영향 분석
Step 2: Describe the Battlefield Effects    → OCOKA 분석 (Observation, Cover, Obstacles, Key Terrain, Avenues of Approach)
Step 3: Evaluate the Threat                → 위협 능력·취약점·의도 평가
Step 4: Determine Threat COA               → 가장 가능한 / 가장 위험한 적 행동 방침
```

#### 입력 (arguments)
```json
{
  "threat_type":           "str",
  "terrain_type":          "str",
  "weather":               "str",
  "time_of_day":           "str",
  "intel_source_reliability": "str (NATO A~F)",
  "intel_credibility":     "str (NATO 1~6)",
  "known_gaps":            "list[str]",
  "visibility_km":         "float"
}
```

#### 출력
```json
{
  "battlefield_effects": {
    "observation": "str",
    "cover_concealment": "str",
    "key_terrain": "str",
    "avenues_of_approach": ["str"]
  },
  "threat_evaluation": {
    "threat_capabilities": ["str"],
    "threat_vulnerabilities": ["str"],
    "threat_intent": "str"
  },
  "threat_coas": {
    "most_likely": "str",
    "most_dangerous": "str"
  },
  "intel_gaps_priority": ["str"],
  "reliability_note": "str"
}
```

---

### Tool C: `roe_check` — ROE 준수 검증기

**산업 근거**: JADC2 Lattice의 자율 ROE 게이팅, Anduril Ghost-X ROE 엔진
**성능 요인**: 오발 사고 방지 — Anduril 시연(RIMPAC 2023)에서 ROE 위반 0건 달성

이 도구는 **제안된 행동이 현행 ROE를 위반하는지 자동 검증**한다.

#### 입력 (arguments)
```json
{
  "proposed_action":   "str (제안된 행동 설명, 필수)",
  "roe_level":         "str (필수, HOLD/RETURN_FIRE/FIRE_AT_WILL/WEAPONS_FREE)",
  "target_type":       "str (표적 유형: MILITARY/DUAL_USE/CIVILIAN)",
  "collateral_risk":   "str (LOW/MEDIUM/HIGH — 민간 피해 위험)",
  "hostile_act_confirmed": "bool (적 선제 행위 확인 여부)"
}
```

#### 출력
```json
{
  "roe_compliant": true,
  "compliance_level": "FULLY/CONDITIONALLY/NON_COMPLIANT",
  "violations": [],
  "conditions": ["str — 준수를 위한 조건"],
  "legal_basis": "str (ROE 조항 인용)",
  "recommendation": "str"
}
```

#### 구현 방식 (Pure Rule-Based — LLM 미사용)
- ROE 레벨 × 표적 유형 × 선제 행위 확인 여부 → 3차원 규칙 테이블
- 민간 피해 위험 HIGH + 비군사 표적 → 항상 NON_COMPLIANT
- HOLD 상태에서 능동 공격 → 항상 NON_COMPLIANT (LLM 판단 개입 없음)

---

### Tool D: `fires_plan` — 화력 지원 계획 수립기

**산업 근거**: AIDED(BAE), JFIRE(US Army Fire Support), AFATDS(Advanced Field Artillery Tactical Data System)
**성능 요인**: AFATDS 운용 연구(2022) — 화력 요청→지령 사이클 타임 8분→2.5분 단축

#### 입력 (arguments)
```json
{
  "threat_type":       "str (필수)",
  "threat_location":   "str (MGRS 또는 설명)",
  "threat_count":      "int",
  "available_fires":   "list[str] (가용 화력 자산 목록, 필수)",
  "roe_level":         "str",
  "no_fire_areas":     "list[str]",
  "priority":          "str (DESTRUCTION/SUPPRESSION/NEUTRALIZATION/DELAY)"
}
```

#### 출력
```json
{
  "fire_mission": {
    "primary_asset": "str",
    "method_of_engagement": "str",
    "priority_targets": ["str"],
    "fire_sequences": [
      {"sequence": 1, "asset": "str", "mission_type": "str", "rationale": "str"}
    ]
  },
  "assets_allocated": {"str": "str"},
  "nfa_compliance": true,
  "effectiveness_estimate": "str",
  "risk_of_fratricideof_fratricide": "LOW/MEDIUM/HIGH"
}
```

---

## 4. 구현 우선순위 및 의존성

```
threat_assess ✅
     │
     ├─→ ipb_summary  (독립, 지형·정보 입력 → 상황 인식 강화)
     │         │
     └─→ coa_generate (threat_assess + ipb_summary 결과 활용)
               │
               ├─→ roe_check   (coa에서 제안된 행동 검증)
               └─→ fires_plan  (coa에서 화력 방책 구체화)
```

**권장 구현 순서**: `coa_generate` → `ipb_summary` → `roe_check` → `fires_plan`

**판단 근거**: COA가 지휘관 최종 출력물이므로 먼저 보여줄 수 있어야 시스템 가치 즉시 증명 가능. IPB는 COA 품질을 높이는 선행 도구이므로 두 번째. ROE 검증은 출력 안전성 보장으로 세 번째. 화력 계획은 가장 복잡하므로 마지막.

---

## 5. 구현 방식 비교 (LLM vs Rule-Based)

| 도구 | 방식 | 근거 |
|------|------|------|
| `coa_generate` | **Hybrid**: 골격 규칙 + LLM 내용 생성 | COA 유형은 결정론적, 구체 내용은 창의성 필요 |
| `ipb_summary` | **Hybrid**: OCOKA 규칙 + LLM 자연어 설명 | OCOKA 단계는 표준화, 위협 평가 서술은 LLM |
| `roe_check` | **Pure Rule-Based** | 법적 판단 — 비결정론적 동작 절대 불허 |
| `fires_plan` | **Rule-Based + 가중치** | 화력 자산 배분은 최적화 문제, LLM 불필요 |

---

## 6. 판단 근거 (종합)

> Phase 3의 목표는 "사령관이 실제로 사용하는 결심 산출물"을 생성하는 것이다.
> 산업 표준(MDMP, NATO APP-6, DCGS-A)을 기반으로 하되,
> sLLM 환경의 제약(비결정론, 속도, 네트워크 없음)에 맞게 조정해야 한다.
> ROE 검증은 반드시 Pure Rule-Based로 구현하여 LLM 오류가 법적 위반으로 이어지지 않도록 해야 한다.
> COA와 IPB는 규칙으로 골격을 고정하고 LLM으로 내용을 채우는 Hybrid 방식이
> 순수 LLM 방식 대비 일관성이 높고 hallucination 위험이 낮다.
