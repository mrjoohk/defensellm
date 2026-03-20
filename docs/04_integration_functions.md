# 04_integration_functions.md — 통합기능(IF) 정의

> UF를 조합하여 사용자 가치 단위의 시나리오를 정의합니다.
> **최종 갱신**: 2026-03-18 — 실제 구현 소스코드 기준으로 전면 동기화

---

## IF-001 — 문서 업로드 → 인덱싱 → 질의 → 근거 인용 답변

- **시나리오**:
  사용자가 방산 문서(더미 텍스트)를 메타데이터와 함께 업로드하면, 시스템은 문서를 청킹·인덱싱하고 이후 사용자의 자연어 질의에 대해 관련 청크를 검색하여 Citation이 포함된 표준 응답을 반환한다.

- **사용 UF 목록**: UF-011, UF-020, UF-021, UF-022, UF-030, UF-031, UF-050, UF-060

- **테스트 파일**: `tests/integration/test_document_pipeline.py`
- **픽스처**: `tests/fixtures/dummy_doc_air.txt`

- **입력**:
  ```json
  {
    "document": {
      "doc_id": "DOC-001",
      "doc_rev": "v1.0",
      "title": "KF-21 운용 교범",
      "field": "air",
      "security_label": "INTERNAL",
      "text": "... (더미 텍스트) ..."
    },
    "query": {
      "text": "KF-21의 최대 순항 고도는?",
      "user": { "role": "analyst", "clearance": "INTERNAL" }
    }
  }
  ```

- **출력**: 표준 응답 스키마
  ```json
  {
    "request_id": "uuid",
    "data": { "answer": "string" },
    "citations": [
      {
        "doc_id": "DOC-001",
        "doc_rev": "v1.0",
        "page": "string",
        "section_id": "sec-NNNN",
        "title": "string",
        "snippet": "string",
        "snippet_hash": "sha256"
      }
    ],
    "security_label": "INTERNAL",
    "version": { "model": "...", "index": "...", "db": "..." },
    "hash": "sha256"
  }
  ```

- **성공 기준**:
  1. 응답에 citations 최소 1개 포함
  2. 각 citation에 doc_id, doc_rev, page(또는 section_id), snippet_hash 포함
  3. 표준 응답 스키마 6개 필드 모두 존재 (request_id, data, citations, security_label, version, hash)
  4. 감사 로그에 request_id 기록됨

- **보안/감사 조건**:
  - 업로드 문서의 security_label과 사용자 clearance 일치 확인
  - 감사 로그에 모델 버전, 인덱스 버전, citation 목록 저장

- **구현 주의사항**:
  - `chunk_document()` 파라미터: `version` (not `doc_rev`)
  - `package_citations()` 입력 청크 필드: `version` → 출력 citation 필드: `doc_rev`

- **관련 REQ-ID**: REQ-003, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-013, REQ-016, REQ-018

---

## IF-002 — 정형 DB 제원 조회 → 제약/호환성 → 근거 포함 응답

- **시나리오**:
  사용자가 특정 플랫폼(예: 더미 전투기 모델)의 무장 호환성을 질의하면, 시스템은 정형 DB에서 제원을 조회하고 Planner가 STRUCTURED_KB_QUERY로 분류한 후 Executor가 DB 결과와 Citation을 포함한 응답을 생성한다.

- **사용 UF 목록**: UF-010, UF-011, UF-030, UF-031, UF-022, UF-050, UF-060

- **테스트 파일**: `tests/integration/test_kb_query.py`

- **입력**:
  ```json
  {
    "query": {
      "text": "DUMMY-A1 플랫폼의 무장 탑재 제한 중량은?",
      "user": { "role": "analyst", "clearance": "INTERNAL" }
    }
  }
  ```

- **출력**: 표준 응답 스키마 (data에 제원 정보, citations에 DB 출처)

