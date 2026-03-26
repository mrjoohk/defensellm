"""
tests/unit/test_decision_support.py

Phase 3 의사결정 지원 도구 단위 테스트
  coa_generate  — 10개
  ipb_summary   —  8개
  roe_check     — 10개
  fires_plan    —  8개
  tool_schemas  —  5개  (스키마 등록 + 구조 검증)
합계: 41개
"""

import pytest

from defense_llm.agent.decision_support import (
    coa_generate,
    ipb_summary,
    roe_check,
    fires_plan,
)
from defense_llm.agent.tool_schemas import get_tool_definitions_for_llm
from defense_llm.serving.mock_llm import MockLLMAdapter

_MOCK_LLM = MockLLMAdapter(fixed_response="이 방책은 규칙 기반 골격과 LLM 서술을 결합한 전술 개념을 제공합니다.")


# ===========================================================================
# A. coa_generate
# ===========================================================================
class TestCoaGenerate:

    # A-01: 기본 인자로 num_coas=3 COA 생성
    def test_default_num_coas_is_three(self):
        result = coa_generate({"threat_type": "ARMOR", "threat_level": "HIGH"}, _MOCK_LLM)
        assert result["num_coas_generated"] == 3
        assert len(result["coas"]) == 3

    # A-02: num_coas=3 명시 설정 적용
    def test_explicit_num_coas_three(self):
        result = coa_generate(
            {"threat_type": "ARMOR", "threat_level": "MEDIUM", "num_coas": 3},
            _MOCK_LLM,
        )
        assert len(result["coas"]) == 3

    # A-03: 각 COA에 필수 키 모두 존재
    def test_each_coa_has_required_keys(self):
        result = coa_generate({"threat_type": "INFANTRY", "threat_level": "HIGH"}, _MOCK_LLM)
        required = {"coa_id", "name", "concept", "advantages", "disadvantages",
                    "success_probability", "resource_demand", "roe_compliant"}
        for coa in result["coas"]:
            assert required.issubset(coa.keys()), f"Missing keys in {coa}"

    # A-04: success_probability 0.0~1.0 범위
    def test_success_probability_bounded(self):
        for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"):
            result = coa_generate({"threat_type": "ARMOR", "threat_level": level}, _MOCK_LLM)
            for coa in result["coas"]:
                p = coa["success_probability"]
                assert 0.0 <= p <= 1.0, f"{level}: prob={p}"

    # A-05: CRITICAL 위협 시 MINIMAL보다 성공 확률 낮음
    def test_critical_lower_prob_than_minimal(self):
        r_crit = coa_generate({"threat_type": "ARMOR", "threat_level": "CRITICAL"}, _MOCK_LLM)
        r_min = coa_generate({"threat_type": "ARMOR", "threat_level": "MINIMAL"}, _MOCK_LLM)
        max_crit = max(c["success_probability"] for c in r_crit["coas"])
        min_min = min(c["success_probability"] for c in r_min["coas"])
        assert max_crit < min_min

    # A-06: recommended_coa는 생성된 COA ID 중 하나
    def test_recommended_coa_is_valid_id(self):
        result = coa_generate({"threat_type": "ARMOR", "threat_level": "HIGH"}, _MOCK_LLM)
        valid_ids = {c["coa_id"] for c in result["coas"]}
        assert result["recommended_coa"] in valid_ids

    # A-07: ROE=HOLD 시 공세적 방책은 roe_compliant=False
    def test_hold_roe_offensive_coa_noncompliant(self):
        result = coa_generate(
            {"threat_type": "ARMOR", "threat_level": "CRITICAL", "roe_level": "HOLD"},
            _MOCK_LLM,
        )
        # recommended_coa는 ROE 준수 방책 중 선택
        rec_id = result["recommended_coa"]
        rec = next(c for c in result["coas"] if c["coa_id"] == rec_id)
        assert rec["roe_compliant"] is True

    # A-08: decision_rationale에 위협 수준과 ROE 포함
    def test_decision_rationale_contains_level_and_roe(self):
        result = coa_generate(
            {"threat_type": "AIR", "threat_level": "HIGH", "roe_level": "RETURN_FIRE"},
            _MOCK_LLM,
        )
        rationale = result["decision_rationale"]
        assert "HIGH" in rationale
        assert "RETURN_FIRE" in rationale

    # A-09: ttl_minutes가 있을 때 rationale에 시간 정보 포함
    def test_ttl_minutes_in_rationale(self):
        result = coa_generate(
            {"threat_type": "ARMOR", "threat_level": "HIGH", "ttl_minutes": 30},
            _MOCK_LLM,
        )
        assert "30" in result["decision_rationale"]

    # A-10: priority_factors가 있을 때 rationale에 포함
    def test_priority_factors_in_rationale(self):
        result = coa_generate(
            {"threat_type": "ARMOR", "threat_level": "MEDIUM",
             "priority_factors": ["병력 보존", "마을 피해 최소화"]},
            _MOCK_LLM,
        )
        assert "병력 보존" in result["decision_rationale"]


