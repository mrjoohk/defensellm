"""
tests/unit/test_threat_assess.py

Executor._threat_assess() 규칙 기반 위협 평가 핸들러 단위 테스트 (14개)
+ Executor.execute() battle_context 주입 통합 테스트 (3개)
합계: 17개
"""

import os
import tempfile
import pytest

from defense_llm.agent.executor import Executor, E_AUTH
from defense_llm.serving.mock_llm import MockLLMAdapter
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger
from defense_llm.knowledge.db_schema import init_db
from defense_llm.agent.battle_context import (
    BattleSituationParser,
    BattleSituationContext,
)


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


def make_executor(mock_llm, index, db, audit, **kwargs):
    return Executor(
        llm_adapter=mock_llm,
        index=index,
        db_path=db,
        audit_logger=audit,
        agent_mode=True,
        **kwargs,
    )


# Minimal BattleSituationContext
_MINIMAL_CTX_DICT = {
    "scenario_id": "SCN-TEST-001",
    "timestamp": "2026-03-26T09:00:00Z",
    "threat": {
        "type": "ARMOR",
        "count": 10,
        "location": {"description": "북부 진입로"},
        "movement": "ADVANCING",
        "confidence": 0.8,
    },
    "friendly_forces": {
        "unit_id": "1BN-A",
        "unit_type": "MECH_INF",
        "location": {"description": "방어 진지"},
        "available_fires": ["155mm SPH Battery", "AT Missiles"],
        "logistics_status": "ADEQUATE",
    },
    "constraints": {
        "roe_level": "RETURN_FIRE",
        "time_constraints": {"ttl_minutes": 30},
    },
    "query": {
        "intent": "THREAT_ASSESS",
        "text": "위협 평가를 수행하라.",
    },
}


# ---------------------------------------------------------------------------
# Helper: build a bare Executor for _threat_assess() unit tests
# ---------------------------------------------------------------------------

def _executor(tmp_db, tmp_audit, empty_index):
    return Executor(
        llm_adapter=MockLLMAdapter(fixed_response="OK"),
        index=empty_index,
        db_path=tmp_db,
        audit_logger=tmp_audit,
    )


# ===========================================================================
# _threat_assess() — 직접 단위 테스트
# ===========================================================================

