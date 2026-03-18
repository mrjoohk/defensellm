# 03_unit_test_coverage.md — UF 단위 테스트 및 커버리지 계획

> **최종 갱신**: 2026-03-18 — 실제 구현 소스코드 기준으로 전면 동기화

---

## 커버리지 목표

| 모듈 카테고리 | 목표 라인 커버리지 |
|--------------|-------------------|
| 일반 모듈 (config, knowledge, rag, agent, eval) | ≥ 70% |
| 보안/감사/스키마 (security, audit, tool_schemas) | ≥ 80% |

---

## UF-001 — 설정 로딩 테스트

**파일**: `tests/unit/test_config.py`

| TC-ID     | 테스트 케이스         | 입력                            | 기대 결과                      |
|-----------|----------------------|--------------------------------|-------------------------------|
| TC-001-01 | 정상 설정 로딩        | 유효한 config dict             | AppConfig 객체 반환            |
| TC-001-02 | 필수 키 누락          | model_name 없는 config         | ValueError(E_VALIDATION)       |
| TC-001-03 | 환경변수 오버라이드   | DEFENSE_LLM_MODEL_NAME 설정    | 환경변수 값 우선 적용           |
| TC-001-04 | 잘못된 security_level | security_level="TOPSECRET"     | ValueError(E_VALIDATION)       |

---

## UF-010 — DB 스키마 초기화 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력                        | 기대 결과                          |
|-----------|--------------------------|-----------------------------|-----------------------------------|
| TC-010-01 | 정상 DB 초기화           | 임시 경로                   | documents, platforms, audit_log 등 테이블 생성 확인 |
| TC-010-02 | 중복 초기화(idempotent)  | 이미 초기화된 DB 경로       | 오류 없이 완료                     |

---

## UF-011 — 문서 메타 등록 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력                              | 기대 결과                |
|-----------|--------------------------|-----------------------------------|--------------------------|
| TC-011-01 | 정상 메타 등록           | 유효한 메타 딕셔너리              | registered=True          |
| TC-011-02 | 필수 필드 누락           | field 없는 딕셔너리               | ValueError(E_VALIDATION) |
| TC-011-03 | 잘못된 security_label    | security_label="TOPSECRET"        | ValueError(E_VALIDATION) |
| TC-011-04 | 중복 doc_id+rev          | 동일 doc_id, doc_rev 재등록       | ValueError(E_CONFLICT)   |

---

## UF-012 — Glossary 매핑 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력              | 기대 결과               |
|-----------|--------------------------|-------------------|-------------------------|
| TC-012-01 | 등록된 약어 조회         | "KF-21"           | found=True, 정의 반환   |
| TC-012-02 | 미등록 약어 조회         | "XYZ-99"          | found=False             |
| TC-012-03 | normalize_text 약어 치환 | "KF-21 운용"      | 풀네임 포함 텍스트 반환  |

---

## UF-020 — 청킹/인덱싱 테스트

**파일**: `tests/unit/test_rag.py`

> ⚠️ 실제 파라미터명: `version` (spec의 `doc_rev` 아님)

| TC-ID     | 테스트 케이스              | 입력                               | 기대 결과                          |
|-----------|---------------------------|------------------------------------|-----------------------------------|
| TC-020-01 | 정상 청킹                  | 500자 텍스트, max_tokens=100       | 청크 수 ≥ 1, 각 청크에 doc_id     |
| TC-020-02 | 빈 텍스트 입력             | text=""                            | ValueError(E_VALIDATION)           |
| TC-020-03 | 청크 토큰 수 초과 없음     | max_tokens=50 설정                 | 모든 청크 token_count ≤ 50         |
| TC-020-04 | Markdown 헤딩 section_path | "# H1\n## H2\ncontent"            | section_path="H1 > H2" 포함        |
| TC-020-05 | [PAGE N] 마커 인식         | "[PAGE 3] 텍스트"                  | chunk.page_range="3"               |

---

## UF-021 — 하이브리드 검색 테스트

**파일**: `tests/unit/test_rag.py`

| TC-ID     | 테스트 케이스            | 입력                                  | 기대 결과                          |
|-----------|--------------------------|---------------------------------------|-----------------------------------|
| TC-021-01 | 정상 검색 결과 반환      | query="전투기 무장", top_k=3          | 결과 수 ≤ 3                       |
| TC-021-02 | 필드 필터 적용           | field_filter=["air"]                  | 반환 결과 모두 doc_field=air       |
| TC-021-03 | 빈 쿼리                  | query=""                              | ValueError(E_VALIDATION)           |
| TC-021-04 | 보안 라벨 필터           | security_label_filter=["PUBLIC"]      | SECRET 라벨 결과 미포함            |
| TC-021-05 | embedder 없이 레거시 검색 | DocumentIndex(embedder=None)          | SimpleVectorIndex fallback 동작   |

