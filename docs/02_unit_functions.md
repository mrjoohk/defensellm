# 02_unit_functions.md — 단위기능(UF) 정의

> 각 UF는 단일 모듈에서 독립적으로 테스트 가능한 최소 기능 단위입니다.

---

## UF-001 — 설정 로딩 및 검증

- **모듈**: `config`
- **목적**: YAML 파일 또는 환경변수에서 설정을 로딩하고 필수 항목을 검증한다.
- **입력**:
  ```json
  { "config_path": "string (optional)", "env_override": "bool" }
  ```
- **출력**:
  ```json
  {
    "model_name": "string",
    "db_path": "string",
    "index_path": "string",
    "security_level": "string",
    "log_path": "string"
  }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 필수 키 누락 또는 타입 오류
- **의존성**: 없음
- **관련 REQ-ID**: REQ-001
- **테스트 포인트**:
  - 정상 설정 파일 로딩 성공
  - 필수 키 누락 시 예외 발생

---

## UF-010 — 정형 DB 스키마 초기화

- **모듈**: `knowledge`
- **목적**: SQLite DB에 플랫폼/무장/시스템 테이블과 schema_version 테이블을 생성한다.
- **입력**:
  ```json
  { "db_path": "string", "schema_version": "string" }
  ```
- **출력**:
  ```json
  { "success": true, "tables_created": ["platforms", "weapons", "constraints", "schema_version"] }
  ```
- **예외/에러 코드**:
  - `E_INTERNAL`: DB 연결 실패 또는 SQL 오류
- **의존성**: UF-001
- **관련 REQ-ID**: REQ-002
- **테스트 포인트**:
  - 테이블 생성 확인
  - 중복 초기화 시 오류 없이 처리(idempotent)

---

## UF-011 — 문서 메타데이터 검증 및 등록

- **모듈**: `knowledge`
- **목적**: 문서 업로드 시 필수 메타데이터를 검증하고 DB에 등록한다.
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

---

## UF-012 — Glossary 매핑

- **모듈**: `knowledge`
- **목적**: 방산 약어/용어를 정규화된 표준 용어와 매핑한다.
- **입력**:
  ```json
  { "term": "string" }
  ```
- **출력**:
  ```json
  { "term": "string", "definition": "string | null", "found": "bool" }
  ```
- **예외/에러 코드**: 없음 (미등록 시 `found=false` 반환)
- **의존성**: 없음(인메모리 딕셔너리 또는 DB)
- **관련 REQ-ID**: REQ-004
- **테스트 포인트**:
  - 등록된 약어 조회 시 정의 반환
  - 미등록 약어 조회 시 `found=false`

---

## UF-020 — 문서 청킹 및 인덱싱

- **모듈**: `rag`
- **목적**: 문서 텍스트를 섹션/단락 단위로 청킹하고 BM25 및 벡터 인덱스에 등록한다.
- **입력**:
  ```json
  {
    "doc_id": "string",
    "doc_rev": "string",
    "text": "string",
    "max_tokens": "int",
    "overlap": "int",
    "security_label": "string",
    "field": "string"
  }
  ```
- **출력**:
  ```json
  {
    "chunks": [
      {
        "chunk_id": "string",
        "doc_id": "string",
        "doc_rev": "string",
        "page": "int",
        "section_id": "string",
        "text": "string",
        "token_count": "int"
      }
    ],
    "indexed_count": "int"
  }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 빈 텍스트 또는 잘못된 파라미터
  - `E_INTERNAL`: 인덱스 쓰기 실패
- **의존성**: UF-011
- **관련 REQ-ID**: REQ-005, REQ-016
- **테스트 포인트**:
  - 청크 수 ≥ 1
  - 각 청크에 doc_id, page 포함
  - 최대 토큰 수 초과 청크 없음

---

## UF-021 — 하이브리드 검색(BM25 + Vector)

- **모듈**: `rag`
- **목적**: 질의에 대해 BM25와 벡터 유사도 검색을 병행하고 메타 필터를 적용하여 결과를 반환한다.
- **입력**:
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
      "doc_rev": "string",
      "page": "int",
      "section_id": "string",
      "text": "string",
      "score": "float"
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

---

## UF-022 — Citation 패키징

- **모듈**: `rag`
- **목적**: 검색 청크 목록으로부터 답변 근거 citation을 패키징한다.
- **입력**:
  ```json
  [
    {
      "chunk_id": "string",
      "doc_id": "string",
      "doc_rev": "string",
      "page": "int",
      "section_id": "string",
      "text": "string"
    }
  ]
  ```