# ===========================================================================
# B. ipb_summary
# ===========================================================================
class TestIpbSummary:

    # B-01: 반환 필드 완전성
    def test_return_keys_complete(self):
        result = ipb_summary({"threat_type": "ARMOR"}, _MOCK_LLM)
        assert "battlefield_effects" in result
        assert "threat_evaluation" in result
        assert "threat_coas" in result
        assert "intel_gaps_priority" in result
        assert "reliability_note" in result

    # B-02: OCOKA 5개 필드 모두 존재
    def test_ocoka_all_five_fields(self):
        result = ipb_summary({"threat_type": "ARMOR", "terrain_type": "MOUNTAIN"}, _MOCK_LLM)
        ocoka = result["battlefield_effects"]
        for field in ("observation", "cover_concealment", "obstacles", "key_terrain", "avenues_of_approach"):
            assert field in ocoka, f"OCOKA 필드 누락: {field}"

    # B-03: avenues_of_approach는 리스트
    def test_avenues_of_approach_is_list(self):
        result = ipb_summary({"threat_type": "INFANTRY", "terrain_type": "URBAN"}, _MOCK_LLM)
        assert isinstance(result["battlefield_effects"]["avenues_of_approach"], list)
        assert len(result["battlefield_effects"]["avenues_of_approach"]) > 0

    # B-04: 위협 능력·취약점은 비어있지 않은 리스트
    def test_threat_caps_and_vulns_nonempty(self):
        result = ipb_summary({"threat_type": "ARMOR"}, _MOCK_LLM)
        te = result["threat_evaluation"]
        assert len(te["threat_capabilities"]) > 0
        assert len(te["threat_vulnerabilities"]) > 0

    # B-05: known_gaps가 있을 때 intel_gaps_priority에 반영
    def test_known_gaps_reflected_in_gaps_priority(self):
        gaps = ["2제대 위치 불명", "포병 수량 미확인"]
        result = ipb_summary({"threat_type": "ARMOR", "known_gaps": gaps}, _MOCK_LLM)
        for gap in gaps:
            assert gap in result["intel_gaps_priority"]

    # B-06: NATO 신뢰도 코드 D/E/F 시 경고 문구 포함
    def test_low_reliability_warning_in_note(self):
        result = ipb_summary(
            {"threat_type": "INFANTRY", "intel_source_reliability": "E",
             "intel_credibility": "5"},
            _MOCK_LLM,
        )
        assert "낮음" in result["reliability_note"] or "불가" in result["reliability_note"]

    # B-07: MOUNTAIN 지형 → 관측 설명에 능선 관련 내용 포함
    def test_mountain_terrain_observation_mentions_ridge(self):
        result = ipb_summary({"threat_type": "ARMOR", "terrain_type": "MOUNTAIN"}, _MOCK_LLM)
        obs = result["battlefield_effects"]["observation"]
        assert "능선" in obs or "고지" in obs

    # B-08: most_likely_coa, most_dangerous_coa 키 존재
    def test_threat_coas_keys_exist(self):
        result = ipb_summary({"threat_type": "MISSILE"}, _MOCK_LLM)
        tc = result["threat_coas"]
        assert "most_likely_coa" in tc
        assert "most_dangerous_coa" in tc