---

## UF-022 — Citation 패키징 테스트

**파일**: `tests/unit/test_rag.py`

> ⚠️ 입력 청크 필수 필드: `doc_id`, `version`, `text` (spec의 `doc_rev` → `version`)

| TC-ID     | 테스트 케이스             | 입력                                  | 기대 결과                              |
|-----------|--------------------------|---------------------------------------|----------------------------------------|
| TC-022-01 | 정상 citation 생성       | 유효한 청크 목록                      | 각 citation에 doc_id, doc_rev, page, snippet_hash 포함 |
| TC-022-02 | snippet_hash 검증        | 동일 텍스트 두 번 패키징              | 동일 hash 값                           |
| TC-022-03 | 필수 필드 누락 청크      | version 없는 청크 입력                | ValueError(E_VALIDATION)               |
| TC-022-04 | snippet 길이 제한        | 500자 텍스트 청크                     | snippet ≤ 300자                        |

---

## UF-023 — 응답 번역 처리기 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                          | 기대 결과                       |
|-----------|---------------------------|-----------------------------------------------|--------------------------------|
| TC-023-01 | 번역 요청 시 LLM 2회 호출 | query="한글로 답해줘", citations 있음          | mock_llm.call_count == 2       |
| TC-023-02 | 번역 미요청 시 1회 호출   | 일반 query, citations 있음                    | mock_llm.call_count == 1       |

---

## UF-030 — 규칙 기반 Planner 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                    |
|-----------|---------------------------|---------------------------------------|------------------------------|
| TC-030-01 | STRUCTURED_KB_QUERY 분류  | "KF-21 최대 속도는?"                  | STRUCTURED_KB_QUERY          |
| TC-030-02 | DOC_RAG_QUERY 분류        | "문서에서 정비 절차 찾아줘"           | DOC_RAG_QUERY                |
| TC-030-03 | SECURITY_RESTRICTED 분류  | "기밀 주파수 알려줘"                  | SECURITY_RESTRICTED          |
| TC-030-04 | UNKNOWN 분류              | "오늘 날씨는?"                        | UNKNOWN                      |
| TC-030-05 | MIXED_QUERY 분류          | "문서에서 최대 속도 제원 찾아줘"      | MIXED_QUERY                  |
| TC-030-06 | 툴 플랜 생성 확인         | DOC_RAG_QUERY 입력                    | tool_plan 길이 ≥ 1           |
| TC-030-07 | SECURITY_RESTRICTED 플랜  | SECURITY_RESTRICTED 입력              | tool="security_refusal"      |

---

## UF-031 — Executor 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                      |
|-----------|---------------------------|---------------------------------------|--------------------------------|
| TC-031-01 | 정상 실행 + 표준 응답     | 유효 플랜 + mock LLM                  | 표준 응답 스키마 6개 필드 반환  |
| TC-031-02 | 스키마 위반 도구 호출     | 잘못된 params 포함 플랜               | error=E_VALIDATION 응답        |
| TC-031-03 | 권한 없는 사용자          | clearance=PUBLIC, SECRET 쿼리         | error=E_AUTH 응답              |
| TC-031-04 | 감사 로그 항상 기록       | 정상 / 오류 요청 모두                  | AuditLogger.write() 호출 확인  |
| TC-031-05 | response hash 포함        | 정상 실행                             | response["hash"] 존재, sha256  |

---

## UF-032 — Tool Schema 검증 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과           |
|-----------|---------------------------|---------------------------------------|---------------------|
| TC-032-01 | 유효한 파라미터           | 올바른 search_docs params             | valid=True          |
| TC-032-02 | 필수 필드 누락            | query 없는 search_docs params         | valid=False         |
| TC-032-03 | 잘못된 타입               | top_k="three" (문자열)                | valid=False         |
| TC-032-04 | 미등록 tool_name          | "unknown_tool"                        | valid=False         |
| TC-032-05 | online_mode 필드 유효성   | online_mode=True (bool)               | valid=True          |

---

## UF-040 — RBAC/ABAC 권한 검사 테스트

