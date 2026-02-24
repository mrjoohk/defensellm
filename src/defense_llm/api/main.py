"""FastAPI HTTP gateway for Defense LLM system.

Endpoints
---------
GET  /api/health
POST /api/query
POST /api/index
GET  /api/audit/{request_id}
GET  /api/audit/recent
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from ..knowledge.db_schema import init_db, get_connection
from ..knowledge.document_meta import register_document, compute_file_hash
from ..rag.indexer import DocumentIndex
from ..rag.chunker import chunk_document
from ..serving.mock_llm import MockLLMAdapter
from ..audit.logger import AuditLogger
from ..agent.executor import Executor
from ..agent.planner_rules.classifier import classify_query
from ..agent.planner_rules.plan_builder import build_plan

# ---------------------------------------------------------------------------
# Paths — can be overridden via environment variables
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..", "..", ".."))

DB_PATH = os.environ.get(
    "DEFENSE_LLM_DB_PATH",
    os.path.join(_PROJECT_ROOT, "data", "defense.db"),
)
INDEX_PATH = os.environ.get(
    "DEFENSE_LLM_INDEX_PATH",
    os.path.join(_PROJECT_ROOT, "data", "index"),
)
LOG_PATH = os.environ.get(
    "DEFENSE_LLM_LOG_PATH",
    os.path.join(_PROJECT_ROOT, "data", "logs"),
)

# ---------------------------------------------------------------------------
# App-level singletons (initialised in lifespan)
# ---------------------------------------------------------------------------
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Ensure data directories exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)

    # Initialize DB
    init_db(DB_PATH)

    # Load or create document index
    index = DocumentIndex()
    if os.path.exists(os.path.join(INDEX_PATH, "meta.json")):
        try:
            index = DocumentIndex.load(INDEX_PATH)
        except Exception:
            pass  # start fresh if corrupt

    # Use Qwen25Adapter for production
    from ..serving.qwen_adapter import Qwen25Adapter
    llm = Qwen25Adapter(model_id="Qwen/Qwen2.5-1.5B-Instruct", preload=True)

    audit_logger = AuditLogger(DB_PATH)

    executor = Executor(
        llm_adapter=llm,
        index=index,
        db_path=DB_PATH,
        audit_logger=audit_logger,
        model_version="Qwen/Qwen2.5-1.5B-Instruct",
        index_version=_load_index_version(INDEX_PATH),
    )

    _state.update(
        {
            "index": index,
            "executor": executor,
            "audit_logger": audit_logger,
            "llm": llm,
        }
    )

    yield

    # Persist index on shutdown
    try:
        _state["index"].save(INDEX_PATH)
    except Exception:
        pass


def _mock_answer(messages: list) -> str:
    """Generate a deterministic mock answer from context."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if "근거 자료:" in content:
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("[문서") or line.startswith("[DB"):
                        return f"[Mock 답변] 제공된 근거 자료에 기반한 답변입니다.\n\n{line[:120]}"
            return "[Mock 답변] 관련 문서가 색인되지 않아 정확한 답변이 어렵습니다."
    return "[Mock 답변] 입력을 처리할 수 없습니다."


