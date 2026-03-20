# 02_unit_functions.md — 단위기능(UF) 정의

> 각 UF는 단일 모듈에서 독립적으로 테스트 가능한 최소 기능 단위입니다.
> **최종 갱신**: 2026-03-18 — 실제 구현 소스코드 기준으로 전면 동기화

---

## UF-001 — 설정 로딩 및 검증

- **모듈**: `config`
- **파일**: `src/defense_llm/config/settings.py`
- **목적**: YAML 파일 또는 환경변수에서 설정을 로딩하고 필수 항목을 검증한다.
- **입력**:
  ```json
  { "config_dict": "dict (optional)", "env_override": "bool" }
  ```
- **출력**:
  ```json
  {
    "model_name": "string",
    "db_path": "string",
    "index_path": "string",
    "log_path": "string",
    "security_level": "string",
    "index_version": "string",
    "db_schema_version": "string",
    "chunk_max_tokens": "int",
    "chunk_overlap": "int",
    "top_k": "int"
  }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 필수 키 누락 또는 유효하지 않은 security_level
- **의존성**: 없음
- **관련 REQ-ID**: REQ-001
- **테스트 포인트**:
  - 정상 설정 dict 로딩 성공
  - 필수 키 누락 시 ValueError(E_VALIDATION)
  - 환경변수 오버라이드 (`DEFENSE_LLM_*` prefix)
  - security_level 유효성 검사

---

## UF-010 — 정형 DB 스키마 초기화

- **모듈**: `knowledge`
- **파일**: `src/defense_llm/knowledge/db_schema.py`
- **목적**: SQLite DB에 documents / platforms / weapons / constraints / audit_log / schema_version 테이블을 생성한다.
- **입력**:
  ```json
  { "db_path": "string", "schema_version": "string (optional)" }
  ```
- **출력**:
  ```json
  { "success": true, "tables_created": ["documents", "platforms", "weapons", "constraints", "audit_log", "schema_version"] }
  ```
- **예외/에러 코드**:
  - `E_INTERNAL`: DB 연결 실패 또는 SQL 오류
- **의존성**: UF-001
- **관련 REQ-ID**: REQ-002
- **테스트 포인트**:
  - 테이블 생성 확인
  - 중복 초기화 시 오류 없이 처리 (CREATE TABLE IF NOT EXISTS)

---

## UF-011 — 문서 메타데이터 검증 및 등록

- **모듈**: `knowledge`
- **파일**: `src/defense_llm/knowledge/document_meta.py`
- **목적**: 문서 업로드 시 필수 메타데이터를 검증하고 SQLite documents 테이블에 등록한다.
- **핵심 함수**: `validate_document_meta(meta: dict) -> DocumentMeta`, `register_document(db_path, meta) -> dict`
- **입력**:
  ```json
  {
    "doc_id": "string",
    "doc_rev": "string",
    "title": "string",
    "field": "air|weapon|ground|sensor|comm",
    "security_label": "PUBLIC|INTERNAL|RESTRICTED|SECRET",
    "file_hash": "sha256 string",
    "page_count": "int (optional)"
  }
  ```
- **출력**:
  ```json
  { "registered": true, "doc_id": "string", "doc_rev": "string" }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 필수 필드 누락, 잘못된 field/security_label 값
  - `E_CONFLICT`: 동일 doc_id + doc_rev 중복 등록
- **의존성**: UF-010
- **관련 REQ-ID**: REQ-003, REQ-016
- **테스트 포인트**:
  - 정상 메타 등록 성공
  - 필수 필드 누락 시 E_VALIDATION
  - 중복 등록 시 E_CONFLICT
  - 유효하지 않은 field/security_label 시 E_VALIDATION

---

## UF-012 — Glossary 매핑

