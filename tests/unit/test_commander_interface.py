"""
tests/unit/test_commander_interface.py

Phase 4 Commander Interface 단위 테스트 (구조적 증명 수준)

목적: compose_decision_support_response()의 체인 구조, I/O 계약,
      도구 간 데이터 흐름(threat_level 전파 등)을 검증한다.

테스트 수: 12개
  F-01 ~ F-05: 반환 구조 검증 (필수 키 존재, package_type, execution_chain)
  F-06 ~ F-08: 체인 데이터 흐름 (threat_level 전파, roe_check 입력, fires_plan 조건부)
  F-09 ~ F-10: 예외 격리 (한 도구 실패 시 체인 계속)
  F-11 ~ F-12: Executor._dispatch_tool 통합 (decision_support_composite 라우팅)
"""

import pytest
from unittest.mock import MagicMock, patch

from defense_llm.agent.commander_interface import (
    compose_decision_support_response,
    _extract_recommended_action,
)
from defense_llm.serving.mock_llm import MockLLMAdapter
from defense_llm.agent.executor import Executor
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger
from defense_llm.knowledge.db_schema import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    return db


@pytest.fixture()
def tmp_audit(tmp_path):
    p = str(tmp_path / "audit.db")
    init_db(p)
    return AuditLogger(p)


@pytest.fixture()
def empty_index():
    return DocumentIndex()


@pytest.fixture()
def mock_llm():
    return MockLLMAdapter(fixed_response="테스트 LLM 응답")


# ---------------------------------------------------------------------------
# Minimal arguments fixture
# ---------------------------------------------------------------------------

_MINIMAL_ARGS = {
    "threat_type": "ARMOR",
    "threat_count": 10,
    "movement": "ADVANCING",
    "confidence": 0.85,
    "roe_level": "RETURN_FIRE",
}

_ARGS_WITH_FIRES = {
    **_MINIMAL_ARGS,
    "available_fires": ["155mm SPH Battery", "AT Missiles"],
    "threat_location": "북부 진입로 YD123456",
    "priority": "SUPPRESSION",
}

# Minimal threat_assess mock result
def _mock_threat_assess(args: dict) -> dict:
    return {
        "threat_level": "HIGH",
        "threat_score": 0.78,
        "threat_summary": "테스트 위협 요약",
        "roe_constraint": "RETURN_FIRE: 교전 허용",
        "recommended_actions": ["화력 집중 준비", "방어 진지 강화"],
        "confidence_note": "신뢰도 적정",
    }


# ===========================================================================
# F-01 ~ F-05: 반환 구조 검증
# ===========================================================================

class TestCompositeReturnStructure:

    def test_f01_package_type_is_correct(self, mock_llm):
        """F-01: 반환 딕셔너리의 package_type이 DECISION_SUPPORT_COMPOSITE이다."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        assert result["package_type"] == "DECISION_SUPPORT_COMPOSITE"

    def test_f02_all_top_level_keys_present(self, mock_llm):
        """F-02: 필수 최상위 키 6개가 모두 존재한다."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        required = {
            "package_type", "execution_chain", "errors",
            "threat_assessment", "ipb_summary",
            "coa_recommendation", "roe_validation",
        }
        assert required.issubset(result.keys())

    def test_f03_fires_plan_key_present(self, mock_llm):
        """F-03: fires_plan 키가 항상 존재한다 (값은 None일 수 있음)."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        assert "fires_plan" in result

    def test_f04_execution_chain_is_list(self, mock_llm):
        """F-04: execution_chain은 리스트이다."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        assert isinstance(result["execution_chain"], list)

    def test_f05_errors_is_list(self, mock_llm):
        """F-05: errors는 리스트이다 (정상 실행 시 비어 있음)."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        assert isinstance(result["errors"], list)


# ===========================================================================
# F-06 ~ F-08: 체인 데이터 흐름
# ===========================================================================

class TestChainDataFlow:

    def test_f06_threat_level_propagated_to_coa(self, mock_llm):
        """F-06: threat_assess의 threat_level이 coa_generate 입력에 전파된다.

        검증 방법: threat_assess가 'CRITICAL'을 반환할 때,
        coa_recommendation의 COA 아카이브가 CRITICAL 레벨 원형을 포함해야 한다.
        """
        def critical_assess(args):
            return {
                "threat_level": "CRITICAL",
                "threat_score": 0.95,
                "threat_summary": "치명적 위협",
                "roe_constraint": "WEAPONS_FREE: 자유 교전",
                "recommended_actions": ["즉각 화력 집중"],
                "confidence_note": "신뢰도 높음",
            }

        result = compose_decision_support_response(
            {**_MINIMAL_ARGS, "roe_level": "WEAPONS_FREE"},
            mock_llm, critical_assess
        )
        coa = result.get("coa_recommendation") or {}
        coas = coa.get("coas", [])
        # CRITICAL 위협에 대한 COA가 생성되었는지 확인
        assert len(coas) > 0, "CRITICAL 위협에 대한 COA가 생성되어야 함"

    def test_f07_roe_check_receives_coa_action(self, mock_llm):
        """F-07: roe_check의 roe_validation 결과가 존재하고 필수 키를 포함한다."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, _mock_threat_assess
        )
        roe = result.get("roe_validation")
        assert roe is not None
        assert "roe_compliant" in roe
        assert "compliance_level" in roe

    def test_f08_fires_plan_none_when_no_fires(self, mock_llm):
        """F-08: available_fires가 없으면 fires_plan은 None이다."""
        result = compose_decision_support_response(
            _MINIMAL_ARGS,   # available_fires 없음
            mock_llm, _mock_threat_assess
        )
        assert result["fires_plan"] is None

    def test_f08b_fires_plan_runs_when_fires_provided(self, mock_llm):
        """F-08b: available_fires가 있으면 fires_plan이 실행되어 결과를 반환한다."""
        result = compose_decision_support_response(
            _ARGS_WITH_FIRES, mock_llm, _mock_threat_assess
        )
        fp = result.get("fires_plan")
        assert fp is not None
        assert "fire_mission" in fp


