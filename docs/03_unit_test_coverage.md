# 03_unit_test_coverage.md — UF 단위 테스트 및 커버리지 계획

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
| TC-001-01 | 정상 설정 로딩        | 유효한 config dict             | 설정 객체 반환                 |
| TC-001-02 | 필수 키 누락          | model_name 없는 config         | E_VALIDATION 예외 발생         |
| TC-001-03 | 환경변수 오버라이드   | 환경변수 설정 후 로딩           | 환경변수 값 우선 적용          |

---

## UF-010 — DB 스키마 초기화 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력                        | 기대 결과                          |
|-----------|--------------------------|-----------------------------|-----------------------------------|
| TC-010-01 | 정상 DB 초기화           | 임시 경로                   | 필수 테이블 모두 생성              |
| TC-010-02 | 중복 초기화(idempotent)  | 이미 초기화된 DB 경로       | 오류 없이 완료                     |

---

## UF-011 — 문서 메타 등록 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력                              | 기대 결과                |
|-----------|--------------------------|-----------------------------------|--------------------------|
| TC-011-01 | 정상 메타 등록           | 유효한 메타 딕셔너리              | registered=True          |
| TC-011-02 | 필수 필드 누락           | field 없는 딕셔너리               | E_VALIDATION             |
| TC-011-03 | 잘못된 security_label    | security_label="TOPSECRET"        | E_VALIDATION             |
| TC-011-04 | 중복 doc_id+rev          | 동일 doc_id, doc_rev 재등록       | E_CONFLICT               |

---

## UF-012 — Glossary 매핑 테스트

**파일**: `tests/unit/test_knowledge.py`

| TC-ID     | 테스트 케이스            | 입력            | 기대 결과               |
|-----------|--------------------------|-----------------|-------------------------|
| TC-012-01 | 등록된 약어 조회         | "KF-21"         | found=True, 정의 반환   |
| TC-012-02 | 미등록 약어 조회         | "XYZ-99"        | found=False             |

---

## UF-020 — 청킹/인덱싱 테스트

**파일**: `tests/unit/test_rag.py`

| TC-ID     | 테스트 케이스            | 입력                             | 기대 결과                       |
|-----------|--------------------------|----------------------------------|---------------------------------|
| TC-020-01 | 정상 청킹                | 500자 텍스트, max_tokens=100     | 청크 수 ≥ 1, 각 청크에 doc_id  |
| TC-020-02 | 빈 텍스트 입력           | text=""                          | E_VALIDATION                    |
| TC-020-03 | 청크 토큰 수 초과 없음   | max_tokens=50 설정               | 모든 청크 토큰 수 ≤ 50         |

---

## UF-021 — 하이브리드 검색 테스트

**파일**: `tests/unit/test_rag.py`

| TC-ID     | 테스트 케이스            | 입력                                  | 기대 결과                          |
|-----------|--------------------------|---------------------------------------|-----------------------------------|
| TC-021-01 | 정상 검색 결과 반환      | query="전투기 무장", top_k=3          | 결과 수 ≤ 3                       |
| TC-021-02 | 필드 필터 적용           | field_filter=["air"]                  | 반환 결과 모두 field=air           |
| TC-021-03 | 빈 쿼리                  | query=""                              | E_VALIDATION                      |
| TC-021-04 | 보안 라벨 필터           | security_label_filter=["PUBLIC"]      | SECRET 라벨 결과 미포함            |

---

## UF-022 — Citation 패키징 테스트

**파일**: `tests/unit/test_rag.py`

| TC-ID     | 테스트 케이스            | 입력                                  | 기대 결과                              |
|-----------|--------------------------|---------------------------------------|----------------------------------------|
| TC-022-01 | 정상 citation 생성       | 유효한 청크 목록                      | 각 citation에 필수 4필드 포함          |
| TC-022-02 | snippet_hash 검증        | 동일 텍스트 두 번 패키징              | 동일 hash 값                           |
| TC-022-03 | 필수 필드 누락 청크       | doc_id 없는 청크 입력                 | E_VALIDATION                           |

---

## UF-030 — 규칙 기반 Planner 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                    |
|-----------|---------------------------|---------------------------------------|------------------------------|
| TC-030-01 | STRUCTURED_KB_QUERY 분류  | "KF-21 최대 속도는?"                  | STRUCTURED_KB_QUERY          |
| TC-030-02 | DOC_RAG_QUERY 분류        | "문서에서 정비 절차 찾아줘"           | DOC_RAG_QUERY                |
| TC-030-03 | SECURITY_RESTRICTED 분류  | "기밀 주파수 알려줘"                  | SECURITY_RESTRICTED          |
| TC-030-04 | UNKNOWN 분류              | "오늘 날씨는?"                        | UNKNOWN                      |
| TC-030-05 | 툴 플랜 생성 확인         | DOC_RAG_QUERY 입력                    | tool_plan 길이 ≥ 1           |

---

