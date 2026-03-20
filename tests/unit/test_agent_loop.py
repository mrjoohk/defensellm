"""Tests for the ReAct agent loop in Executor._run_agent_loop."""

import os
import tempfile

import pytest

from defense_llm.agent.executor import Executor, E_LOOP_LIMIT
import defense_llm.agent.script_tools as st
from defense_llm.serving.mock_llm import MockLLMAdapter
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger
from defense_llm.knowledge.db_schema import init_db


# ---------------------------------------------------------------------------
# Shared fixtures
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


# ---------------------------------------------------------------------------
# Basic agent loop: text response on first turn (no tool_calls)
# ---------------------------------------------------------------------------

def test_agent_loop_immediate_text_answer(tmp_db, tmp_audit, empty_index):
    mock = MockLLMAdapter(fixed_response="KF-21의 최대속도는 마하 1.8입니다.")
    ex = make_executor(mock, empty_index, tmp_db, tmp_audit)
    resp = ex.execute([], {"role": "analyst", "clearance": "INTERNAL"}, query="KF-21 속도는?")
    assert resp["data"]["answer"] == "KF-21의 최대속도는 마하 1.8입니다."
    assert "error" not in resp


# ---------------------------------------------------------------------------
# Two-turn loop: search_docs → text answer → citations populated
# ---------------------------------------------------------------------------

def test_agent_loop_two_turns_with_search(tmp_db, tmp_audit):
    # Prepare index with one document
    from defense_llm.rag.chunker import chunk_document
    index = DocumentIndex()
    chunks_result = chunk_document(
        doc_id="DOC-001", version="v1",
        text="KF-21 항공기의 최대 순항 속도는 마하 1.8이다.",
        security_label="PUBLIC", doc_field="air",
    )
    index.add_chunks(chunks_result["chunks"])

    search_tc = [
        {
            "id": "c0", "type": "function",
            "function": {"name": "search_docs", "arguments": {"query": "KF-21 속도", "top_k": 3}},
        }
    ]
    mock = MockLLMAdapter(
        fixed_response="KF-21의 최대 순항 속도는 마하 1.8입니다.",
        tool_call_sequence=[search_tc, None],
    )
    ex = make_executor(mock, index, tmp_db, tmp_audit)
    resp = ex.execute(
        [], {"role": "analyst", "clearance": "PUBLIC"},
        query="KF-21 순항 속도는?",
    )
    assert "마하" in resp["data"]["answer"]
    assert mock.call_count == 2


# ---------------------------------------------------------------------------
# RBAC gate: search with insufficient clearance returns error in tool result
# ---------------------------------------------------------------------------

def test_agent_loop_rbac_blocked(tmp_db, tmp_audit, empty_index):
    search_tc = [
        {
            "id": "c0", "type": "function",
            "function": {
                "name": "search_docs",
                "arguments": {
                    "query": "기밀 무기 정보",
                    "security_label_filter": ["SECRET"],
                },
            },
        }
    ]
    mock = MockLLMAdapter(
        fixed_response="접근이 거부되었습니다.",
        tool_call_sequence=[search_tc, None],
    )
    ex = make_executor(mock, empty_index, tmp_db, tmp_audit)
    resp = ex.execute(
        [], {"role": "guest", "clearance": "PUBLIC"},
        query="기밀 무기 정보 알려줘",
    )
    # Loop should complete (LLM handles the E_AUTH tool result and answers)
    assert resp is not None
    assert mock.call_count == 2


# ---------------------------------------------------------------------------
# Max turns circuit breaker
# ---------------------------------------------------------------------------

def test_agent_loop_max_turns_exceeded(tmp_db, tmp_audit, empty_index):
    # LLM always returns a tool_call — never stops
    always_tc = [
        {
            "id": "c0", "type": "function",
            "function": {"name": "search_docs", "arguments": {"query": "x"}},
        }
    ]
    # tool_call_sequence with 20 identical entries
    mock = MockLLMAdapter(
        fixed_response="done",
        tool_call_sequence=[always_tc] * 20,
    )
    ex = make_executor(mock, empty_index, tmp_db, tmp_audit, max_agent_turns=3)
    resp = ex.execute([], {"role": "analyst", "clearance": "PUBLIC"}, query="test")
    assert resp.get("error") == E_LOOP_LIMIT


# ---------------------------------------------------------------------------
# Sentinel: [NO_RELEVANT_DOCS] clears citations
# ---------------------------------------------------------------------------