class TestThreatAssessRuleLogic:

    # T-01: ARMOR + ADVANCING + high count → HIGH or CRITICAL
    def test_armor_advancing_high_count_is_high_or_critical(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "ARMOR", "count": 20,
            "movement": "ADVANCING", "confidence": 0.9,
        })
        assert result["threat_level"] in ("HIGH", "CRITICAL")
        assert result["threat_score"] >= 0.65

    # T-02: INFANTRY + RETREATING + low count → LOW or MINIMAL
    def test_infantry_retreating_low_count_is_low(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "INFANTRY", "count": 2,
            "movement": "RETREATING", "confidence": 0.7,
        })
        assert result["threat_level"] in ("LOW", "MINIMAL", "MEDIUM")
        assert result["threat_score"] < 0.65

    # T-03: MISSILE + ADVANCING → CRITICAL
    def test_missile_advancing_is_critical(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "MISSILE", "count": 5,
            "movement": "ADVANCING", "confidence": 0.95,
        })
        assert result["threat_level"] == "CRITICAL"
        assert result["threat_score"] >= 0.80

    # T-04: 신뢰도 0.0 → 점수가 0.5 미만으로 크게 감소
    def test_zero_confidence_reduces_score(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        r_high = ex._threat_assess({"threat_type": "ARMOR", "count": 10,
                                     "movement": "ADVANCING", "confidence": 1.0})
        r_zero = ex._threat_assess({"threat_type": "ARMOR", "count": 10,
                                     "movement": "ADVANCING", "confidence": 0.0})
        assert r_zero["threat_score"] < r_high["threat_score"]
        assert "낮습니다" in r_zero["confidence_note"]

    # T-05: count=1 vs count=50 → 점수 차이 발생
    def test_higher_count_increases_score(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        r1 = ex._threat_assess({"threat_type": "ARMOR", "count": 1, "confidence": 0.8})
        r50 = ex._threat_assess({"threat_type": "ARMOR", "count": 50, "confidence": 0.8})
        assert r50["threat_score"] > r1["threat_score"]

    # T-06: ROE=HOLD → 즉각 교전 권고 없음
    def test_roe_hold_no_immediate_fire_action(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "ARMOR", "count": 8,
            "movement": "ADVANCING", "confidence": 0.85,
            "roe_level": "HOLD",
        })
        fire_actions = [a for a in result["recommended_actions"]
                        if "화력 집중" in a or "사격" in a]
        assert len(fire_actions) == 0, f"HOLD ROE should not produce fire actions: {fire_actions}"
        assert "HOLD" in result["roe_constraint"]

    # T-07: ROE=WEAPONS_FREE → 화력 관련 행동 포함
    def test_roe_weapons_free_includes_fire_action(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "ARMOR", "count": 15,
            "movement": "ADVANCING", "confidence": 0.9,
            "roe_level": "WEAPONS_FREE",
        })
        assert any("화력" in a for a in result["recommended_actions"])

    # T-08: available_fires 있을 때 화력 준비 행동 포함 (ROE != HOLD)
    def test_available_fires_generates_fires_action(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "ARMOR", "count": 5, "confidence": 0.7,
            "roe_level": "RETURN_FIRE",
            "available_fires": ["155mm SPH Battery", "AT Missiles"],
        })
        assert any("155mm" in a or "AT" in a for a in result["recommended_actions"])

    # T-09: MECH_INF vs ARMOR → AT/공중 화력 우선 권고
    def test_mech_vs_armor_recommends_at_priority(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({
            "threat_type": "ARMOR", "count": 10, "confidence": 0.8,
            "roe_level": "FIRE_AT_WILL",
            "friendly_unit_type": "MECH_INF",
        })
        assert any("AT 미사일" in a or "공중" in a for a in result["recommended_actions"])

    # T-10: 반환 필드 완전성 확인
    def test_return_dict_has_all_required_keys(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({"threat_type": "INFANTRY", "count": 3})
        required_keys = {
            "threat_level", "threat_score", "threat_summary",
            "roe_constraint", "recommended_actions", "confidence_note",
        }
        assert required_keys.issubset(result.keys())

    # T-11: threat_score 범위 0.0~1.0 보장
    def test_threat_score_bounded_0_to_1(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        for tt in ("MISSILE", "INFANTRY", "CYBER", "ARMOR"):
            r = ex._threat_assess({"threat_type": tt, "count": 100, "confidence": 1.0,
                                    "movement": "ADVANCING"})
            assert 0.0 <= r["threat_score"] <= 1.0, f"{tt}: score={r['threat_score']}"

    # T-12: 알 수 없는 threat_type → 기본값 처리, 오류 없음
    def test_unknown_threat_type_uses_default(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({"threat_type": "SUBMARINE", "count": 3})
        assert "threat_level" in result
        assert 0.0 <= result["threat_score"] <= 1.0

    # T-13: recommended_actions는 리스트이고 비어있지 않음
    def test_recommended_actions_is_nonempty_list(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        result = ex._threat_assess({"threat_type": "AIR", "count": 4, "confidence": 0.6})
        assert isinstance(result["recommended_actions"], list)
        assert len(result["recommended_actions"]) > 0

    # T-14: FLANKING은 ADVANCING보다 movement modifier가 낮음 → 점수 차이 확인
    def test_advancing_scores_higher_than_flanking(self, tmp_db, tmp_audit, empty_index):
        ex = _executor(tmp_db, tmp_audit, empty_index)
        r_adv = ex._threat_assess({"threat_type": "ARMOR", "count": 5,
                                    "movement": "ADVANCING", "confidence": 0.8})
        r_flk = ex._threat_assess({"threat_type": "ARMOR", "count": 5,
                                    "movement": "FLANKING", "confidence": 0.8})
        assert r_adv["threat_score"] > r_flk["threat_score"]


# ===========================================================================
# Executor.execute() — battle_context 주입 통합 테스트
# ===========================================================================

class TestExecutorBattleContextIntegration:

    # T-15: battle_context 제공 시 user_content에 전투 상황 텍스트 포함
    def test_battle_context_injected_into_user_turn(
        self, tmp_db, tmp_audit, empty_index, monkeypatch
    ):
        """_run_agent_loop 내 LLM 호출 메시지에 battle_context.to_prompt_text() 포함 확인."""
        captured_messages = []

        class CaptureLLM(MockLLMAdapter):
            def chat(self, messages, **kw):
                captured_messages.extend(messages)
                return {"content": "테스트 응답", "tool_calls": None}

        ex = make_executor(CaptureLLM(), empty_index, tmp_db, tmp_audit)
        ctx = BattleSituationParser.from_dict(_MINIMAL_CTX_DICT)

        ex.execute(
            tool_plan=[],
            user_context={"role": "analyst", "clearance": "SECRET", "user_id": "u1"},
            query="위협을 평가하라.",
            agent_mode=True,
            battle_context=ctx,
        )

        user_msgs = [m["content"] for m in captured_messages if m["role"] == "user"]
        assert len(user_msgs) > 0
        first_user = user_msgs[0]
        assert "전투 상황 컨텍스트" in first_user
        assert "SCN-TEST-001" in first_user
        assert "ARMOR" in first_user

    # T-16: battle_context 없을 때 user_content는 query만 포함
    def test_no_battle_context_user_content_is_plain_query(
        self, tmp_db, tmp_audit, empty_index
    ):
        captured_messages = []

        class CaptureLLM(MockLLMAdapter):
            def chat(self, messages, **kw):
                captured_messages.extend(messages)
                return {"content": "응답", "tool_calls": None}

        ex = make_executor(CaptureLLM(), empty_index, tmp_db, tmp_audit)
        ex.execute(
            tool_plan=[],
            user_context={"role": "analyst", "clearance": "SECRET", "user_id": "u1"},
            query="일반 질의입니다.",
            agent_mode=True,
        )

        user_msgs = [m["content"] for m in captured_messages if m["role"] == "user"]
        assert user_msgs[0] == "일반 질의입니다."

    # T-17: battle_context 제공 시 threat_assess 도구가 tool_defs에 포함
    def test_threat_assess_in_tool_defs_when_battle_context_provided(
        self, tmp_db, tmp_audit, empty_index
    ):
        """threat_assess는 battle_context가 있을 때만 LLM에 제공된다."""
        captured_tool_names = []

        class CaptureLLM(MockLLMAdapter):
            def chat(self, messages, tools=None, **kw):
                if tools:
                    captured_tool_names.extend(
                        t["function"]["name"] for t in tools
                    )
                return {"content": "응답", "tool_calls": None}

        ex = make_executor(CaptureLLM(), empty_index, tmp_db, tmp_audit)
        ctx = BattleSituationParser.from_dict(_MINIMAL_CTX_DICT)

        ex.execute(
            tool_plan=[],
            user_context={"role": "analyst", "clearance": "SECRET", "user_id": "u1"},
            query="위협 평가",
            agent_mode=True,
            battle_context=ctx,
        )

        assert "threat_assess" in captured_tool_names

    # T-18 (보너스): battle_context 없을 때 threat_assess가 tool_defs에 없음
    def test_threat_assess_absent_from_tool_defs_without_battle_context(
        self, tmp_db, tmp_audit, empty_index
    ):
        captured_tool_names = []

        class CaptureLLM(MockLLMAdapter):
            def chat(self, messages, tools=None, **kw):
                if tools:
                    captured_tool_names.extend(
                        t["function"]["name"] for t in tools
                    )
                return {"content": "응답", "tool_calls": None}

        ex = make_executor(CaptureLLM(), empty_index, tmp_db, tmp_audit)
        ex.execute(
            tool_plan=[],
            user_context={"role": "analyst", "clearance": "SECRET", "user_id": "u1"},
            query="일반 질의",
            agent_mode=True,
        )

        assert "threat_assess" not in captured_tool_names