**파일**: `tests/unit/test_security.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                        | 기대 결과          |
|-----------|---------------------------|---------------------------------------------|--------------------|
| TC-040-01 | PUBLIC 사용자 PUBLIC 접근 | clearance=PUBLIC, label=PUBLIC              | allowed=True       |
| TC-040-02 | PUBLIC 사용자 SECRET 접근 | clearance=PUBLIC, label=SECRET              | allowed=False      |
| TC-040-03 | SECRET 사용자 RESTRICTED  | clearance=SECRET, label=RESTRICTED          | allowed=True       |
| TC-040-04 | 필드 제한                  | role=air_analyst, field=weapon              | allowed=False      |
| TC-040-05 | post-search 필터          | 혼합 security_label 결과 목록               | PUBLIC 항목만 반환  |

---

## UF-041 — 출력 마스킹 테스트

**파일**: `tests/unit/test_security.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                              | 기대 결과                          |
|-----------|---------------------------|---------------------------------------------------|-----------------------------------|
| TC-041-01 | 좌표 마스킹               | "위도 37.1234, 경도 127.5678"                     | [REDACTED] 치환 확인              |
| TC-041-02 | 주파수 마스킹             | "운용 주파수 9.75 GHz"                            | [REDACTED] 치환 확인              |
| TC-041-03 | sys_id 마스킹             | "시스템 ID: KF-21 확인"                           | [REDACTED] 치환 확인              |
| TC-041-04 | 마스킹 불필요 텍스트      | "항공기 최대 고도 15000m"                         | 원문 유지                          |
| TC-041-05 | masked_count 정확성       | 좌표 + 주파수 포함 텍스트                          | masked_count=2                    |
| TC-041-06 | 규칙 선택적 적용          | mask_rules=["coordinates"] 만                     | 주파수/sys_id 미치환               |

---

## UF-042 — JWT 인증 테스트 (P0 추가)

**파일**: `tests/unit/test_auth.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스                | 입력                                    | 기대 결과                       |
|-----------|-----------------------------|-----------------------------------------|--------------------------------|
| TC-042-01 | 정상 발급 및 검증           | 유효한 user_id, role, clearance         | 페이로드 일치                   |
| TC-042-02 | 페이로드 exp/iat 포함 확인  | issue_token 후 verify                   | exp > iat                      |
| TC-042-03 | jti 포함 확인               | issue_token 후 verify                   | jti 존재                       |
| TC-042-04 | 위변조 토큰 → E_AUTH        | 토큰 마지막 4자 변경                     | PermissionError(E_AUTH)        |
| TC-042-05 | 잘못된 서명 키 → E_AUTH     | 다른 secret으로 verify                  | PermissionError(E_AUTH)        |
| TC-042-06 | 만료된 토큰 → E_AUTH        | ttl_seconds=1, 2초 대기 후 verify       | PermissionError(E_AUTH)        |
| TC-042-07 | 짧은 secret → E_VALIDATION  | secret_key="tooshort"                   | ValueError(E_VALIDATION)       |
| TC-042-08 | 환경변수 secret 사용        | DEFENSE_LLM_JWT_SECRET 환경변수 설정   | 정상 동작                      |
| TC-042-09 | 두 토큰 jti 상이            | 동일 user 두 번 발급                    | p1["jti"] != p2["jti"]         |
| TC-042-10 | extract_user_context RBAC   | analyst/INTERNAL 토큰 → check_access   | allowed=True (INTERNAL 자원)   |

---

## UF-050 — Audit 로그 테스트

**파일**: `tests/unit/test_audit.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                   |
|-----------|---------------------------|---------------------------------------|-----------------------------|
| TC-050-01 | 정상 감사 레코드 저장     | 유효한 감사 데이터                    | saved=True, audit_id 반환   |
| TC-050-02 | audit_id로 조회           | 저장 후 fetch(audit_id)               | 동일 레코드 반환             |
| TC-050-03 | request_id로 조회         | 저장 후 fetch_by_request_id()         | 동일 레코드 반환             |
| TC-050-04 | 필수 필드 누락            | request_id 없는 데이터                | ValueError(E_VALIDATION)    |
| TC-050-05 | error_code 저장           | error_code="E_AUTH" 포함 저장         | 조회 시 error_code 일치      |
| TC-050-06 | citations JSON 직렬화     | citations 목록 포함 저장              | 조회 시 동일 citations 반환  |

---

## UF-060 — LLM 어댑터 Mock 테스트