def test_agent_loop_sentinel_clears_citations(tmp_db, tmp_audit):
    from defense_llm.rag.chunker import chunk_document
    index = DocumentIndex()
    chunks = chunk_document(
        doc_id="D1", version="v1",
        text="관련 없는 문서 내용입니다.",
        security_label="PUBLIC", doc_field="air",
    )
    index.add_chunks(chunks["chunks"])

    # LLM returns sentinel after a search
    search_tc = [
        {
            "id": "c0", "type": "function",
            "function": {"name": "search_docs", "arguments": {"query": "완전히 다른 주제"}},
        }
    ]
    mock = MockLLMAdapter(
        fixed_response="[NO_RELEVANT_DOCS]",
        tool_call_sequence=[search_tc, None],
    )
    ex = make_executor(mock, index, tmp_db, tmp_audit)
    resp = ex.execute([], {"role": "analyst", "clearance": "PUBLIC"}, query="완전히 다른 주제")
    assert resp["citations"] == []
    assert "찾을 수 없습니다" in resp["data"]["answer"]


# ---------------------------------------------------------------------------
# Pipeline backward-compat: agent_mode=False uses _run_plan
# ---------------------------------------------------------------------------

def test_pipeline_mode_backward_compat(tmp_db, tmp_audit, empty_index):
    """agent_mode=False uses static _run_plan (pipeline). Response schema must be valid."""
    mock = MockLLMAdapter(fixed_response="파이프라인 답변")
    ex = Executor(
        llm_adapter=mock,
        index=empty_index,
        db_path=tmp_db,
        audit_logger=tmp_audit,
        agent_mode=False,
    )
    plan = [{"tool": "search_docs", "params": {"query": "test"}}]
    resp = ex.execute(plan, {"role": "analyst", "clearance": "PUBLIC"})
    # Pipeline ran successfully — standard response schema present
    assert "request_id" in resp
    assert "data" in resp
    assert "hash" in resp
    # Empty index → no context → LLM not called (returns "검색 결과가 없습니다" message)
    assert mock.call_count == 0


# ---------------------------------------------------------------------------
# Script execution flow (6-turn)
# ---------------------------------------------------------------------------

@pytest.fixture()
def allowed_tmpdir_for_scripts(tmp_path):
    st.add_allowed_path(str(tmp_path))
    yield tmp_path
    abs_path = os.path.abspath(str(tmp_path))
    if abs_path in st.ALLOWED_BASE_PATHS:
        st.ALLOWED_BASE_PATHS.remove(abs_path)


def test_agent_loop_full_script_pipeline(tmp_db, tmp_audit, empty_index, allowed_tmpdir_for_scripts):
    base = str(allowed_tmpdir_for_scripts)
    script_path = os.path.join(base, "test_script.py")
    batch_path = os.path.join(base, "run.bat")
    csv_path = os.path.join(base, "results", "result.csv")

    tool_call_sequence = [
        # Turn 0: search
        [{"id": "c0", "type": "function",
          "function": {"name": "search_docs", "arguments": {"query": "KF-21 분석"}}}],
        # Turn 1: create_script
        [{"id": "c1", "type": "function",
          "function": {"name": "create_script",
                       "arguments": {"script_path": script_path,
                                     "script_content": "print('analysis done')\n"}}}],
        # Turn 2: create_batch_script
        [{"id": "c2", "type": "function",
          "function": {"name": "create_batch_script",
                       "arguments": {"batch_path": batch_path,
                                     "script_path": script_path}}}],
        # Turn 3: execute_batch_script
        [{"id": "c3", "type": "function",
          "function": {"name": "execute_batch_script",
                       "arguments": {"batch_path": batch_path, "timeout_seconds": 30}}}],
        # Turn 4: save_results_csv
        [{"id": "c4", "type": "function",
          "function": {"name": "save_results_csv",
                       "arguments": {"data": [{"platform": "KF-21", "status": "ok"}],
                                     "csv_path": csv_path}}}],
        # Turn 5: final text answer
        None,
    ]

    mock = MockLLMAdapter(
        fixed_response=f"분석 완료. 결과는 {csv_path}에 저장됨.",
        tool_call_sequence=tool_call_sequence,
    )
    ex = make_executor(
        mock, empty_index, tmp_db, tmp_audit,
        script_tools_enabled=True, max_agent_turns=10,
    )
    resp = ex.execute(
        [], {"role": "analyst", "clearance": "PUBLIC", "user_id": "tester"},
        query="KF-21 분석 후 결과를 CSV로 저장해줘",
    )

    assert mock.call_count == 6
    assert os.path.exists(csv_path)
    assert "result.csv" in resp["data"]["answer"]