- **출력**:
  ```json
  [
    {
      "doc_id": "string",
      "doc_rev": "string",
      "page": "int",
      "section_id": "string",
      "snippet": "string",
      "snippet_hash": "sha256 string"
    }
  ]
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: 청크에 필수 필드 누락
- **의존성**: UF-021
- **관련 REQ-ID**: REQ-007
- **테스트 포인트**:
  - 각 citation에 doc_id, doc_rev, page, snippet_hash 포함
  - snippet_hash는 SHA-256 형식

---

## UF-030 — 규칙 기반 Planner

- **모듈**: `agent`
- **목적**: 입력 질의를 규칙으로 분류하고 실행할 도구 플랜을 생성한다.
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
    "query_type": "STRUCTURED_KB_QUERY|DOC_RAG_QUERY|MIXED_QUERY|SECURITY_RESTRICTED|UNKNOWN",
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

---

## UF-031 — LLM Executor

- **모듈**: `agent`
- **목적**: Tool plan에 따라 도구를 순차 호출하고, 스키마 검증 및 응답 템플릿 적용 후 표준 응답을 생성한다.
- **입력**:
  ```json
  {
    "tool_plan": [{ "tool": "string", "params": {} }],
    "user_context": { "role": "string", "clearance": "string" },
    "request_id": "uuid"
  }
  ```
- **출력**: 표준 응답 스키마(REQ-018 참고)
- **예외/에러 코드**:
  - `E_AUTH`: 권한 없음
  - `E_VALIDATION`: 스키마 위반
  - `E_INTERNAL`: 도구 실행 오류
- **의존성**: UF-030, UF-032, UF-040
- **관련 REQ-ID**: REQ-009, REQ-018
- **테스트 포인트**:
  - 정상 플랜 실행 시 표준 응답 반환
  - 스키마 위반 도구 호출 시 E_VALIDATION

---

## UF-032 — Tool Schema 검증

- **모듈**: `agent`
- **목적**: JSON Schema를 이용해 도구 호출 파라미터의 유효성을 검증한다.
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

---

## UF-040 — RBAC/ABAC 권한 검사

- **모듈**: `security`
- **목적**: 사용자 역할/허가등급과 리소스의 보안 라벨을 비교하여 접근 허용 여부를 결정한다.
- **입력**:
  ```json
  {
    "user": { "role": "string", "clearance": "PUBLIC|INTERNAL|RESTRICTED|SECRET" },
    "resource": { "security_label": "string", "field": "string" }
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

---

## UF-041 — 출력 마스킹

- **모듈**: `security`
- **목적**: 응답 텍스트에서 민감 정보(좌표, 주파수, 시스템 식별자)를 정규식으로 마스킹한다.
- **입력**:
  ```json
  { "text": "string", "mask_rules": ["coordinates", "frequency", "sys_id"] }
  ```
- **출력**:
  ```json
  { "masked_text": "string", "masked_count": "int" }
  ```
- **예외/에러 코드**: 없음
- **의존성**: 없음
- **관련 REQ-ID**: REQ-012
- **테스트 포인트**:
  - 좌표 패턴 마스킹 확인
  - 주파수 값 마스킹 확인
  - 마스킹 불필요한 텍스트 원문 유지

---

## UF-050 — Audit 레코드 생성 및 저장

- **모듈**: `audit`
- **목적**: 각 요청의 감사 정보를 DB(또는 파일)에 저장한다.
- **입력**:
  ```json
  {
    "request_id": "uuid",
    "user_id": "string",
    "query": "string",
    "model_version": "string",
    "index_version": "string",
    "citations": [{}],
    "response_hash": "sha256 string",
    "timestamp": "ISO8601 string"
  }
  ```
- **출력**:
  ```json
  { "saved": true, "audit_id": "string" }
  ```
- **예외/에러 코드**:
  - `E_INTERNAL`: 저장 실패
- **의존성**: UF-010
- **관련 REQ-ID**: REQ-013
- **테스트 포인트**:
  - 감사 레코드 저장 후 조회 성공
  - 필수 필드 누락 시 저장 실패

---

## UF-060 — LLM 어댑터 인터페이스 + Mock

- **모듈**: `serving`
- **목적**: LLM 호출을 추상화하는 어댑터 인터페이스와 테스트용 mock 구현을 제공한다.
- **입력**:
  ```json
  {
    "messages": [{ "role": "system|user|assistant", "content": "string" }],
    "model": "string",
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
  - 어댑터 교체(mock → real) 시 인터페이스 동일성 확인

---

## UF-070 — Eval Runner

- **모듈**: `eval`
- **목적**: 정해진 QA 샘플을 실행하고 결과 JSON 리포트를 생성한다.
- **입력**:
  ```json
  {
    "samples": [
      {
        "id": "string",
        "question": "string",
        "expected_answer_keywords": ["string"],
        "expected_citation_doc_ids": ["string"]
      }
    ],
    "system_config": {}
  }
  ```
- **출력**:
  ```json
  {
    "total": "int",
    "passed": "int",
    "failed": "int",
    "pass_rate": "float",
    "results": [
      {
        "id": "string",
        "pass": "bool",
        "citation_match": "bool",
        "details": "string"
      }
    ]
  }
  ```
- **예외/에러 코드**:
  - `E_VALIDATION`: samples 빈 목록
- **의존성**: UF-030, UF-031, UF-060
- **관련 REQ-ID**: REQ-015
- **테스트 포인트**:
  - 샘플 실행 후 리포트 JSON 생성
  - pass_rate 계산 정확성

---

## UF 의존성 요약

```
UF-001 (config)
  └─ UF-010 (db init)
       └─ UF-011 (doc meta)
            └─ UF-020 (chunking)
                 └─ UF-021 (hybrid search)
                      └─ UF-022 (citation)
UF-030 (planner) ──── UF-040 (rbac)
  └─ UF-031 (executor) ──── UF-032 (tool schema)
UF-041 (masking)  [독립]
UF-050 (audit)    [UF-010 의존]
UF-060 (llm adapter) [UF-001 의존]
UF-070 (eval)     [UF-030, UF-031, UF-060 의존]
```
