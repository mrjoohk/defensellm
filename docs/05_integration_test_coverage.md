# 05_integration_test_coverage.md — IF 통합 테스트 및 커버리지 계획

> **최종 갱신**: 2026-03-18 — 실제 구현 소스코드 기준으로 전면 동기화

---

## 커버리지 목표 (통합)

| 목표 | 기준 |
|------|------|
| 핵심 시나리오 성공률 | **100%** |
| 보안/감사 시나리오 통과율 | **100%** |
| coverage 리포트 생성 | 필수 |

---

## ITC-001 — IF-001: 문서 업로드 → 인덱싱 → 질의 → 근거 인용 답변

**파일**: `tests/integration/test_document_pipeline.py`

### 전제 조건
- SQLite 임시 DB (conftest.py 픽스처)
- 더미 텍스트 문서 (`tests/fixtures/dummy_doc_air.txt`)
- Mock LLM 어댑터 (`MockLLMAdapter`)
- `DocumentIndex` (embedder=None, 레거시 TF-IDF fallback)

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                    |
|------------|-----------------------------------|----------------------------------------------|
| ITC-001-01 | 문서 등록 → 인덱싱 성공           | indexed_count ≥ 1                            |
| ITC-001-02 | 질의 후 citation 포함 응답 반환   | citations 최소 1건, 필수 필드 포함           |
| ITC-001-03 | 표준 응답 스키마 검증             | request_id, data, citations, security_label, version, hash 모두 존재 |
| ITC-001-04 | 감사 로그 기록 확인               | fetch_by_request_id()로 레코드 조회 성공     |

### 검증 코드 요점
```python
# citation 검증 예시 (실제 필드명 기준)
for c in response["citations"]:
    assert "doc_id" in c
    assert "doc_rev" in c          # package_citations() 출력 필드
    assert "page" in c or "section_id" in c
    assert "snippet_hash" in c
    assert len(c["snippet_hash"]) == 64  # SHA-256 hex
```

### 구현 주의사항
- `chunk_document()` 호출 시 파라미터명 `version` 사용 (not `doc_rev`)
- `DocumentIndex.add_chunks(chunks["chunks"])` — `chunk_document()` 반환값의 `"chunks"` 키

---

## ITC-002 — IF-002: 정형 DB 조회 → 제약 적용 → 근거 응답

**파일**: `tests/integration/test_kb_query.py`

### 전제 조건
- 더미 플랫폼 데이터 SQLite 삽입
- Mock LLM 어댑터

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                    |
|------------|-----------------------------------|----------------------------------------------|
| ITC-002-01 | STRUCTURED_KB_QUERY 플랜 생성     | query_type=STRUCTURED_KB_QUERY               |
| ITC-002-02 | DB에서 제원 조회 성공             | data에 응답 포함 (검색 결과 없으면 빈 안내)  |
| ITC-002-03 | 표준 응답 스키마 6개 필드         | 모두 존재                                    |
| ITC-002-04 | 감사 로그 기록 확인               | fetch_by_request_id()로 레코드 조회 성공     |

---

## ITC-003 — IF-003: 권한 없는 사용자 → 기밀 문서 접근 거절

**파일**: `tests/integration/test_security_access.py`

### 전제 조건
- SECRET 라벨 문서 인덱싱 (`tests/fixtures/dummy_doc_secret.txt`)
- clearance=PUBLIC 사용자 컨텍스트

### 테스트 케이스

| TC-ID      | 설명                                    | 기대 결과                                 |
|------------|----------------------------------------|-------------------------------------------|
| ITC-003-01 | PUBLIC 사용자 SECRET 필터 → 0건        | citations=[], 결과 0건                    |
| ITC-003-02 | 응답에 E_AUTH 또는 거절 메시지 포함    | response.get("error")=="E_AUTH" 또는 data.answer에 거절 표시 |
| ITC-003-03 | SECRET 문서 내용 미노출 확인           | 응답 텍스트에 SECRET 문서 스니펫 미포함   |
| ITC-003-04 | 감사 로그에 거절 기록                  | audit_record["error_code"] == "E_AUTH"    |

