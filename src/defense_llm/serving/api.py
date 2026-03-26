"""
api.py — Phase 5: FastAPI Server + Agent Endpoint + Web UI

엔드포인트:
  GET  /           → 웹 UI (battle_context JSON 업로드 포함)
  POST /agent      → 에이전트 실행, 표준 응답 반환
  GET  /health     → 헬스체크

설계 원칙 (구조적 증명 단계):
  - MockLLMAdapter + 임시 SQLite + 빈 DocumentIndex로 초기화
  - 인증 없음 (향후 JWTAuthManager 연동 예정)
  - battle_context JSON은 요청 본문 또는 파일 업로드 양쪽 지원
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# ── Internal imports ────────────────────────────────────────────────────────
from ..agent.battle_context import BattleSituationParser, validate_battle_situation
from ..agent.executor import Executor
from ..audit.logger import AuditLogger
from ..knowledge.db_schema import init_db
from ..rag.indexer import DocumentIndex
from ..serving.mock_llm import MockLLMAdapter


# ===========================================================================
# App state container
# ===========================================================================

class _AppState:
    executor: Optional[Executor] = None
    db_path: Optional[str] = None
    _tmp_dir: Optional[tempfile.TemporaryDirectory] = None


_state = _AppState()


# ===========================================================================
# Lifespan (startup / shutdown)
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Executor on startup; cleanup on shutdown."""
    _state._tmp_dir = tempfile.TemporaryDirectory()
    _state.db_path = os.path.join(_state._tmp_dir.name, "defense.db")
    init_db(_state.db_path)

    _state.executor = Executor(
        llm_adapter=MockLLMAdapter(
            fixed_response="분석 완료. 전술 상황을 검토하였습니다.",
        ),
        index=DocumentIndex(),
        db_path=_state.db_path,
        audit_logger=AuditLogger(_state.db_path),
        agent_mode=True,
        max_agent_turns=10,
    )
    yield
    _state._tmp_dir.cleanup()


# ===========================================================================
# FastAPI app
# ===========================================================================

app = FastAPI(
    title="Defense LLM Agent API",
    description="전투 상황 의사결정 지원 에이전트 API (Phase 5)",
    version="0.5.0",
    lifespan=lifespan,
)


# ===========================================================================
# Pydantic schemas
# ===========================================================================

class AgentRequest(BaseModel):
    query: str = Field(..., description="사용자 질의 문자열")
    battle_situation: Optional[Dict[str, Any]] = Field(
        None,
        description="BattleSituationPrompt JSON 딕셔너리 (선택)",
    )
    agent_mode: bool = Field(True, description="에이전트 모드 활성화 (기본값: True)")
    use_composite: bool = Field(
        False,
        description="decision_support_composite 도구 직접 트리거 (Phase 4 체인)",
    )
    user_context: Dict[str, str] = Field(
        default_factory=lambda: {
            "role": "analyst",
            "clearance": "SECRET",
            "user_id": "api_user",
        },
        description="사용자 컨텍스트 (role / clearance / user_id)",
    )


class AgentResponse(BaseModel):
    request_id: str
    answer: str
    citations: List[Dict[str, Any]]
    error_code: Optional[str]
    tool_call_log: List[Dict[str, Any]]
    battle_context_parsed: bool = Field(
        False,
        description="battle_situation이 성공적으로 파싱되었는지 여부",
    )


# ===========================================================================
# Endpoints
# ===========================================================================

@app.get("/health")
def health():
    """헬스체크 — Executor 초기화 여부 포함."""
    return {
        "status": "ok",
        "executor_ready": _state.executor is not None,
    }


