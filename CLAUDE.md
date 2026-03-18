# CLAUDE.md
## Execution Instructions for Claude Code

You are tasked with implementing a Defense-domain sLLM Agent System according to requirements.md.

You MUST follow the exact execution order below.

---

# ENVIRONMENT

## Python Interpreter
- **Path**: `C:/Users/user/anaconda3/envs/dllm/python`
- **Conda env**: `dllm`
- **Always use this interpreter** for all pytest, coverage, and Python execution commands.
- Command example: `C:/Users/user/anaconda3/envs/dllm/python -m pytest tests/`

---

# WORKFLOW RULES (from CLAUDE_ref.md)

### Rule 1 — Review Before Creating Output
> Before creating any final deliverable (document, file), first share the analysis/investigation summary with the user and wait for approval.

**Flow**: Start task → Perform analysis → Present findings to user → Await approval → Create output

### Rule 2 — Preserve Analysis as MD Files
> Save all analysis/investigation content created during tasks as MD files for reuse in future tasks.

**Filename convention**: `YYMMDD_HHMM_[description].md`
Example: `260318_1430_uf_status_analysis.md`

### Rule 3 — State Judgment Rationale
> Every decision, choice, or recommendation must include the rationale (판단 근거).

**Apply**: Include a "판단 근거:" section in all analysis MD files and user reports.

### Rule 4 — File Creation Log
> All files created in the working folder must be logged in `0.FilesUpdate.xlsx`.
> **If `0.FilesUpdate.xlsx` does not exist, create it first, then record the entry.**

| Column | Content |
|--------|---------|
| 일시 | YYYY-MM-DD HH:MM |
| 파일명 | Created filename |
| 요청 요약 | Core content of user's request |

### Rule 5 — Output Format Standard
> Deliverables containing tables or figures must be created as `.docx`.

| Condition | Format |
|-----------|--------|
| Contains table or figure | `.docx` |
| Text-focused analysis/memo | `.md` |
| Data/numeric-focused | `.xlsx` |
| Slide presentation | `.pptx` |

### Workflow Summary
```
Receive request
  → Perform analysis/investigation
  → [Rule 3] Summarize with judgment rationale
  → [Rule 1] Present to user for review → Await approval
  → Create output
  → [Rule 2] Save analysis as MD (yymmdd_hhmm_*.md)
  → [Rule 4] Update 0.FilesUpdate.xlsx
```

---

# IMPLEMENTATION STATUS (as of 2026-03-18)

## Unit Functions (UF) — All COMPLETED ✅

| UF-ID | Module | File | Status | Notes |
|-------|--------|------|--------|-------|
| UF-001 | config | `src/defense_llm/config/settings.py` | ✅ Complete | `load_config()`, env override |
| UF-010 | knowledge | `src/defense_llm/knowledge/db_schema.py` | ✅ Complete | SQLite DDL, idempotent |
| UF-011 | knowledge | `src/defense_llm/knowledge/document_meta.py` | ✅ Complete | register/validate doc meta |
| UF-012 | knowledge | `src/defense_llm/knowledge/glossary.py` | ✅ Complete | defense glossary mapping |
| UF-020 | rag | `src/defense_llm/rag/chunker.py` | ✅ Complete | `chunk_document()`, heading-aware; NOTE: param is `version` not `doc_rev` |
| UF-021 | rag | `src/defense_llm/rag/retriever.py` + `indexer.py` | ✅ Complete | BM25 + dense vector hybrid; `DocumentIndex` |
| UF-022 | rag | `src/defense_llm/rag/citation.py` | ✅ Complete | `package_citations()`, SHA-256 snippet hash |
| UF-030 | agent | `src/defense_llm/agent/planner_rules/classifier.py` + `plan_builder.py` | ✅ Complete | rule-based classification + plan builder |
| UF-031 | agent | `src/defense_llm/agent/executor.py` | ✅ Complete | `Executor` class, standard response schema |
| UF-032 | agent | `src/defense_llm/agent/tool_schemas.py` | ✅ Complete | `validate_tool_call()` per-tool JSON schema |
| UF-040 | security | `src/defense_llm/security/rbac.py` | ✅ Complete | RBAC + ABAC clearance check |
| UF-041 | security | `src/defense_llm/security/masking.py` | ✅ Complete | coordinates / frequency / sys_id masking |
| UF-050 | audit | `src/defense_llm/audit/logger.py` + `schema.py` | ✅ Complete | `AuditLogger`, SQLite append-only |
| UF-060 | serving | `src/defense_llm/serving/adapter.py` + `mock_llm.py` | ✅ Complete | `AbstractLLMAdapter` + `MockLLMAdapter` |
| UF-070 | eval | `src/defense_llm/eval/runner.py` | ✅ Complete | `EvalRunner`, QA pass-rate report |