## UF-031 — Executor 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                      |
|-----------|---------------------------|---------------------------------------|--------------------------------|
| TC-031-01 | 정상 실행 + 표준 응답     | 유효 플랜 + mock LLM                  | 표준 응답 스키마 반환          |
| TC-031-02 | 스키마 위반 도구 호출     | 잘못된 params 포함 플랜               | E_VALIDATION 포함 응답         |
| TC-031-03 | 권한 없는 사용자          | clearance=PUBLIC, SECRET 쿼리         | E_AUTH 포함 응답               |

---

## UF-032 — Tool Schema 검증 테스트

**파일**: `tests/unit/test_agent.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과           |
|-----------|---------------------------|---------------------------------------|---------------------|
| TC-032-01 | 유효한 파라미터           | 올바른 search_docs params             | valid=True          |
| TC-032-02 | 필수 필드 누락            | query 없는 search_docs params         | valid=False         |
| TC-032-03 | 잘못된 타입               | top_k="three" (문자열)                | valid=False         |

---

## UF-040 — RBAC/ABAC 권한 검사 테스트

**파일**: `tests/unit/test_security.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                        | 기대 결과          |
|-----------|---------------------------|---------------------------------------------|--------------------|
| TC-040-01 | PUBLIC 사용자 PUBLIC 접근 | clearance=PUBLIC, label=PUBLIC              | allowed=True       |
| TC-040-02 | PUBLIC 사용자 SECRET 접근 | clearance=PUBLIC, label=SECRET              | allowed=False      |
| TC-040-03 | SECRET 사용자 RESTRICTED  | clearance=SECRET, label=RESTRICTED          | allowed=True       |
| TC-040-04 | 필드 제한                  | role=air_analyst, field=weapon              | allowed=False      |

---

## UF-041 — 출력 마스킹 테스트

**파일**: `tests/unit/test_security.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                              | 기대 결과                          |
|-----------|---------------------------|---------------------------------------------------|-----------------------------------|
| TC-041-01 | 좌표 마스킹               | "위도 37.1234, 경도 127.5678"                     | [REDACTED] 치환 확인              |
| TC-041-02 | 주파수 마스킹             | "운용 주파수 9.75 GHz"                            | [REDACTED] 치환 확인              |
| TC-041-03 | 마스킹 불필요 텍스트      | "항공기 최대 고도 15000m"                         | 원문 유지                          |
| TC-041-04 | masked_count 정확성       | 2개 패턴 포함 텍스트                              | masked_count=2                    |

---

## UF-050 — Audit 로그 테스트

**파일**: `tests/unit/test_audit.py` (목표: ≥ 80%)

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                   |
|-----------|---------------------------|---------------------------------------|-----------------------------|
| TC-050-01 | 정상 감사 레코드 저장     | 유효한 감사 데이터                    | saved=True, audit_id 반환   |
| TC-050-02 | 저장 후 조회              | 저장 후 audit_id로 조회               | 동일 레코드 반환             |
| TC-050-03 | 필수 필드 누락            | request_id 없는 데이터                | E_VALIDATION / 저장 실패    |

---

## UF-060 — LLM 어댑터 Mock 테스트

**파일**: `tests/unit/test_serving.py`

| TC-ID     | 테스트 케이스              | 입력                                  | 기대 결과                       |
|-----------|---------------------------|---------------------------------------|---------------------------------|
| TC-060-01 | Mock 어댑터 응답           | 표준 messages 입력                    | content 문자열 반환             |
| TC-060-02 | usage 필드 포함            | 임의 messages                         | usage.prompt_tokens ≥ 0        |
| TC-060-03 | 어댑터 인터페이스 일치     | Mock/Real 동일 메서드 시그니처        | AbstractLLMAdapter 구현 확인   |

---

## UF-070 — Eval Runner 테스트

**파일**: `tests/unit/test_eval.py`

| TC-ID     | 테스트 케이스              | 입력                                          | 기대 결과                       |
|-----------|---------------------------|-----------------------------------------------|--------------------------------|
| TC-070-01 | 정상 리포트 생성           | 2개 샘플, mock 시스템                         | pass_rate 계산, JSON 리포트    |
| TC-070-02 | 빈 샘플 목록              | samples=[]                                    | E_VALIDATION                   |
| TC-070-03 | citation 일치 확인        | expected_doc_ids와 실제 일치                  | citation_match=True            |

---

## 커버리지 측정 명령

```bash
pytest tests/unit/ --cov=src/defense_llm --cov-report=term-missing --cov-report=xml:coverage.xml
```

### 모듈별 커버리지 목표 요약

| 모듈 경로                          | 목표  |
|------------------------------------|-------|
| `src/defense_llm/config/`          | ≥70%  |
| `src/defense_llm/knowledge/`       | ≥70%  |
| `src/defense_llm/rag/`             | ≥70%  |
| `src/defense_llm/agent/`           | ≥70%  |
| `src/defense_llm/serving/`         | ≥70%  |
| `src/defense_llm/eval/`            | ≥70%  |
| `src/defense_llm/security/`        | **≥80%** |
| `src/defense_llm/audit/`           | **≥80%** |
| `src/defense_llm/agent/tool_schemas.py` | **≥80%** |