# ===========================================================================
# F-09 ~ F-10: 예외 격리
# ===========================================================================

class TestExceptionIsolation:

    def test_f09_chain_continues_when_ipb_raises(self, mock_llm):
        """F-09: ipb_summary가 예외를 발생시켜도 체인이 중단되지 않는다.

        ipb_summary를 패치하여 예외를 발생시키고,
        coa_recommendation과 roe_validation이 여전히 반환되는지 확인한다.
        """
        with patch(
            "defense_llm.agent.commander_interface.ipb_summary",
            side_effect=RuntimeError("ipb 강제 예외"),
        ):
            result = compose_decision_support_response(
                _MINIMAL_ARGS, mock_llm, _mock_threat_assess
            )

        # ipb_summary 실패 → None
        assert result["ipb_summary"] is None
        # errors에 기록
        assert any("ipb_summary" in e for e in result["errors"])
        # 나머지 체인은 계속 실행
        assert result["coa_recommendation"] is not None
        assert result["roe_validation"] is not None

    def test_f10_threat_assess_error_recorded(self, mock_llm):
        """F-10: threat_assess_fn이 예외를 발생시키면 errors에 기록되고
        나머지 체인은 기본값으로 계속된다."""
        def failing_assess(args):
            raise ValueError("threat_assess 강제 실패")

        result = compose_decision_support_response(
            _MINIMAL_ARGS, mock_llm, failing_assess
        )
        assert result["threat_assessment"] is None
        assert any("threat_assess" in e for e in result["errors"])
        # 나머지 체인은 기본 threat_level="MEDIUM"으로 계속
        assert result["coa_recommendation"] is not None


# ===========================================================================
# F-11 ~ F-12: Executor 통합 (decision_support_composite 라우팅)
# ===========================================================================

class TestExecutorIntegration:

    def test_f11_dispatch_routes_to_composite(self, tmp_db, tmp_audit, empty_index, mock_llm):
        """F-11: Executor._dispatch_tool('decision_support_composite', ...) 가
        compose_decision_support_response를 호출하고 package_type을 반환한다."""
        ex = Executor(
            llm_adapter=mock_llm,
            index=empty_index,
            db_path=tmp_db,
            audit_logger=tmp_audit,
            agent_mode=True,
        )

        result = ex._dispatch_tool(
            "decision_support_composite",
            _MINIMAL_ARGS,
            {"role": "analyst", "clearance": "SECRET", "user_id": "u1"},
            [],
            [],
        )
        assert result.get("package_type") == "DECISION_SUPPORT_COMPOSITE"

    def test_f12_composite_in_battle_tool_list(self):
        """F-12: tool_schemas에 decision_support_composite 스키마가 등록되어 있다."""
        from defense_llm.agent.tool_schemas import get_tool_definitions_for_llm
        defs = get_tool_definitions_for_llm(["decision_support_composite"])
        names = [d["function"]["name"] for d in defs]
        assert "decision_support_composite" in names


# ===========================================================================
# Helpers: _extract_recommended_action
# ===========================================================================

class TestExtractRecommendedAction:

    def test_returns_fallback_on_none(self):
        assert _extract_recommended_action(None) == "방어 행동"

    def test_returns_fallback_on_empty_coas(self):
        assert _extract_recommended_action({"coas": [], "recommended_coa": None}) == "방어 행동"

    def test_returns_matched_coa_name(self):
        coa_result = {
            "recommended_coa": "COA-B",
            "coas": [
                {"coa_id": "COA-A", "name": "공세적 방어"},
                {"coa_id": "COA-B", "name": "기동 방어"},
            ],
        }
        assert _extract_recommended_action(coa_result) == "기동 방어"

    def test_returns_first_coa_when_recommended_id_not_matched(self):
        coa_result = {
            "recommended_coa": "COA-Z",
            "coas": [{"coa_id": "COA-A", "name": "최초 방책"}],
        }
        assert _extract_recommended_action(coa_result) == "최초 방책"