- **모듈**: `knowledge`
- **파일**: `src/defense_llm/knowledge/glossary.py`
- **목적**: 방산 약어/용어를 정규화된 표준 용어와 매핑한다. 기본 15개 용어(KF-21, AAM, AESA 등) 내장.
- **핵심 클래스**: `Glossary(entries=None)`
- **주요 메서드**:
  - `lookup(term: str) -> dict` — 단어 조회
  - `add(term, definition)` — 신규 용어 추가
  - `normalize_text(text: str) -> str` — 텍스트 내 약어 일괄 치환
  - `all_terms() -> dict` — 전체 사전 반환
- **입력** (`lookup`):
  ```json
  { "term": "string" }
  ```
- **출력** (`lookup`):
  ```json
  { "term": "string", "definition": "string | null", "found": "bool" }
  ```
- **예외/에러 코드**: 없음 (미등록 시 `found=false` 반환)
- **의존성**: 없음
- **관련 REQ-ID**: REQ-004
- **테스트 포인트**:
  - 등록된 약어(KF-21) 조회 시 정의 반환
  - 미등록 약어 조회 시 found=false
  - normalize_text로 텍스트 내 약어 치환 확인

---

## UF-020 — 문서 청킹 및 인덱싱

- **모듈**: `rag`
- **파일**: `src/defense_llm/rag/chunker.py`
- **목적**: 문서 텍스트를 섹션/단락 단위로 청킹하고 Chunk 객체 목록을 반환한다. Markdown 헤딩(#/##/###) 및 [PAGE N] 마커를 인식하여 section_path와 page_range를 추적한다.
- **핵심 함수**: `chunk_document(...) -> dict`
- **⚠️ 주의**: 스펙의 `doc_rev` 파라미터는 실제 코드에서 `version`으로 구현됨
- **입력**:
  ```json
  {
    "doc_id": "string",
    "version": "string",
    "text": "string",
    "security_label": "PUBLIC|INTERNAL|RESTRICTED|SECRET",
    "doc_field": "air|weapon|ground|sensor|comm",
    "doc_type": "string (optional, default='unknown')",
    "title": "string (optional)",
    "system": "string (optional)",
    "subsystem": "string (optional)",
    "date": "string (optional)",
    "language": "string (optional, default='en')",
    "source_uri": "string (optional)",
    "max_tokens": "int (default=512)",
    "overlap": "int (default=64)"
  }
  ```
- **출력**:
  ```json
  {
    "chunks": [
      {
        "chunk_id": "sha256[:16] string",
        "doc_id": "string",
        "version": "string",
        "page_range": "string",
        "section_id": "sec-NNNN",
        "section_path": "H1 > H2 > H3",
        "text": "string",
        "token_count": "int",
        "security_label": "string",
        "doc_field": "string",
        "doc_type": "string",
        "title": "string"
      }
    ],
    "indexed_count": "int"
  }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 빈 텍스트 또는 잘못된 파라미터 (max_tokens ≤ 0, overlap 범위 초과)
  - `E_INTERNAL`: 인덱스 쓰기 실패
- **의존성**: UF-011
- **관련 REQ-ID**: REQ-005, REQ-016
- **테스트 포인트**:
  - 청크 수 ≥ 1
  - 각 청크에 doc_id, page_range 포함
  - 최대 토큰 수 초과 청크 없음
  - 빈 텍스트 시 E_VALIDATION
  - Markdown 헤딩 인식 → section_path 설정
  - [PAGE N] 마커 → page_range 추적

---

## UF-021 — 하이브리드 검색 (BM25 + Vector)

- **모듈**: `rag`
- **파일**: `src/defense_llm/rag/retriever.py`, `src/defense_llm/rag/indexer.py`
- **목적**: 질의에 대해 BM25와 벡터 유사도 검색을 병행하고 메타 필터를 적용하여 결과를 반환한다.
- **핵심 클래스**: `DocumentIndex(embedder=None)`, `BM25Index`, `DenseVectorIndex`, `SimpleVectorIndex`(레거시)
- **핵심 함수**: `hybrid_search(index, query, top_k, field_filter, security_label_filter)`
- **embedder 주입**:
  - `embedder=None` → 레거시 TF-IDF `SimpleVectorIndex` 사용 (오프라인 테스트용)
  - `embedder=AbstractEmbedder` → `DenseVectorIndex` 사용 (코사인 유사도)
- **추가 기능**:
  - `add_chunks()` — 청크 추가 시 cosine similarity > 0.95 근사 중복 제거
  - `save(index_dir)` — BM25/Dense/Legacy 인덱스를 디스크에 저장 (pickle + JSON)
  - `load(index_dir, embedder)` — 저장된 인덱스 로드
  - `chunk_count()` — 현재 인덱스의 청크 수 반환
- **입력** (hybrid_search):
  ```json
  {
    "query": "string",
    "field_filter": ["string"],
    "security_label_filter": ["string"],
    "top_k": "int"
  }
  ```
- **출력**:
  ```json
  [
    {
      "chunk_id": "string",
      "doc_id": "string",
      "version": "string",
      "page_range": "string",
      "section_id": "string",
      "text": "string",
      "score": "float",
      "security_label": "string",
      "doc_field": "string",
      "doc_type": "string",
      "title": "string",
      "language": "string"
    }
  ]
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: query 빈 문자열
- **의존성**: UF-020
- **관련 REQ-ID**: REQ-006, REQ-016
- **테스트 포인트**:
  - 결과 수 ≤ top_k
  - 메타 필터 적용 시 해당 field만 반환
  - 빈 쿼리 시 E_VALIDATION
  - security_label_filter 미포함 문서 제외 확인
  - save/load 라운드트립 후 검색 결과 동일

---

## UF-022 — Citation 패키징

- **모듈**: `rag`
- **파일**: `src/defense_llm/rag/citation.py`
- **목적**: 검색 청크 목록으로부터 답변 근거 citation을 패키징한다.
- **핵심 함수**: `package_citations(chunks: List[dict]) -> List[dict]`
- **⚠️ 주의**: 입력 청크의 필수 필드는 `doc_id`, `version`, `text` (spec의 `doc_rev` → 실제 `version`)
- **입력** (청크 목록의 각 청크):
  ```json
  {
    "chunk_id": "string",
    "doc_id": "string",
    "version": "string",
    "page_range": "string",
    "section_id": "string",
    "title": "string (optional)",
    "text": "string"
  }
  ```
- **출력** (citation 목록):
  ```json
  [
    {
      "doc_id": "string",
      "doc_rev": "string",
      "page": "string",
      "section_id": "string",
      "title": "string",
      "snippet": "string (text[:300])",
      "snippet_hash": "sha256 string"
    }
  ]
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 청크에 `doc_id`, `version`, `text` 중 누락 필드 존재
- **의존성**: UF-021
- **관련 REQ-ID**: REQ-007
- **테스트 포인트**:
  - 각 citation에 doc_id, doc_rev, page, snippet_hash 포함
  - snippet_hash는 SHA-256 형식
  - 동일 텍스트 → 동일 snippet_hash
  - 필수 필드 누락 청크 → E_VALIDATION

---

## UF-023 — 응답 번역 처리기

- **모듈**: `agent`
- **파일**: `src/defense_llm/agent/executor.py` (Executor._run_plan 내 인라인)
- **목적**: 질의에 "한글" 또는 "한국어" 키워드가 포함된 경우, LLM 응답을 한국어로 번역한다.
- **트리거 조건**: `query_text`에 "한글" 또는 "한국어" 포함 AND citations 존재
- **처리 방식**: LLM을 번역 프롬프트로 2차 호출
- **예외/에러 코드**: 없음 (번역 실패 시 원문 유지)
- **의존성**: UF-031, UF-060
- **관련 REQ-ID**: REQ-009
- **테스트 포인트**:
  - 번역 요청 시 LLM chat() 2회 호출 확인
  - 번역 미요청 시 1회 호출

---

## UF-030 — 규칙 기반 Planner

- **모듈**: `agent`
- **파일**: `src/defense_llm/agent/planner_rules/classifier.py`, `plan_builder.py`
- **목적**: 입력 질의를 규칙(정규식)으로 분류하고 실행할 도구 플랜을 생성한다.
- **핵심 함수**: `classify_query(query, user_context) -> QueryType`, `build_plan(query_type, context) -> List[dict]`
- **QueryType enum**: `STRUCTURED_KB_QUERY | DOC_RAG_QUERY | MIXED_QUERY | SECURITY_RESTRICTED | UNKNOWN`
- **분류 우선순위**: SECURITY_RESTRICTED > (STRUCTURED & DOC) = MIXED > STRUCTURED > DOC > UNKNOWN
- **입력**:
  ```json
  {
    "query": "string",
    "user_context": { "role": "string", "clearance": "string" }
  }
  ```
- **출력**:
  ```json
  {
    "query_type": "QueryType",
    "tool_plan": [
      { "tool": "string", "params": {} }
    ]
  }
  ```
- **예외/에러 코드**: 없음 (UNKNOWN 반환)
- **의존성**: UF-001
- **관련 REQ-ID**: REQ-008
- **테스트 포인트**:
  - 키워드 기반 분류 정확도 (각 타입 최소 1 케이스)
  - 보안 트리거 키워드 시 SECURITY_RESTRICTED 반환
  - 빈 쿼리 → UNKNOWN
  - SECURITY_RESTRICTED → tool: security_refusal

---

## UF-031 — LLM Executor

- **모듈**: `agent`
- **파일**: `src/defense_llm/agent/executor.py`
- **목적**: Tool plan에 따라 도구를 순차 호출하고, 스키마 검증 및 응답 템플릿 적용 후 표준 응답을 생성한다. 모든 요청에 대해 감사 로그를 기록한다.
- **핵심 클래스**: `Executor(llm_adapter, index, db_path, audit_logger, model_version, index_version, db_schema_version, index_path=None)`
- **핵심 메서드**: `execute(tool_plan, user_context, request_id=None) -> dict`
- **처리 흐름**:
  1. 각 tool에 대해 `validate_tool_call()` 스키마 검증 (UF-032)
  2. `security_refusal` → PermissionError 발생
  3. `search_docs` → RBAC 검사 후 `DocumentIndex.search()` 실행
     - `online_mode=True` 시 `_fallback_web_search()` 추가 실행 (⚠️ 네트워크 필요)
  4. `query_structured_db` → SQLite platforms 테이블 키워드 검색
  5. `generate_answer` / `format_response` → 컨텍스트 수집 완료 후 일괄 처리
  6. `package_citations()` 호출 (UF-022)
  7. LLM으로 최종 답변 생성 (UF-060)
  8. `AuditLogger.write()` 호출 (UF-050) — 오류 응답도 기록
- **입력**:
  ```json
  {
    "tool_plan": [{ "tool": "string", "params": {} }],
    "user_context": { "role": "string", "clearance": "string", "user_id": "string" },
    "request_id": "uuid (optional)"
  }
  ```
- **출력**: 표준 응답 스키마 (REQ-018)
  ```json
  {
    "request_id": "uuid",
    "data": { "answer": "string" },
    "citations": [{ "doc_id": "...", "doc_rev": "...", "page": "...", "snippet_hash": "..." }],
    "security_label": "string",
    "version": { "model": "...", "index": "...", "db": "..." },
    "error": "string (optional)",
    "hash": "sha256 string"
  }
  ```
- **예외/에러 코드**:
  - `E_AUTH`: 권한 없음 (응답에 포함, 예외 발생하지 않음)
  - `E_VALIDATION`: 스키마 위반 (응답에 포함)
  - `E_INTERNAL`: 도구 실행 오류 (응답에 포함)
- **의존성**: UF-030, UF-032, UF-040, UF-022, UF-050, UF-060
- **관련 REQ-ID**: REQ-009, REQ-018
- **테스트 포인트**:
  - 정상 플랜 실행 시 표준 응답 반환
  - 스키마 위반 도구 호출 시 error=E_VALIDATION
  - security_refusal tool → error=E_AUTH
  - 감사 로그 항상 기록 (오류 시에도)

---

## UF-032 — Tool Schema 검증

- **모듈**: `agent`
- **파일**: `src/defense_llm/agent/tool_schemas.py`
- **목적**: 등록된 JSON Schema로 도구 호출 파라미터의 유효성을 검증한다.
- **핵심 함수**: `validate_tool_call(tool_name, params) -> dict`
- **등록된 툴**: `search_docs`, `query_structured_db`, `generate_answer`, `format_response`, `security_refusal`
- **`search_docs` 스키마** (실제 구현 기준):
  ```json
  {
    "required": ["query"],
    "properties": {
      "query": "str",
      "top_k": "int",
      "field_filter": "list",
      "security_label_filter": "list",
      "online_mode": "bool"
    }
  }
  ```
- **입력**:
  ```json
  { "tool_name": "string", "params": {} }
  ```
- **출력**:
  ```json
  { "valid": "bool", "errors": ["string"] }
  ```
- **예외/에러 코드**: 없음 (결과에 반영)
- **의존성**: 없음
- **관련 REQ-ID**: REQ-010
- **테스트 포인트**:
  - 올바른 파라미터 시 valid=True
  - 필수 필드 누락 시 valid=False + 에러 메시지
  - 타입 불일치 시 valid=False (예: top_k="three")
  - 미등록 tool_name 시 valid=False

---

## UF-040 — RBAC/ABAC 권한 검사

- **모듈**: `security`
- **파일**: `src/defense_llm/security/rbac.py`
- **목적**: 사용자 역할/허가등급과 리소스의 보안 라벨을 비교하여 접근 허용 여부를 결정한다.
- **핵심 함수**: `check_access(user, resource_security_labels, resource_field=None) -> dict`
- **보조 함수**: `filter_results_by_clearance(results, user) -> List[dict]` — 검색 후 필터링
- **허가등급 계층**: PUBLIC(0) < INTERNAL(1) < RESTRICTED(2) < SECRET(3)
- **역할별 필드 권한**:
  - `admin`: 전체 (`air, weapon, ground, sensor, comm`)
  - `analyst`: 전체
  - `air_analyst`: `air, sensor`
  - `weapon_analyst`: `weapon`
  - `ground_analyst`: `ground`
  - `comm_analyst`: `comm, sensor`
  - `guest`: `air` 만
- **입력**:
  ```json
  {
    "user": { "role": "string", "clearance": "PUBLIC|INTERNAL|RESTRICTED|SECRET" },
    "resource_security_labels": ["string"],
    "resource_field": "string (optional)"
  }
  ```
- **출력**:
  ```json
  { "allowed": "bool", "reason": "string" }
  ```
- **예외/에러 코드**: 없음 (결과에 반영)
- **의존성**: UF-001
- **관련 REQ-ID**: REQ-011
- **테스트 포인트**:
  - clearance < security_label 시 allowed=False
  - clearance >= security_label 시 allowed=True
  - 역할에 없는 field 접근 시 allowed=False

---

## UF-041 — 출력 마스킹

- **모듈**: `security`
- **파일**: `src/defense_llm/security/masking.py`
- **목적**: 응답 텍스트에서 민감 정보(좌표, 주파수, 시스템 식별자)를 정규식으로 `[REDACTED]`로 마스킹한다.
- **핵심 함수**: `mask_output(text, mask_rules=None) -> dict`
- **마스킹 규칙**:
  - `coordinates`: 위경도 좌표 (십진법/도분초 모두 지원, 위도/경도 한국어 표현 포함)
  - `frequency`: 주파수 값 (GHz, MHz, kHz, THz, Hz)
  - `sys_id`: 시스템 식별자 (`[A-Z]{2,4}-[0-9]{3,8}` 패턴)
- **입력**:
  ```json
  { "text": "string", "mask_rules": ["coordinates", "frequency", "sys_id"] }
  ```
- **출력**:
  ```json
  { "masked_text": "string", "masked_count": "int" }
  ```
- **예외/에러 코드**: 없음 (미등록 규칙은 무시)
- **의존성**: 없음
- **관련 REQ-ID**: REQ-012
- **테스트 포인트**:
  - 좌표 패턴 마스킹 확인
  - 주파수 값 마스킹 확인 (예: `9.75 GHz` → `[REDACTED]`)
  - sys_id 패턴 마스킹 확인 (예: `KF-21` → `[REDACTED]`)
  - 마스킹 불필요한 텍스트 원문 유지
  - masked_count 정확도 확인

---

## UF-042 — JWT 인증 (P0 추가)

- **모듈**: `security`
- **파일**: `src/defense_llm/security/auth.py`
- **목적**: HS256 JWT 토큰을 발급하고 검증한다. RBAC의 사용자 컨텍스트(role, clearance)를 토큰 클레임에서 추출한다.
- **핵심 클래스**: `JWTAuthManager(secret_key, algorithm="HS256", ttl_seconds=3600)`
- **핵심 함수**: `extract_user_context(token, auth_manager) -> dict`
- **토큰 페이로드 스키마**:
  ```json
  {
    "sub": "user_id",
    "role": "string",
    "clearance": "string",
    "jti": "uuid (중복방지)",
    "iat": "int (발급 시각)",
    "exp": "int (만료 시각)"
  }
  ```
- **보안 요구사항**: secret_key ≥ 32자 (환경변수 `DEFENSE_LLM_JWT_SECRET`)
- **입력** (issue_token):
  ```json
  { "user_id": "string", "role": "string", "clearance": "string" }
  ```
- **출력** (extract_user_context):
  ```json
  { "user_id": "string", "role": "string", "clearance": "string" }
  ```
- **예외/에러 코드**:
  - `E_AUTH`: 토큰 만료, 서명 불일치, 위변조
  - `E_VALIDATION`: secret_key 길이 부족 (< 32자)
- **의존성**: UF-040 (RBAC 통합)
- **관련 REQ-ID**: REQ-011
- **테스트 포인트**:
  - 정상 발급 → 검증 → 페이로드 일치
  - 만료된 토큰 → E_AUTH
  - 위변조 토큰 → E_AUTH
  - 잘못된 서명 키 → E_AUTH
  - 짧은 secret → E_VALIDATION
  - 동일 사용자 두 토큰의 jti 상이

---

## UF-050 — Audit 레코드 생성 및 저장

- **모듈**: `audit`
- **파일**: `src/defense_llm/audit/logger.py`, `src/defense_llm/audit/schema.py`
- **목적**: 각 요청의 감사 정보를 SQLite audit_log 테이블에 append-only로 저장한다.
- **핵심 클래스**: `AuditLogger(db_path: str)`
- **주요 메서드**:
  - `write(request_id, user_id, query, model_version, index_version, citations, response_hash, error_code=None, timestamp=None) -> dict`
  - `fetch(audit_id) -> dict`
  - `fetch_by_request_id(request_id) -> dict`
- **입력** (write):
  ```json
  {
    "request_id": "uuid",
    "user_id": "string",
    "query": "string",
    "model_version": "string",
    "index_version": "string",
    "citations": [{}],
    "response_hash": "sha256 string",
    "error_code": "string (optional)",
    "timestamp": "ISO8601 string (optional)"
  }
  ```
- **출력** (write):
  ```json
  { "saved": true, "audit_id": "uuid" }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: request_id, model_version, index_version, response_hash 중 누락
  - `E_INTERNAL`: SQLite 쓰기 실패
- **의존성**: UF-010
- **관련 REQ-ID**: REQ-013
- **테스트 포인트**:
  - 감사 레코드 저장 후 audit_id로 조회 성공
  - fetch_by_request_id로 조회 성공
  - 필수 필드 누락 시 E_VALIDATION
  - timestamp 미제공 시 UTC 현재 시각 자동 설정

---

## UF-060 — LLM 어댑터 인터페이스 + Mock

- **모듈**: `serving`
- **파일**: `src/defense_llm/serving/adapter.py`, `src/defense_llm/serving/mock_llm.py`
- **목적**: LLM 호출을 추상화하는 어댑터 인터페이스와 테스트용 결정론적 mock 구현을 제공한다.
- **추상 클래스**: `AbstractLLMAdapter` — `chat(messages, max_tokens, temperature) -> dict` 필수 구현
- **Mock 클래스**: `MockLLMAdapter(fixed_response, response_fn=None, model="mock-llm-0.0")`
  - `fixed_response`: 모든 호출에 고정 응답 반환
  - `response_fn`: callable(messages) → str (동적 응답)
  - `call_count` property: 호출 횟수 추적 (테스트 assertion용)
- **입력**:
  ```json
  {
    "messages": [{ "role": "system|user|assistant", "content": "string" }],
    "max_tokens": "int",
    "temperature": "float (optional)"
  }
  ```
- **출력**:
  ```json
  {
    "content": "string",
    "model": "string",
    "usage": { "prompt_tokens": "int", "completion_tokens": "int" }
  }
  ```
- **예외/에러 코드**:
  - `E_INTERNAL`: 어댑터 호출 실패
- **의존성**: UF-001
- **관련 REQ-ID**: REQ-014, REQ-017
- **테스트 포인트**:
  - Mock 어댑터로 고정 응답 반환 확인
  - response_fn으로 동적 응답 확인
  - call_count 증가 확인
  - AbstractLLMAdapter 구현 확인 (isinstance)

---

## UF-061 — Embedding 추상화 + 구현 (P0 추가)

- **모듈**: `rag`
- **파일**: `src/defense_llm/rag/embedder.py`
- **목적**: 텍스트를 L2-정규화된 float32 벡터로 인코딩하는 추상 인터페이스와 두 가지 구현을 제공한다.
- **추상 클래스**: `AbstractEmbedder` — `encode(texts) -> np.ndarray`, `dim` property
- **구현체**:
  - `TFIDFEmbedder(vocab_size=1024)`: 오프라인 테스트용 TF-IDF 벡터 (모델 불필요)
  - `Qwen25Embedder(model_id, device, batch_size, max_length, preload)`: Qwen2.5 last-hidden-state mean-pool (프로덕션)
- **입력** (encode):
  ```json
  { "texts": ["string"] }
  ```
- **출력** (encode):
  - `numpy.ndarray (N, dim)`, dtype=float32, L2-정규화된 행렬
- **예외/에러 코드**:
  - `E_INTERNAL`: 모델 로딩 실패 (Qwen25Embedder)
- **의존성**: UF-001 (설정), numpy
- **관련 REQ-ID**: REQ-006, REQ-016
- **테스트 포인트**:
  - TFIDFEmbedder — AbstractEmbedder 인터페이스 구현 확인
  - encode 출력 shape (N, vocab_size), dtype float32
  - L2 정규화 확인 (norm ≈ 1.0)
  - 동일 텍스트 → 동일 벡터 (결정론적)
  - auto-fit (explicit fit 없이 encode 호출)

---

## UF-062 — Qwen2.5 프로덕션 어댑터 (P0 추가)

- **모듈**: `serving`
- **파일**: `src/defense_llm/serving/qwen_adapter.py`
- **목적**: HuggingFace transformers를 통해 Qwen2.5-1.5B-Instruct 모델을 로딩하고 채팅 완성을 수행한다. 더 큰 모델(7B/14B/32B)로의 업그레이드는 `model_id` 변경만으로 가능하다.
- **핵심 클래스**: `Qwen25Adapter(model_id, device_map="auto", torch_dtype="auto", max_new_tokens_default=512, temperature_default=0.1, preload=False)`
- **특징**:
  - 지연 로딩 (Lazy loading): 첫 번째 `chat()` 호출 시 모델 로드
  - `device_map="auto"`: GPU 자동 배치
  - `unload()` 메서드: GPU 메모리 해제
- **입력**:
  ```json
  {
    "messages": [{ "role": "system|user|assistant", "content": "string" }],
    "max_tokens": "int (0=default 사용)",
    "temperature": "float (< 0 = default 사용)"
  }
  ```
- **출력**:
  ```json
  {
    "content": "string",
    "model": "model_id string",
    "usage": { "prompt_tokens": "int", "completion_tokens": "int" }
  }
  ```
- **예외/에러 코드**:
  - `E_INTERNAL`: 모델 로딩 실패
- **의존성**: UF-001, transformers, torch
- **관련 REQ-ID**: REQ-014, REQ-017
- **테스트 포인트**:
  - AbstractLLMAdapter 구현 확인 (인터페이스 계약)
  - model_name property 반환값 확인
  - 단위 테스트: 모델 로딩은 mock으로 대체

---

## UF 의존성 요약

```
UF-001 (config)
  └─ UF-010 (db init)
       ├─ UF-011 (doc meta)
       │    └─ UF-020 (chunking)
       │         └─ UF-021 (hybrid search)  ←── UF-061 (embedder, optional)
       │              └─ UF-022 (citation)
       └─ UF-050 (audit)
UF-030 (planner) ──── UF-040 (rbac)
  └─ UF-031 (executor) ──── UF-032 (tool schema)
                       └─── UF-023 (translation, inline)
UF-041 (masking)  [독립]
UF-042 (jwt auth) [독립, UF-040 통합]
UF-060 (llm adapter mock)  [UF-001 의존]
UF-062 (qwen adapter)      [UF-001 의존]
UF-070 (eval)     [UF-030, UF-031, UF-060 의존]
```

## UF 전체 목록 요약

| UF-ID | 모듈 | 파일 | 상태 |
|-------|------|------|------|
| UF-001 | config | settings.py | ✅ 완료 |
| UF-010 | knowledge | db_schema.py | ✅ 완료 |
| UF-011 | knowledge | document_meta.py | ✅ 완료 |
| UF-012 | knowledge | glossary.py | ✅ 완료 |
| UF-020 | rag | chunker.py | ✅ 완료 (파라미터 `version` 주의) |
| UF-021 | rag | retriever.py + indexer.py | ✅ 완료 (embedder 주입, 영속성 지원) |
| UF-022 | rag | citation.py | ✅ 완료 (입력 필드 `version` 주의) |
| UF-023 | agent | executor.py (인라인) | ✅ 완료 (번역 처리기) |
| UF-030 | agent | classifier.py + plan_builder.py | ✅ 완료 |
| UF-031 | agent | executor.py | ✅ 완료 |
| UF-032 | agent | tool_schemas.py | ✅ 완료 (online_mode 필드 추가) |
| UF-040 | security | rbac.py | ✅ 완료 |
| UF-041 | security | masking.py | ✅ 완료 |
| UF-042 | security | auth.py | ✅ 완료 (P0 추가) |
| UF-050 | audit | logger.py + schema.py | ✅ 완료 |
| UF-060 | serving | adapter.py + mock_llm.py | ✅ 완료 |
| UF-061 | rag | embedder.py | ✅ 완료 (P0 추가) |
| UF-062 | serving | qwen_adapter.py | ✅ 완료 (P0 추가) |
| UF-070 | eval | runner.py | ✅ 완료 |