@app.post("/agent", response_model=AgentResponse)
def agent_endpoint(request: AgentRequest):
    """에이전트 엔드포인트.

    battle_situation JSON이 있으면 BattleSituationContext로 파싱하여
    Executor.execute()에 전달한다.
    """
    if _state.executor is None:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    # ── Parse battle_context ────────────────────────────────────────────────
    battle_context = None
    battle_context_parsed = False

    if request.battle_situation:
        # Step 1: structural parse (KeyError → missing required field)
        try:
            battle_context = BattleSituationParser.from_dict(request.battle_situation)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": "battle_situation parse failed", "errors": [str(exc)]},
            )
        # Step 2: semantic validation (invalid ENUM values, range checks)
        errors = validate_battle_situation(battle_context)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"message": "battle_situation validation failed", "errors": errors},
            )
        battle_context_parsed = True

    # ── Build query: inject use_composite hint ──────────────────────────────
    query = request.query
    if request.use_composite and battle_context is not None:
        query = f"[use_composite=true] {query}"

    # ── Execute ─────────────────────────────────────────────────────────────
    result = _state.executor.execute(
        tool_plan=[],
        user_context=request.user_context,
        query=query,
        agent_mode=request.agent_mode,
        battle_context=battle_context,
    )

    # Standard response schema: answer is nested under "data" key
    return AgentResponse(
        request_id=result.get("request_id", str(uuid.uuid4())),
        answer=result.get("data", {}).get("answer", ""),
        citations=result.get("citations", []),
        error_code=result.get("error", None),  # executor uses "error" not "error_code"
        tool_call_log=result.get("tool_call_log", []),
        battle_context_parsed=battle_context_parsed,
    )


@app.post("/agent/upload", response_model=AgentResponse)
async def agent_upload_endpoint(
    query: str,
    battle_situation_file: Optional[UploadFile] = File(None),
    agent_mode: bool = True,
    use_composite: bool = False,
):
    """파일 업로드 방식 에이전트 엔드포인트.

    battle_situation_file: JSON 파일 업로드 (BattleSituationPrompt 스키마)
    """
    battle_situation: Optional[Dict[str, Any]] = None

    if battle_situation_file is not None:
        content = await battle_situation_file.read()
        try:
            battle_situation = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"JSON 파싱 실패: {exc}",
            )

    req = AgentRequest(
        query=query,
        battle_situation=battle_situation,
        agent_mode=agent_mode,
        use_composite=use_composite,
    )
    return agent_endpoint(req)


# ===========================================================================
# Web UI (GET /)
# ===========================================================================