### 검증 코드 요점
```python
# 보안 검증 예시
assert response["citations"] == []
assert response.get("error") == "E_AUTH" or "권한" in response["data"]["answer"]

# SECRET 내용 노출 방지 검증
secret_content = open("tests/fixtures/dummy_doc_secret.txt").read()[:50]
assert secret_content not in response["data"]["answer"]
```

---

## ITC-004 — IF-004: 감사 로그 필수 필드 저장 검증

**파일**: `tests/integration/test_audit_logging.py`

### 전제 조건
- IF-001 또는 IF-002 정상 실행 후

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                           |
|------------|-----------------------------------|-----------------------------------------------------|
| ITC-004-01 | 감사 레코드 필수 필드 확인        | request_id, model_version, index_version 모두 존재  |
| ITC-004-02 | citation 목록 저장 확인           | 감사 레코드 citations 필드 비어있지 않음             |
| ITC-004-03 | response_hash 일치 확인           | 감사의 response_hash == response["hash"]             |
| ITC-004-04 | timestamp 형식 확인               | ISO8601 형식 준수 (parse 성공)                      |
| ITC-004-05 | fetch_by_request_id 조회 성공     | 응답 request_id로 감사 레코드 조회 성공              |

### 검증 코드 요점
```python
from datetime import datetime
audit = audit_logger.fetch_by_request_id(response["request_id"])
assert audit is not None
assert audit["response_hash"] == response["hash"]
datetime.fromisoformat(audit["timestamp"])  # ISO8601 파싱 성공 확인
```

---

## ITC-005 — IF-005: Tool Schema 위반 → 안전 응답

**파일**: `tests/integration/test_tool_schema_violation.py`

### 전제 조건
- Mock LLM 어댑터
- 잘못된 파라미터를 포함한 tool_plan 직접 주입

### 테스트 케이스

| TC-ID      | 설명                                  | 기대 결과                              |
|------------|---------------------------------------|----------------------------------------|
| ITC-005-01 | 스키마 위반 tool_plan → E_VALIDATION  | response["error"] == "E_VALIDATION"    |
| ITC-005-02 | citations 0건 확인                    | response["citations"] == []            |
| ITC-005-03 | 시스템 계속 동작 확인                 | 이후 정상 요청 처리 가능 (citations 반환) |
| ITC-005-04 | 감사 로그에 오류 기록                 | audit_record["error_code"] == "E_VALIDATION" |
| ITC-005-05 | hash 필드 오류 응답에도 존재          | response["hash"] 존재, sha256 형식     |

---

## 통합 테스트 공통 설정

### conftest.py 요점
```python
# tests/integration/conftest.py
import pytest
import tempfile
from defense_llm.knowledge.db_schema import init_db
from defense_llm.serving.mock_llm import MockLLMAdapter
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger

@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("db") / "test.db")
    init_db(db_path)
    return db_path

@pytest.fixture(scope="session")
def mock_llm():
    return MockLLMAdapter(fixed_response="테스트 응답입니다.")

@pytest.fixture(scope="session")
def document_index():
    # embedder=None → 레거시 TF-IDF fallback (오프라인 테스트)
    return DocumentIndex(embedder=None)

@pytest.fixture(scope="session")
def audit_logger(tmp_db):
    return AuditLogger(tmp_db)
```

### 더미 데이터 위치
```
tests/
  fixtures/
    dummy_doc_air.txt        # air 필드 더미 문서 (INTERNAL)
    dummy_doc_secret.txt     # SECRET 라벨 더미 문서
    dummy_qa_samples.json    # Eval Runner용 QA 샘플
```

---

## 통합 테스트 실행 명령

```bash
# dllm 환경 Python 사용
C:\Users\user\anaconda3\envs\dllm\python -m pytest tests/integration/ -v \
  --cov=src/defense_llm \
  --cov-report=term-missing \
  --cov-report=xml:coverage_integration.xml
```

---

## 전체 테스트 실행

```bash
# 단위 + 통합 전체 실행
C:\Users\user\anaconda3\envs\dllm\python -m pytest -q

# 커버리지 포함 전체 실행
C:\Users\user\anaconda3\envs\dllm\python -m pytest \
  --cov=src/defense_llm \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml
```