- **성공 기준**:
  1. Planner가 STRUCTURED_KB_QUERY 또는 MIXED_QUERY로 분류
  2. 응답 data에 수치 정보 포함
  3. citations에 출처(DB 레코드 또는 문서) 포함
  4. 감사 로그 기록

- **보안/감사 조건**: 권한 없는 사용자 접근 시 E_AUTH

- **관련 REQ-ID**: REQ-002, REQ-003, REQ-007, REQ-008, REQ-009, REQ-013, REQ-018

---

## IF-003 — 권한 없는 사용자의 기밀 문서 검색 → 결과 0건/거절

- **시나리오**:
  clearance=PUBLIC 사용자가 security_label=SECRET 문서의 내용을 질의하면, 검색 단계 또는 접근 제어 단계에서 차단되어 결과 0건 또는 명시적 거절 메시지가 반환된다. 출력 마스킹도 적용된다.

- **사용 UF 목록**: UF-021, UF-040, UF-041, UF-031, UF-050

- **테스트 파일**: `tests/integration/test_security_access.py`
- **픽스처**: `tests/fixtures/dummy_doc_secret.txt`

- **입력**:
  ```json
  {
    "query": {
      "text": "기밀 시스템 식별자 조회",
      "user": { "role": "guest", "clearance": "PUBLIC" }
    },
    "indexed_docs_include_secret": true
  }
  ```

- **출력**:
  ```json
  {
    "request_id": "uuid",
    "data": { "answer": "접근 권한이 없습니다." },
    "citations": [],
    "security_label": "PUBLIC",
    "error": "E_AUTH",
    "version": {},
    "hash": "sha256"
  }
  ```

- **성공 기준**:
  1. citations 0건
  2. 응답에 E_AUTH 또는 "권한 없음" 표시
  3. SECRET 라벨 문서의 내용이 응답 text에 노출되지 않음
  4. 감사 로그에 거절 사실 기록

- **보안/감사 조건**:
  - 검색 전(pre-search) 필터: `security_label_filter` 파라미터 제한
  - 검색 후(post-search) 필터: `filter_results_by_clearance()` (UF-040)
  - 출력 마스킹 적용 (UF-041)

- **구현 메커니즘**:
  - `Executor._run_plan()` 내 `check_access()` 호출 → `PermissionError` 발생
  - `execute()` 에서 PermissionError 캐치 → `error=E_AUTH` 응답 구성
  - `AuditLogger.write(error_code="E_AUTH")` 기록

- **관련 REQ-ID**: REQ-006, REQ-011, REQ-012, REQ-013

---

## IF-004 — 감사 로그에 request_id / 모델버전 / 인덱스버전 / citation 저장 확인

- **시나리오**:
  임의의 정상 질의가 처리된 후, 감사 DB를 조회하면 해당 request_id에 대해 모델 버전, 인덱스 버전, citation 목록, 응답 해시가 모두 저장되어 있음을 확인한다.

- **사용 UF 목록**: UF-031, UF-050

- **테스트 파일**: `tests/integration/test_audit_logging.py`

- **입력**: IF-001 또는 IF-002와 동일한 정상 질의

- **출력**:
  ```json
  {
    "audit_record": {
      "audit_id": "uuid",
      "request_id": "uuid",
      "user_id": "string",
      "model_version": "qwen2.5-1.5b-instruct",
      "index_version": "idx-YYYYMMDD-hhmm",
      "citations": [{ "doc_id": "...", "snippet_hash": "..." }],
      "response_hash": "sha256",
      "timestamp": "ISO8601",
      "error_code": "string | null"
    }
  }
  ```

- **성공 기준**:
  1. 감사 레코드에 6개 필수 필드 모두 존재 (request_id, model_version, index_version, citations, response_hash, timestamp)
  2. request_id가 응답과 감사 레코드에서 동일
  3. response_hash가 실제 응답의 SHA-256과 일치
  4. timestamp가 ISO8601 형식

- **보안/감사 조건**: 감사 레코드는 변경 불가 (append-only SQLite INSERT)