def _load_index_version(index_path: str) -> str:
    import json
    meta_path = os.path.join(index_path, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                return json.load(f).get("index_version", "idx-00000000-0000")
        except Exception:
            pass
    return "idx-00000000-0000"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Defense LLM API",
    description="RAG + Structured KB query gateway with audit and security enforcement.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UserContext(BaseModel):
    role: str = "analyst"
    clearance: str = "INTERNAL"
    user_id: str = "u-001"


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    user: UserContext = Field(default_factory=UserContext)
    field_filters: List[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    show_citations: bool = True


class IndexResponse(BaseModel):
    success: bool
    doc_id: str
    doc_rev: str
    chunks_indexed: int
    file_hash: str
    index_version: str
    status: str
    scanned_pages: Optional[int] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    """Health check endpoint."""
    index: DocumentIndex = _state.get("index")
    chunk_count = len(index._meta) if index else 0
    llm = _state.get("llm")
    model_name = llm.model_name if llm else "unknown"
    return {
        "status": "ok",
        "db_path": DB_PATH,
        "index_path": INDEX_PATH,
        "chunks_indexed": chunk_count,
        "model": model_name,
        "index_version": _load_index_version(INDEX_PATH),
    }


@app.post("/api/query")
def query(req: QueryRequest):
    """Execute a query through the full RAG/agent pipeline."""
    executor: Executor = _state.get("executor")
    if not executor:
        raise HTTPException(status_code=503, detail="System not ready")

    user_context = {
        "role": req.user.role,
        "clearance": req.user.clearance,
        "user_id": req.user.user_id,
    }

    # Determine security label filter from clearance
    clearance_order = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]
    user_clearance_idx = clearance_order.index(req.user.clearance) if req.user.clearance in clearance_order else 1
    security_label_filter = clearance_order[: user_clearance_idx + 1]

    # Classify and build plan
    query_type = classify_query(req.question, user_context)
    plan = build_plan(
        query_type,
        context={
            "query": req.question,
            "field_filter": req.field_filters,
            "security_label_filter": security_label_filter,
            "top_k": req.top_k,
        },
    )

    # Inject top_k into search_docs step
    for step in plan:
        if step["tool"] == "search_docs":
            step["params"]["top_k"] = req.top_k

    response = executor.execute(plan, user_context)
    if not req.show_citations:
        response.pop("citations", None)

    return response


@app.post("/api/index", response_model=IndexResponse)
async def index_document(
    file: UploadFile = File(...),
    doc_id: str = Form(...),
    doc_rev: str = Form(...),
    title: str = Form(...),
    field: str = Form(...),
    security_label: str = Form(...),
    max_tokens: int = Form(default=256),
    overlap: int = Form(default=32),
):
    """Upload and index a document."""
    index: DocumentIndex = _state.get("index")
    if not index:
        raise HTTPException(status_code=503, detail="System not ready")

    content = await file.read()
    file_hash = compute_file_hash(content)

    # Register document metadata
    try:
        register_document(
            DB_PATH,
            {
                "doc_id": doc_id,
                "doc_rev": doc_rev,
                "title": title,
                "field": field,
                "security_label": security_label,
                "file_hash": file_hash,
            },
        )
    except ValueError as e:
        err_str = str(e)
        if "E_CONFLICT" in err_str:
            raise HTTPException(status_code=409, detail=err_str)
        raise HTTPException(status_code=422, detail=err_str)

    # Decode text or extract from PDF
    filename = file.filename or ""
    is_pdf = filename.lower().endswith(".pdf") or content.startswith(b"%PDF")

    parsed_pages = 0
    if is_pdf:
        import io
        try:
            import fitz  # PyMuPDF
            doc = fitz.open("pdf", content)
            pages = [page.get_text() for page in doc]
            doc.close()
        except ImportError:
            import pypdf
            fp = io.BytesIO(content)
            reader = pypdf.PdfReader(fp)
            pages = [page.extract_text() or "" for page in reader.pages]

        n_pages = len(pages)
        parsed_pages = n_pages
        if n_pages == 0:
            raise HTTPException(status_code=422, detail="PDF has no pages.")

        text = "\n\n".join(pages)
        char_density = len(text) / n_pages
        
        # UF-021: Reject Scanned PDFs
        if char_density < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Scanned PDF detected (Density: {char_density:.1f} chars/page). Indexing rejected as per UF-021."
            )
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("cp949")
            except Exception:
                raise HTTPException(status_code=422, detail="File must be UTF-8, CP949, or PDF.")

    # Chunk and index
    chunks = chunk_document(
        text=text,
        doc_id=doc_id,
        doc_rev=doc_rev,
        security_label=security_label,
        doc_field=field,
        max_tokens=max_tokens,
        overlap=overlap,
    )

    if chunks:
        index.add_chunks(chunks)
        # Save with versioned name
        import datetime
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")
        version = f"idx-{ts}"
        index.save(INDEX_PATH)
        # Write version to meta
        import json
        meta_path = os.path.join(INDEX_PATH, "meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
            except Exception:
                pass
        meta["index_version"] = version
        with open(meta_path, "w") as f:
            json.dump(meta, f)
    else:
        version = _load_index_version(INDEX_PATH)

    return IndexResponse(
        success=True,
        doc_id=doc_id,
        doc_rev=doc_rev,
        chunks_indexed=len(chunks),
        file_hash=file_hash,
        index_version=version,
        status="indexed",
        scanned_pages=parsed_pages,
    )


@app.get("/api/audit/recent")
def audit_recent(limit: int = 20):
    """Return the most recent audit records."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        import json
        for row in rows:
            row["citations"] = json.loads(row.get("citations_json") or "[]")
        return {"records": rows, "count": len(rows)}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/{request_id}")
def audit_by_request_id(request_id: str):
    """Return the audit record for a given request_id."""
    audit_logger: AuditLogger = _state.get("audit_logger")
    if not audit_logger:
        raise HTTPException(status_code=503, detail="System not ready")

    record = audit_logger.fetch_by_request_id(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No record for request_id={request_id}")
    return record


# ---------------------------------------------------------------------------
# Serve React build (production)
# ---------------------------------------------------------------------------
_WEB_DIST = os.path.join(_PROJECT_ROOT, "web", "dist")

if os.path.isdir(_WEB_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_WEB_DIST, "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str = ""):
        index_html = os.path.join(_WEB_DIST, "index.html")
        if os.path.exists(index_html):
            return FileResponse(index_html)
        raise HTTPException(status_code=404, detail="Frontend not built")