## Extra Components (beyond original UF plan) — P0 Extensions ✅

| Component | File | Purpose |
|-----------|------|---------|
| Qwen25Adapter | `src/defense_llm/serving/qwen_adapter.py` | Production LLM adapter (lazy-load, HuggingFace) |
| AbstractEmbedder / Qwen25Embedder / TFIDFEmbedder | `src/defense_llm/rag/embedder.py` | Real embedding + TF-IDF fallback for tests |
| JWTAuthManager | `src/defense_llm/security/auth.py` | JWT issuance + verification (PyJWT) |

## Integration Functions (IF) — All COMPLETED ✅

| IF-ID | Scenario | Test File | Status |
|-------|----------|-----------|--------|
| IF-001 | Document upload → index → query → citation response | `tests/integration/test_document_pipeline.py` | ✅ Complete |
| IF-002 | Structured DB query → constraint → cited response | `tests/integration/test_kb_query.py` | ✅ Complete |
| IF-003 | Unauthorized access → blocked result | `tests/integration/test_security_access.py` | ✅ Complete |
| IF-004 | Audit log verification | `tests/integration/test_audit_logging.py` | ✅ Complete |
| IF-005 | Tool schema violation → safe failure | `tests/integration/test_tool_schema_violation.py` | ✅ Complete |

## Known Issues / Technical Debt

| Issue | Location | Impact | Action Required |
|-------|----------|--------|-----------------|
| `_fallback_web_search` uses network (duckduckgo, requests, bs4) | `executor.py:219–334` | Violates "No network access" rule; only triggers when `online_mode=True` | Ensure `online_mode` is never set in test/offline runs |
| UF-022 ID misused for "Dynamic Web Search Fallback" comment | `executor.py:157` | Comment confusion only | Clarify comment in next refactor |
| `UF-023` (Response Translation Processor) referenced in executor but not in `02_unit_functions.md` | `executor.py:207` | Undocumented feature | Add to `02_unit_functions.md` if keeping |
| `chunk_document()` uses `version`/`doc_rev` inconsistently | `chunker.py` vs spec | API drift from spec | Align parameter name in next cleanup |

---

# PHASE 1 — Requirements Formalization

1. Read requirements.md.
2. Convert all design-level requirements into structured REQ entries.
3. Create file:
   docs/01_requirements_analysis.md

Each REQ must contain:
- REQ-ID
- Description
- Input
- Output
- Success Criteria
- Validation Method
- Priority

No ambiguous wording allowed.

---

# PHASE 2 — Unit Function Decomposition

1. Decompose REQs into Unit Functions (UF).
2. Each UF must be implementable as an isolated Python function or class.

Create:
docs/02_unit_functions.md

Each UF must contain:
- UF-ID
- Module
- Purpose
- Input/Output Schema
- Exceptions
- Dependencies
- Related REQ-ID
- Test Points

Modules must include:
config
security
knowledge
rag
agent
serving
audit
eval

---

# PHASE 3 — Unit Tests & Coverage

1. Create test skeletons under tests/unit/
2. Every UF must have:
   - at least 1 success test
   - at least 1 failure test
3. LLM must be mocked.
4. No external services allowed.

Create:
docs/03_unit_test_coverage.md

Coverage Targets:
- Overall ≥ 70%
- Security/Audit ≥ 80%

---

# PHASE 4 — Integration Function Design

Combine UFs into Integration Functions (IF).

Create:
docs/04_integration_functions.md

Required IF scenarios:
1. Document upload → indexing → query → citation response
2. Structured DB query → constraint enforcement → cited response
3. Unauthorized search → blocked result
4. Audit logging verification
5. Tool schema violation → safe failure

Each IF must specify:
- Scenario
- Used UFs
- Input/Output
- Success Criteria
- Security Conditions

---

# PHASE 5 — Integration Tests

1. Implement integration tests in tests/integration/
2. Use SQLite temporary DB
3. Use mock LLM
4. Verify:
   - citation presence
   - security enforcement
   - audit log creation

Create:
docs/05_integration_test_coverage.md

---

# Implementation Rules

- No network access.
- No real model loading required.
- Serving layer must use adapter pattern.
- Planner must be rule-based.
- Executor must validate schema before responding.
- All outputs must follow the standard response schema in requirements.md.
- Use pytest + coverage.
- Provide README with reproducible commands.

---

# Final Output Requirements

At completion, provide:
1. File list created
2. pytest summary
3. coverage summary
4. REQ ↔ UF ↔ IF trace table
5. Upgrade notes for switching to 7B+

You must not skip any phase.
You must not collapse phases.
You must not introduce non-deterministic behavior.

---

# currentDate
Today's date is 2026-03-18.
