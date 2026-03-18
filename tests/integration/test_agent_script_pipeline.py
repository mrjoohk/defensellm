"""IF-006: Integration test for the full agent script execution pipeline.

Tests the complete flow:
  User query
    → LLM (search_docs tool_call) → RAG retrieval
    → LLM (create_script tool_call) → Python script written
    → LLM (create_batch_script tool_call) → Batch wrapper written
    → LLM (execute_batch_script tool_call) → Script executed
    → LLM (save_results_csv tool_call) → CSV saved
    → LLM (final answer) → Standard response with audit log entry
"""

import csv
import os
import sqlite3

import pytest

import defense_llm.agent.script_tools as st
from defense_llm.agent.executor import Executor
from defense_llm.audit.logger import AuditLogger
from defense_llm.knowledge.db_schema import init_db
from defense_llm.rag.chunker import chunk_document
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.serving.mock_llm import MockLLMAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace(tmp_path):
    """A temp directory registered as an allowed script path."""
    st.add_allowed_path(str(tmp_path))
    yield tmp_path
    abs_path = os.path.abspath(str(tmp_path))
    if abs_path in st.ALLOWED_BASE_PATHS:
        st.ALLOWED_BASE_PATHS.remove(abs_path)


@pytest.fixture()
def db_path(tmp_path):
    p = str(tmp_path / "kb.db")
    init_db(p)
    return p


@pytest.fixture()
def audit_path(tmp_path):
    p = str(tmp_path / "audit.db")
    init_db(p)
    return p


@pytest.fixture()
def populated_index():
    index = DocumentIndex()
    chunks = chunk_document(
        doc_id="DOC-KF21", version="v1",
        text="KF-21 항공기의 최대 순항 속도는 마하 1.8이며 운용 고도는 15,000m이다.",
        security_label="PUBLIC", doc_field="air",
    )
    index.add_chunks(chunks["chunks"])
    return index


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

def test_full_agent_script_pipeline(workspace, db_path, audit_path, populated_index):
    base = str(workspace)
    script_path = os.path.join(base, "test_script.py")
    batch_path = os.path.join(base, "run.bat")
    results_dir = os.path.join(base, "results")
    csv_path = os.path.join(results_dir, "result.csv")

    # Forward-slash variants for safe embedding in Python script literals
    results_dir_fwd = results_dir.replace("\\", "/")
    csv_path_fwd = csv_path.replace("\\", "/")

    expected_answer = f"분석 완료. 결과는 {csv_path}에 저장됨."

    tool_call_sequence = [
        # 1. Search docs
        [{"id": "tc0", "type": "function",
          "function": {"name": "search_docs",
                       "arguments": {"query": "KF-21 속도 분석", "top_k": 3}}}],
        # 2. Create analysis script
        [{"id": "tc1", "type": "function",
          "function": {"name": "create_script",
                       "arguments": {
                           "script_path": script_path,
                           "script_content": (
                               "import csv, os\n"
                               f"os.makedirs('{results_dir_fwd}', exist_ok=True)\n"
                               f"with open('{csv_path_fwd}', 'w', newline='', encoding='utf-8-sig') as f:\n"
                               "    w = csv.DictWriter(f, fieldnames=['platform','mach'])\n"
                               "    w.writeheader()\n"
                               "    w.writerow({'platform': 'KF-21', 'mach': '1.8'})\n"
                               "print('done')\n"
                           ),
                       }}}],
        # 3. Create batch wrapper
        [{"id": "tc2", "type": "function",
          "function": {"name": "create_batch_script",
                       "arguments": {"batch_path": batch_path,
                                     "script_path": script_path}}}],
        # 4. Execute batch script
        [{"id": "tc3", "type": "function",
          "function": {"name": "execute_batch_script",
                       "arguments": {"batch_path": batch_path,
                                     "timeout_seconds": 30}}}],
        # 5. Final text answer
        None,
    ]

    audit = AuditLogger(audit_path)
    mock = MockLLMAdapter(
        fixed_response=expected_answer,
        tool_call_sequence=tool_call_sequence,
    )
    ex = Executor(
        llm_adapter=mock,
        index=populated_index,
        db_path=db_path,
        audit_logger=audit,
        agent_mode=True,
        max_agent_turns=10,
        script_tools_enabled=True,
    )

    user_ctx = {"role": "analyst", "clearance": "PUBLIC", "user_id": "if006-user"}
    resp = ex.execute([], user_ctx, query="KF-21 속도 분석 후 결과를 CSV로 저장해줘")

    # ---- Response schema valid ----
    assert "request_id" in resp
    assert "data" in resp
    assert "hash" in resp

    # ---- Answer contains CSV path ----
    assert "result.csv" in resp["data"]["answer"]

    # ---- CSV file was created by the script ----
    assert os.path.exists(csv_path), f"Expected CSV at {csv_path}"
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["platform"] == "KF-21"

    # ---- Audit log has entries ----
    conn = sqlite3.connect(audit_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM audit_log")
    count = cursor.fetchone()[0]
    conn.close()
    assert count >= 1   # at least the main request log entry

    # ---- Script files were created ----
    assert os.path.exists(script_path)
    assert os.path.exists(batch_path)

    # ---- Correct number of LLM calls ----
    assert mock.call_count == 5