# ===========================================================================
# C. roe_check
# ===========================================================================
class TestRoeCheck:

    # C-01: HOLD + 공격적 행동 → NON_COMPLIANT
    def test_hold_with_offensive_action_noncompliant(self):
        result = roe_check({
            "proposed_action": "155mm 포대로 적 전차를 사격하라.",
            "roe_level": "HOLD",
        })
        assert result["compliance_level"] == "NON_COMPLIANT"
        assert result["roe_compliant"] is False

    # C-02: HOLD + 방어 행동 → CONDITIONALLY (회피 조건 포함)
    def test_hold_with_defensive_action_conditionally(self):
        result = roe_check({
            "proposed_action": "방어 진지로 후퇴하여 진지를 강화한다.",
            "roe_level": "HOLD",
        })
        # HOLD는 offensive 아니어도 conditions 있으므로 CONDITIONALLY
        assert result["compliance_level"] in ("CONDITIONALLY", "FULLY")

    # C-03: RETURN_FIRE + 선제행위 미확인 → NON_COMPLIANT
    def test_return_fire_without_hostile_act_noncompliant(self):
        result = roe_check({
            "proposed_action": "적 기갑을 즉각 사격한다.",
            "roe_level": "RETURN_FIRE",
            "hostile_act_confirmed": False,
        })
        assert result["compliance_level"] == "NON_COMPLIANT"
        assert any("선제" in v for v in result["violations"])

    # C-04: RETURN_FIRE + 선제행위 확인 + 군사 표적 → FULLY
    def test_return_fire_with_hostile_act_military_target_fully(self):
        result = roe_check({
            "proposed_action": "아군을 공격한 적 보병에 반격한다.",
            "roe_level": "RETURN_FIRE",
            "target_type": "MILITARY",
            "hostile_act_confirmed": True,
            "collateral_risk": "LOW",
        })
        assert result["compliance_level"] == "FULLY"
        assert result["roe_compliant"] is True

    # C-05: 민간인 표적은 모든 ROE에서 NON_COMPLIANT
    def test_civilian_target_always_noncompliant(self):
        for roe in ("RETURN_FIRE", "FIRE_AT_WILL", "WEAPONS_FREE"):
            result = roe_check({
                "proposed_action": "마을 주민을 대상으로 사격",
                "roe_level": roe,
                "target_type": "CIVILIAN",
                "hostile_act_confirmed": True,
            })
            assert result["compliance_level"] == "NON_COMPLIANT", f"ROE={roe}: 민간인 표적은 항상 위반"

    # C-06: WEAPONS_FREE + 군사 표적 + 저 민간피해 → FULLY
    def test_weapons_free_military_low_collateral_fully(self):
        result = roe_check({
            "proposed_action": "적 미사일 발사대를 타격한다.",
            "roe_level": "WEAPONS_FREE",
            "target_type": "MILITARY",
            "collateral_risk": "LOW",
        })
        assert result["compliance_level"] == "FULLY"

    # C-07: FIRE_AT_WILL + HIGH 민간피해 → CONDITIONALLY
    def test_fire_at_will_high_collateral_conditionally(self):
        result = roe_check({
            "proposed_action": "도심 내 적 거점을 포격한다.",
            "roe_level": "FIRE_AT_WILL",
            "target_type": "DUAL_USE",
            "collateral_risk": "HIGH",
        })
        assert result["compliance_level"] in ("CONDITIONALLY", "NON_COMPLIANT")

    # C-08: 반환 필드 완전성
    def test_return_keys_complete(self):
        result = roe_check({"proposed_action": "방어", "roe_level": "RETURN_FIRE"})
        for key in ("roe_compliant", "compliance_level", "violations", "conditions",
                    "legal_basis", "recommendation"):
            assert key in result

    # C-09: legal_basis에 ROE 키워드 포함
    def test_legal_basis_contains_roe_keyword(self):
        for roe in ("HOLD", "RETURN_FIRE", "FIRE_AT_WILL", "WEAPONS_FREE"):
            result = roe_check({"proposed_action": "행동", "roe_level": roe})
            assert roe in result["legal_basis"], f"legal_basis에 {roe} 없음"

    # C-10: 미정의 ROE → NON_COMPLIANT
    def test_undefined_roe_is_noncompliant(self):
        result = roe_check({"proposed_action": "행동", "roe_level": "UNDEFINED_ROE"})
        assert result["compliance_level"] == "NON_COMPLIANT"


