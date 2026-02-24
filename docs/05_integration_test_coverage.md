# 05_integration_test_coverage.md — IF 통합 테스트 및 커버리지 계획

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
- SQLite 임시 DB
- 더미 텍스트 문서 (`tests/fixtures/dummy_doc_air.txt`)
- Mock LLM 어댑터

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                    |
|------------|-----------------------------------|----------------------------------------------|
| ITC-001-01 | 문서 등록 → 인덱싱 성공           | indexed_count ≥ 1                            |
| ITC-001-02 | 질의 후 citation 포함 응답 반환   | citations 최소 1건, 필수 4필드 포함          |
| ITC-001-03 | 표준 응답 스키마 검증             | 6개 최상위 필드 모두 존재                    |
| ITC-001-04 | 감사 로그 기록 확인               | 감사 DB에 request_id 존재                    |

### 검증 코드 요점
```python
# citation 검증 예시
for c in response["citations"]:
    assert "doc_id" in c
    assert "doc_rev" in c
    assert "page" in c or "section_id" in c
    assert "snippet_hash" in c
```

---

## ITC-002 — IF-002: 정형 DB 조회 → 제약 적용 → 근거 응답

**파일**: `tests/integration/test_kb_query.py`

### 전제 조건
- 더미 플랫폼 데이터 삽입 (`tests/fixtures/dummy_platform.sql`)
- Mock LLM 어댑터

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                    |
|------------|-----------------------------------|----------------------------------------------|
| ITC-002-01 | STRUCTURED_KB_QUERY 플랜 생성     | query_type=STRUCTURED_KB_QUERY               |
| ITC-002-02 | DB에서 제원 조회 성공             | data에 수치 정보 포함                        |
| ITC-002-03 | citations에 출처 포함             | citations 최소 1건                           |
| ITC-002-04 | 감사 로그 기록 확인               | 감사 DB에 request_id 존재                    |

---

## ITC-003 — IF-003: 권한 없는 사용자 → 기밀 문서 접근 거절

**파일**: `tests/integration/test_security_access.py`

### 전제 조건
- SECRET 라벨 문서 인덱싱 (`tests/fixtures/dummy_doc_secret.txt`)
- clearance=PUBLIC 사용자 컨텍스트

### 테스트 케이스

| TC-ID      | 설명                                    | 기대 결과                                 |
|------------|----------------------------------------|-------------------------------------------|
| ITC-003-01 | PUBLIC 사용자 SECRET 문서 검색 → 0건   | citations=[], 결과 0건                    |
| ITC-003-02 | 응답에 E_AUTH 또는 거절 메시지 포함    | error 또는 data.answer에 거절 표시        |
| ITC-003-03 | SECRET 문서 내용 미노출 확인           | 응답 텍스트에 SECRET 문서 스니펫 미포함   |
| ITC-003-04 | 출력 마스킹 적용 확인                  | 좌표/주파수 패턴 미노출                   |
| ITC-003-05 | 감사 로그에 거절 기록                  | 감사 DB에 error=E_AUTH 기록              |

---

## ITC-004 — IF-004: 감사 로그 필수 필드 저장 검증

**파일**: `tests/integration/test_audit_logging.py`

### 전제 조건
- IF-001 또는 IF-002 정상 실행 후

### 테스트 케이스

| TC-ID      | 설명                              | 기대 결과                                           |
|------------|-----------------------------------|-----------------------------------------------------|
| ITC-004-01 | 감사 레코드 필수 필드 확인        | request_id, model_version, index_version 모두 존재  |
| ITC-004-02 | citation 목록 저장 확인           | 감사 레코드의 citations 필드가 비어있지 않음         |
| ITC-004-03 | response_hash 일치 확인           | 감사의 response_hash == SHA256(응답 JSON)            |
| ITC-004-04 | timestamp 형식 확인               | ISO8601 형식 준수                                   |

---

## ITC-005 — IF-005: Tool Schema 위반 → 안전 응답

**파일**: `tests/integration/test_tool_schema_violation.py`

### 전제 조건
- Mock LLM 어댑터
- 잘못된 파라미터를 포함한 tool_plan 직접 주입

### 테스트 케이스

| TC-ID      | 설명                                  | 기대 결과                              |
|------------|---------------------------------------|----------------------------------------|
| ITC-005-01 | 스키마 위반 tool_plan → E_VALIDATION  | error=E_VALIDATION 응답                |
| ITC-005-02 | citations 0건 확인                    | citations=[]                           |
| ITC-005-03 | 시스템 계속 동작 확인                 | 이후 정상 요청 처리 가능               |
| ITC-005-04 | 감사 로그에 오류 기록                 | 감사 DB에 오류 상태 기록               |

---

## 통합 테스트 공통 설정

### conftest.py 요점
```python
# tests/integration/conftest.py
import pytest
import tempfile
from defense_llm.knowledge.db_schema import init_db
from defense_llm.serving.mock_llm import MockLLMAdapter

@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    init_db(str(db_path))
    return str(db_path)

@pytest.fixture(scope="session")
def mock_llm():
    return MockLLMAdapter(fixed_response="테스트 응답입니다.")
```

### 더미 데이터 위치
```
tests/
  fixtures/
    dummy_doc_air.txt        # air 필드 더미 문서
    dummy_doc_secret.txt     # SECRET 라벨 더미 문서
    dummy_platform.sql       # 더미 플랫폼 DB 데이터
    dummy_qa_samples.json    # Eval Runner용 QA 샘플
```

---

## 통합 테스트 실행 명령

```bash
pytest tests/integration/ -v --cov=src/defense_llm --cov-report=term-missing --cov-report=xml:coverage_integration.xml
```

---

## 전체 테스트 실행

```bash
pytest -q
pytest --cov=src/defense_llm --cov-report=term-missing --cov-report=xml
```