_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Defense LLM — Agent Interface</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 14px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  header .badge {
    background: #238636;
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: .5px;
  }
  header h1 { font-size: 17px; font-weight: 600; color: #f0f6fc; }
  .container {
    display: flex;
    flex: 1;
    gap: 0;
    max-height: calc(100vh - 53px);
  }
  /* ── LEFT PANEL ── */
  .left-panel {
    width: 420px;
    min-width: 340px;
    background: #161b22;
    border-right: 1px solid #30363d;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px;
    gap: 16px;
  }
  .section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: #8b949e;
    margin-bottom: 6px;
  }
  /* Query area */
  textarea {
    width: 100%;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #c9d1d9;
    font-size: 13px;
    padding: 10px 12px;
    resize: vertical;
    outline: none;
    transition: border-color .2s;
    font-family: inherit;
  }
  textarea:focus { border-color: #58a6ff; }
  /* Battle context upload zone */
  .upload-zone {
    border: 2px dashed #30363d;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color .2s, background .2s;
    position: relative;
  }
  .upload-zone:hover, .upload-zone.drag-over {
    border-color: #58a6ff;
    background: #161b22;
  }
  .upload-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-zone .icon { font-size: 28px; margin-bottom: 4px; }
  .upload-zone .hint { font-size: 12px; color: #8b949e; }
  .upload-zone .filename {
    margin-top: 6px;
    font-size: 12px;
    color: #3fb950;
    font-weight: 600;
    display: none;
  }
  /* JSON paste toggle */
  details { border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
  details summary {
    padding: 8px 12px;
    cursor: pointer;
    font-size: 12px;
    color: #8b949e;
    background: #0d1117;
    user-select: none;
    list-style: none;
  }
  details summary::marker, details summary::-webkit-details-marker { display: none; }
  details summary::before { content: '▶ '; font-size: 10px; }
  details[open] summary::before { content: '▼ '; }
  details textarea { border-radius: 0; border: none; border-top: 1px solid #30363d; min-height: 120px; }
  /* Options */
  .options-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .option-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    cursor: pointer;
    user-select: none;
  }
  .option-label input[type=checkbox] {
    accent-color: #58a6ff;
    width: 15px;
    height: 15px;
  }
  /* User context */
  .ctx-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .ctx-field label { font-size: 11px; color: #8b949e; display: block; margin-bottom: 3px; }
  .ctx-field select, .ctx-field input[type=text] {
    width: 100%;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 5px;
    color: #c9d1d9;
    font-size: 12px;
    padding: 6px 8px;
    outline: none;
  }
  .ctx-field select:focus, .ctx-field input[type=text]:focus { border-color: #58a6ff; }
  /* Submit button */
  .btn-submit {
    width: 100%;
    padding: 11px;
    background: #238636;
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: background .2s;
    letter-spacing: .3px;
  }
  .btn-submit:hover { background: #2ea043; }
  .btn-submit:active { background: #1a7f2e; }
  .btn-submit:disabled { background: #21262d; color: #8b949e; cursor: not-allowed; }
  /* ── RIGHT PANEL ── */
  .right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
    gap: 14px;
    overflow-y: auto;
    background: #0d1117;
  }
  .response-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .response-header h2 { font-size: 14px; font-weight: 600; color: #f0f6fc; }
  .status-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 700;
    display: none;
  }
  .status-badge.ok { background: #1f4d26; color: #3fb950; display: inline-block; }
  .status-badge.error { background: #4d1f1f; color: #f85149; display: inline-block; }
  .status-badge.loading { background: #1f3a4d; color: #58a6ff; display: inline-block; }
  /* Response cards */
  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
  }
  .card-header {
    padding: 10px 14px;
    background: #21262d;
    border-bottom: 1px solid #30363d;
    font-size: 12px;
    font-weight: 700;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: .6px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-body {
    padding: 14px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .card-body.json-view {
    font-family: 'Consolas', 'Fira Code', monospace;
    font-size: 12px;
    color: #adbac7;
    max-height: 320px;
    overflow-y: auto;
  }
  /* Meta strip */
  .meta-strip {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 11px;
    color: #8b949e;
    padding: 8px 14px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
  }
  .meta-item strong { color: #c9d1d9; }
  /* Placeholder */
  .placeholder {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #30363d;
    font-size: 15px;
    gap: 8px;
  }
  .placeholder .icon { font-size: 48px; }
  /* Spinner */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner {
    width: 20px; height: 20px;
    border: 3px solid #30363d;
    border-top-color: #58a6ff;
    border-radius: 50%;
    animation: spin .8s linear infinite;
    display: none;
  }
  /* Highlight JSON keys */
  .jkey { color: #79c0ff; }
  .jstring { color: #a5d6ff; }
  .jnumber { color: #f2cc60; }
  .jbool { color: #ff7b72; }
  .jnull { color: #ff7b72; }
</style>
</head>
<body>

<header>
  <span class="badge">DEFENSE LLM</span>
  <h1>Agent Decision Support Interface</h1>
  <span style="margin-left:auto;font-size:11px;color:#8b949e;">Phase 5 — Structural Proof</span>
</header>

<div class="container">

  <!-- ── LEFT: Input Panel ── -->
  <div class="left-panel">

    <!-- Query -->
    <div>
      <div class="section-title">Query</div>
      <textarea id="queryInput" rows="3" placeholder="전술 질의를 입력하세요. 예: 현재 위협 수준을 평가하고 행동 방책을 제시하라."></textarea>
    </div>

    <!-- Battle Context Upload -->
    <div>
      <div class="section-title">Battle Context (JSON)</div>
      <div class="upload-zone" id="uploadZone">
        <input type="file" id="jsonFileInput" accept=".json,application/json"/>
        <div class="icon">📂</div>
        <div style="font-size:13px;color:#c9d1d9;margin-bottom:2px;">Click or drag JSON file here</div>
        <div class="hint">BattleSituationPrompt schema</div>
        <div class="filename" id="uploadedFilename"></div>
      </div>
    </div>

    <!-- Paste JSON -->
    <details id="pasteDetails">
      <summary>Paste JSON directly</summary>
      <textarea id="jsonPasteInput" rows="7" placeholder='{"scenario_id":"SCN-001", "timestamp":"2026-03-26T00:00:00Z", ...}'></textarea>
    </details>

    <!-- Options -->
    <div>
      <div class="section-title">Options</div>
      <div class="options-row">
        <label class="option-label">
          <input type="checkbox" id="agentMode" checked/>
          Agent Mode
        </label>
        <label class="option-label">
          <input type="checkbox" id="useComposite"/>
          Composite Chain
        </label>
      </div>
    </div>

    <!-- User Context -->
    <div>
      <div class="section-title">User Context</div>
      <div class="ctx-row">
        <div class="ctx-field">
          <label>Role</label>
          <select id="ctxRole">
            <option value="analyst">analyst</option>
            <option value="commander">commander</option>
            <option value="operator">operator</option>
          </select>
        </div>
        <div class="ctx-field">
          <label>Clearance</label>
          <select id="ctxClearance">
            <option value="SECRET">SECRET</option>
            <option value="CONFIDENTIAL" selected>CONFIDENTIAL</option>
            <option value="RESTRICTED">RESTRICTED</option>
            <option value="PUBLIC">PUBLIC</option>
          </select>
        </div>
        <div class="ctx-field" style="grid-column:1/-1;">
          <label>User ID</label>
          <input type="text" id="ctxUserId" value="api_user"/>
        </div>
      </div>
    </div>

    <!-- Submit -->
    <button class="btn-submit" id="submitBtn" onclick="submitRequest()">
      ▶ Run Agent
    </button>

  </div>

  <!-- ── RIGHT: Response Panel ── -->
  <div class="right-panel" id="rightPanel">

    <div class="response-header">
      <h2>Response</h2>
      <div style="display:flex;align-items:center;gap:8px;">
        <div class="spinner" id="spinner"></div>
        <span class="status-badge" id="statusBadge"></span>
      </div>
    </div>

    <div id="placeholderMsg" class="placeholder">
      <div class="icon">🛡️</div>
      <div>Submit a query to see the agent response</div>
    </div>

    <div id="responseContent" style="display:none;display:flex;flex-direction:column;gap:12px;">
      <!-- Meta strip -->
      <div class="meta-strip" id="metaStrip"></div>
      <!-- Answer card -->
      <div class="card" id="answerCard">
        <div class="card-header">🗣 Answer</div>
        <div class="card-body" id="answerBody"></div>
      </div>
      <!-- Tool Call Log -->
      <details class="card" id="toolLogCard" style="display:none;">
        <summary class="card-header" style="cursor:pointer;">🔧 Tool Call Log</summary>
        <div class="card-body json-view" id="toolLogBody"></div>
      </details>
      <!-- Citations -->
      <details class="card" id="citationsCard" style="display:none;">
        <summary class="card-header" style="cursor:pointer;">📎 Citations</summary>
        <div class="card-body json-view" id="citationsBody"></div>
      </details>
    </div>

  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let _uploadedJSON = null;

// ── File upload handling ───────────────────────────────────────────────────
const jsonFileInput = document.getElementById('jsonFileInput');
const uploadZone    = document.getElementById('uploadZone');
const filenameEl    = document.getElementById('uploadedFilename');
const pasteInput    = document.getElementById('jsonPasteInput');

jsonFileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  readFile(file);
});

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) readFile(file);
});

function readFile(file) {
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      _uploadedJSON = JSON.parse(ev.target.result);
      filenameEl.textContent = '✓ ' + file.name;
      filenameEl.style.display = 'block';
      // Sync to paste area for visibility
      pasteInput.value = JSON.stringify(_uploadedJSON, null, 2);
    } catch (err) {
      filenameEl.textContent = '✗ JSON parse error';
      filenameEl.style.color = '#f85149';
      filenameEl.style.display = 'block';
      _uploadedJSON = null;
    }
  };
  reader.readAsText(file);
}

// Also parse paste area when typing
pasteInput.addEventListener('input', () => {
  const v = pasteInput.value.trim();
  if (!v) { _uploadedJSON = null; return; }
  try {
    _uploadedJSON = JSON.parse(v);
    filenameEl.textContent = '✓ JSON valid (pasted)';
    filenameEl.style.color = '#3fb950';
    filenameEl.style.display = 'block';
  } catch (_) {
    filenameEl.textContent = '✗ JSON invalid';
    filenameEl.style.color = '#f85149';
    filenameEl.style.display = 'block';
    _uploadedJSON = null;
  }
});

// ── Submit ─────────────────────────────────────────────────────────────────
async function submitRequest() {
  const query = document.getElementById('queryInput').value.trim();
  if (!query) {
    alert('질의(Query)를 입력하세요.');
    return;
  }

  setLoading(true);

  const payload = {
    query,
    battle_situation: _uploadedJSON || null,
    agent_mode: document.getElementById('agentMode').checked,
    use_composite: document.getElementById('useComposite').checked,
    user_context: {
      role: document.getElementById('ctxRole').value,
      clearance: document.getElementById('ctxClearance').value,
      user_id: document.getElementById('ctxUserId').value || 'api_user',
    },
  };

  try {
    const res = await fetch('/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.detail || JSON.stringify(data));
    } else {
      showResponse(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message);
  } finally {
    setLoading(false);
  }
}

// ── Keyboard shortcut: Ctrl+Enter ─────────────────────────────────────────
document.getElementById('queryInput').addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') submitRequest();
});

// ── UI helpers ─────────────────────────────────────────────────────────────
function setLoading(on) {
  const btn = document.getElementById('submitBtn');
  const spinner = document.getElementById('spinner');
  btn.disabled = on;
  btn.textContent = on ? '⌛ Running...' : '▶ Run Agent';
  spinner.style.display = on ? 'block' : 'none';
  const badge = document.getElementById('statusBadge');
  if (on) {
    badge.className = 'status-badge loading';
    badge.textContent = 'RUNNING';
    badge.style.display = 'inline-block';
  }
}

function showResponse(data) {
  document.getElementById('placeholderMsg').style.display = 'none';
  const rc = document.getElementById('responseContent');
  rc.style.display = 'flex';
  rc.style.flexDirection = 'column';
  rc.style.gap = '12px';

  const badge = document.getElementById('statusBadge');
  if (data.error_code) {
    badge.className = 'status-badge error';
    badge.textContent = data.error_code;
  } else {
    badge.className = 'status-badge ok';
    badge.textContent = 'OK';
  }

  // Meta strip
  document.getElementById('metaStrip').innerHTML = `
    <span class="meta-item"><strong>Request ID</strong> ${data.request_id}</span>
    <span class="meta-item"><strong>Battle Context</strong> ${data.battle_context_parsed ? '✓ parsed' : '—'}</span>
    <span class="meta-item"><strong>Tool Calls</strong> ${data.tool_call_log.length}</span>
    <span class="meta-item"><strong>Citations</strong> ${data.citations.length}</span>
  `;

  // Answer
  document.getElementById('answerBody').textContent = data.answer || '(empty)';

  // Tool call log
  const tlCard = document.getElementById('toolLogCard');
  const tlBody = document.getElementById('toolLogBody');
  if (data.tool_call_log && data.tool_call_log.length > 0) {
    tlCard.style.display = 'block';
    tlBody.innerHTML = syntaxHighlight(JSON.stringify(data.tool_call_log, null, 2));
  } else {
    tlCard.style.display = 'none';
  }

  // Citations
  const citCard = document.getElementById('citationsCard');
  const citBody = document.getElementById('citationsBody');
  if (data.citations && data.citations.length > 0) {
    citCard.style.display = 'block';
    citBody.innerHTML = syntaxHighlight(JSON.stringify(data.citations, null, 2));
  } else {
    citCard.style.display = 'none';
  }
}

function showError(msg) {
  document.getElementById('placeholderMsg').style.display = 'none';
  const rc = document.getElementById('responseContent');
  rc.style.display = 'flex';
  rc.style.flexDirection = 'column';
  rc.style.gap = '12px';

  const badge = document.getElementById('statusBadge');
  badge.className = 'status-badge error';
  badge.textContent = 'ERROR';

  document.getElementById('metaStrip').innerHTML = '';
  document.getElementById('answerBody').textContent = '⚠ ' + msg;
  document.getElementById('toolLogCard').style.display = 'none';
  document.getElementById('citationsCard').style.display = 'none';
}

// ── JSON syntax highlight ──────────────────────────────────────────────────
function syntaxHighlight(json) {
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let cls = 'jnumber';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'jkey' : 'jstring';
      } else if (/true|false/.test(match)) {
        cls = 'jbool';
      } else if (/null/.test(match)) {
        cls = 'jnull';
      }
      return '<span class="' + cls + '">' + match + '</span>';
    }
  );
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def web_ui():
    """Web UI — Battle Context JSON 업로드 + 에이전트 쿼리 입력창."""
    return HTMLResponse(content=_HTML)