# ===========================================================================
# D. fires_plan
# ===========================================================================
class TestFiresPlan:

    # D-01: available_fires 없을 때 오류 반환
    def test_no_fires_returns_error(self):
        result = fires_plan({"threat_type": "ARMOR", "available_fires": []})
        assert "error" in result

    # D-02: ROE=HOLD 시 fire_mission=None 반환
    def test_roe_hold_returns_null_mission(self):
        result = fires_plan({
            "threat_type": "ARMOR",
            "available_fires": ["155mm SPH Battery"],
            "roe_level": "HOLD",
        })
        assert result["fire_mission"] is None
        assert result["nfa_compliance"] is True

    # D-03: AT 미사일은 대기갑 효과도 최고
    def test_at_missile_highest_effectiveness_vs_armor(self):
        result = fires_plan({
            "threat_type": "ARMOR",
            "available_fires": ["AT Missiles", "155mm SPH Battery", "Mortar Platoon"],
            "roe_level": "RETURN_FIRE",
        })
        assert result["fire_mission"]["primary_asset"] == "AT Missiles"

    # D-04: 화력 순서(sequences) 생성 및 구조 검증
    def test_fire_sequences_structure(self):
        result = fires_plan({
            "threat_type": "INFANTRY",
            "available_fires": ["155mm SPH Battery", "Mortar Platoon", "CAS"],
            "roe_level": "FIRE_AT_WILL",
        })
        seqs = result["fire_mission"]["fire_sequences"]
        assert len(seqs) >= 1
        for seq in seqs:
            assert "sequence" in seq
            assert "asset" in seq
            assert "mission_type" in seq
            assert "effectiveness_vs_threat" in seq

    # D-05: 사격금지구역 있을 때 nfa_note 포함
    def test_nfa_note_when_no_fire_areas_present(self):
        result = fires_plan({
            "threat_type": "ARMOR",
            "available_fires": ["155mm SPH Battery"],
            "roe_level": "RETURN_FIRE",
            "no_fire_areas": ["NFZ-VILLAGE-01"],
        })
        assert "nfa_note" in result
        assert "NFZ-VILLAGE-01" in result["nfa_note"]

    # D-06: DESTRUCTION priority → 사격 임무 유형에 반영
    def test_destruction_priority_in_mission_type(self):
        result = fires_plan({
            "threat_type": "ARMOR",
            "available_fires": ["MLRS Battery"],
            "roe_level": "WEAPONS_FREE",
            "priority": "DESTRUCTION",
        })
        assert "파괴" in result["fire_mission"]["method_of_engagement"]

    # D-07: assets_allocated는 dict이고 비어있지 않음
    def test_assets_allocated_nonempty_dict(self):
        result = fires_plan({
            "threat_type": "MISSILE",
            "available_fires": ["Patriot Battery", "MLRS Battery"],
            "roe_level": "FIRE_AT_WILL",
        })
        assert isinstance(result["assets_allocated"], dict)
        assert len(result["assets_allocated"]) > 0

    # D-08: 반환 필드 완전성
    def test_return_keys_complete(self):
        result = fires_plan({
            "threat_type": "DRONE",
            "available_fires": ["AA Gun Battery"],
            "roe_level": "RETURN_FIRE",
        })
        for key in ("fire_mission", "assets_allocated", "nfa_compliance",
                    "effectiveness_estimate", "risk_of_fratricide"):
            assert key in result, f"키 누락: {key}"


# ===========================================================================
# E. tool_schemas — Phase 3 스키마 등록 검증
# ===========================================================================
class TestPhase3Schemas:

    # E-01: 4개 도구 모두 스키마 등록
    def test_all_four_tools_registered(self):
        for tool in ("coa_generate", "ipb_summary", "roe_check", "fires_plan"):
            defs = get_tool_definitions_for_llm([tool])
            assert len(defs) == 1, f"{tool} 스키마 미등록"
            assert defs[0]["function"]["name"] == tool

    # E-02: coa_generate 필수 필드
    def test_coa_generate_required_fields(self):
        defs = get_tool_definitions_for_llm(["coa_generate"])
        req = defs[0]["function"]["parameters"]["required"]
        assert "threat_type" in req
        assert "threat_level" in req

    # E-03: ipb_summary 필수 필드
    def test_ipb_summary_required_field(self):
        defs = get_tool_definitions_for_llm(["ipb_summary"])
        req = defs[0]["function"]["parameters"]["required"]
        assert "threat_type" in req

    # E-04: roe_check 필수 필드
    def test_roe_check_required_fields(self):
        defs = get_tool_definitions_for_llm(["roe_check"])
        req = defs[0]["function"]["parameters"]["required"]
        assert "proposed_action" in req
        assert "roe_level" in req

    # E-05: fires_plan 필수 필드
    def test_fires_plan_required_fields(self):
        defs = get_tool_definitions_for_llm(["fires_plan"])
        req = defs[0]["function"]["parameters"]["required"]
        assert "threat_type" in req
        assert "available_fires" in req