- **구현 주의사항**:
  - `AuditLogger.fetch_by_request_id(request_id)` 사용하여 조회
  - `citations` 필드는 JSON 직렬화 후 저장, 조회 시 역직렬화

- **관련 REQ-ID**: REQ-013, REQ-018

---

## IF-005 — 툴 호출 스키마 위반 → Executor 실패 처리 → 안전 응답

- **시나리오**:
  Planner가 생성한 tool_plan에 스키마를 위반하는 파라미터가 포함된 경우, Executor는 실행을 중단하고 `E_VALIDATION`을 포함한 안전 응답을 반환한다. 시스템은 부분 실행 결과를 노출하지 않는다.

- **사용 UF 목록**: UF-031, UF-032, UF-050

- **테스트 파일**: `tests/integration/test_tool_schema_violation.py`

- **입력**:
  ```json
  {
    "tool_plan": [
      { "tool": "search_docs", "params": { "typo_field": "invalid" } }
    ],
    "user": { "role": "analyst", "clearance": "INTERNAL" }
  }
  ```

- **출력**:
  ```json
  {
    "request_id": "uuid",
    "data": { "answer": "요청 처리 중 오류가 발생했습니다." },
    "citations": [],
    "security_label": "INTERNAL",
    "error": "E_VALIDATION",
    "version": {},
    "hash": "sha256"
  }
  ```

- **성공 기준**:
  1. 응답에 `error: E_VALIDATION` 포함
  2. citations 0건 (부분 결과 노출 없음)
  3. 감사 로그에 실패 기록
  4. 시스템이 중단되지 않고 안전 응답 반환

- **보안/감사 조건**:
  - 오류 응답도 감사 로그 기록 (`AuditLogger.write(error_code="E_VALIDATION")`)
  - 스키마 위반 즉시 실행 중단 (첫 번째 위반 tool에서 raise ValueError)

- **구현 메커니즘**:
  - `validate_tool_call(tool, params)` → `valid=False` → `raise ValueError`
  - `execute()` 에서 ValueError 캐치 → `error=E_VALIDATION` 응답
  - `hash` 필드는 오류 응답에도 항상 포함

- **관련 REQ-ID**: REQ-009, REQ-010, REQ-013

---

## IF 사용 UF 매트릭스

| IF-ID  | UF-011 | UF-020 | UF-021 | UF-022 | UF-023 | UF-030 | UF-031 | UF-032 | UF-040 | UF-041 | UF-050 | UF-060 |
|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| IF-001 | ✓      | ✓      | ✓      | ✓      |        | ✓      | ✓      |        |        |        | ✓      | ✓      |
| IF-002 | ✓      |        | ✓      | ✓      |        | ✓      | ✓      |        |        |        | ✓      | ✓      |
| IF-003 |        |        | ✓      |        |        | ✓      | ✓      |        | ✓      | ✓      | ✓      |        |
| IF-004 |        |        |        |        |        |        | ✓      |        |        |        | ✓      |        |
| IF-005 |        |        |        |        |        |        | ✓      | ✓      |        |        | ✓      |        |

## 주요 데이터 흐름 요약

```
[IF-001 Document Pipeline]
register_document() → chunk_document() → DocumentIndex.add_chunks()
  → classify_query() → build_plan()
  → Executor.execute()
      → validate_tool_call() [UF-032]
      → check_access() [UF-040]
      → DocumentIndex.search() [UF-021]
      → package_citations() [UF-022]
      → LLM.chat() [UF-060]
      → AuditLogger.write() [UF-050]
  → standard response schema

[IF-003 Security Block]
Executor.execute()
  → validate_tool_call()
  → check_access() → allowed=False → raise PermissionError
  → error=E_AUTH → AuditLogger.write(error_code="E_AUTH")
  → citations=[] 응답

[IF-005 Schema Violation]
Executor.execute()
  → validate_tool_call() → valid=False → raise ValueError
  → error=E_VALIDATION → AuditLogger.write(error_code="E_VALIDATION")
  → citations=[] 응답
```