**파일**: `tests/unit/test_serving.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                           |
|-----------|---------------------------|---------------------------------------|-------------------------------------|
| TC-060-01 | Mock 고정 응답             | fixed_response="테스트"               | content="테스트"                    |
| TC-060-02 | usage 필드 포함            | 임의 messages                         | usage.prompt_tokens ≥ 0            |
| TC-060-03 | AbstractLLMAdapter 구현    | isinstance(mock, AbstractLLMAdapter)  | True                                |
| TC-060-04 | response_fn 동적 응답      | response_fn=lambda m: "동적"          | content="동적"                      |
| TC-060-05 | call_count 증가            | chat() 3회 호출                       | call_count == 3                     |
| TC-060-06 | model_name property        | MockLLMAdapter(model="test-v1")       | model_name == "test-v1"             |

---

## UF-061 — Embedding 추상화 테스트 (P0 추가)

**파일**: `tests/unit/test_embedder.py`

| TC-ID     | 테스트 케이스              | 입력                                     | 기대 결과                           |
|-----------|---------------------------|------------------------------------------|-------------------------------------|
| TC-061-01 | AbstractEmbedder 구현 확인 | isinstance(TFIDFEmbedder(), AbstractEmbedder) | True                           |
| TC-061-02 | encode shape 확인          | 2개 텍스트, vocab_size=128               | (2, 128) float32                   |
| TC-061-03 | L2 정규화 확인             | encode 후 row norm                       | ≈ 1.0                              |
| TC-061-04 | auto-fit (explicit 없이)   | encode 바로 호출                         | 오류 없이 동작                      |
| TC-061-05 | 동일 텍스트 → 동일 벡터    | 동일 텍스트 2회 encode                   | 배열 동일                           |
| TC-061-06 | DocumentIndex + embedder   | TFIDFEmbedder 주입 후 add_chunks + search | 결과 반환                          |
| TC-061-07 | index save/load 라운드트립 | save() → load() → chunk_count 비교       | 일치                               |
| TC-061-08 | 로드된 인덱스 검색 가능    | load() 후 search()                       | 결과 ≥ 1                           |
| TC-061-09 | load 디렉토리 없음         | DocumentIndex.load("nonexistent")        | FileNotFoundError                  |
| TC-061-10 | save 파일 목록 확인        | save() 후 파일 존재 확인                 | bm25.pkl, dense.pkl, legacy.pkl, meta.json |

---

## UF-070 — Eval Runner 테스트

**파일**: `tests/unit/test_eval.py`

| TC-ID     | 테스트 케이스              | 입력                                          | 기대 결과                       |
|-----------|---------------------------|-----------------------------------------------|--------------------------------|
| TC-070-01 | 정상 리포트 생성           | 2개 샘플, mock 시스템                         | pass_rate 계산, JSON 리포트     |
| TC-070-02 | 빈 샘플 목록              | samples=[]                                    | ValueError(E_VALIDATION)        |
| TC-070-03 | citation 일치 확인        | expected_citation_doc_ids와 실제 일치          | citation_match=True            |
| TC-070-04 | pass_rate 범위            | 1개 통과, 1개 실패                             | pass_rate=0.5                  |

---

## 커버리지 측정 명령

```bash
# dllm 환경 Python 사용
C:\Users\user\anaconda3\envs\dllm\python -m pytest tests/unit/ \
  --cov=src/defense_llm \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml
```

### 모듈별 커버리지 목표 요약

| 모듈 경로                               | 목표     | 비고 |
|-----------------------------------------|----------|------|
| `src/defense_llm/config/`              | ≥ 70%    | |
| `src/defense_llm/knowledge/`           | ≥ 70%    | |
| `src/defense_llm/rag/chunker.py`       | ≥ 70%    | |
| `src/defense_llm/rag/retriever.py`     | ≥ 70%    | |
| `src/defense_llm/rag/indexer.py`       | ≥ 70%    | |
| `src/defense_llm/rag/citation.py`      | ≥ 70%    | |
| `src/defense_llm/rag/embedder.py`      | ≥ 70%    | TFIDFEmbedder 경로만 (Qwen25 모델 미로딩) |
| `src/defense_llm/agent/`               | ≥ 70%    | |
| `src/defense_llm/serving/mock_llm.py`  | ≥ 70%    | |
| `src/defense_llm/serving/qwen_adapter.py` | ≥ 50% | 모델 로딩 제외 |
| `src/defense_llm/eval/`               | ≥ 70%    | |
| `src/defense_llm/security/rbac.py`    | **≥ 80%** | |
| `src/defense_llm/security/masking.py` | **≥ 80%** | |
| `src/defense_llm/security/auth.py`    | **≥ 80%** | |
| `src/defense_llm/audit/`              | **≥ 80%** | |
| `src/defense_llm/agent/tool_schemas.py` | **≥ 80%** | |
