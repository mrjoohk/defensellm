# Defense Domain sLLM/Agent System

방산 도메인 지식·에이전트 시스템 — Qwen2.5 1.5B 기반, 상위 모델 확장 가능

---

## 특징

- **RAG + 정형 DB**: 지식은 문서/DB에, 모델은 언어 생성·도구 호출에 집중
- **Rule-based Planner + LLM Executor**: 1.5B 소형 모델에 최적화된 안정적 파이프라인
- **RBAC/ABAC 보안**: 검색 전/후 접근 제어, 출력 마스킹
- **완전 감사 로그**: request_id, 모델/인덱스 버전, citation, 응답 해시
- **오프라인 동작**: 외부 네트워크 없이 mock LLM으로 전체 테스트 실행
- **어댑터 패턴**: `serving/` 레이어만 교체하여 1.5B → 7B/14B/32B 전환

---

## 프로젝트 구조

```
src/defense_llm/
├── config/          # 설정 로딩 (UF-001)
├── knowledge/       # DB 스키마, 문서 메타, Glossary (UF-010~012)
├── rag/             # 청킹, 인덱싱, 검색, Citation (UF-020~022)
├── agent/           # Planner(규칙), Executor, Tool Schema (UF-030~032)
├── security/        # RBAC/ABAC, 출력 마스킹 (UF-040~041)
├── audit/           # 감사 로그 (UF-050)
├── serving/         # LLM 어댑터 + Mock (UF-060)
└── eval/            # Eval Runner (UF-070)

tests/
├── unit/            # UF 단위 테스트
├── integration/     # IF 통합 테스트
└── fixtures/        # 더미 문서, QA 샘플

docs/
├── 01_requirements.md
├── 02_unit_functions.md
├── 03_unit_test_coverage.md
├── 04_integration_functions.md
└── 05_integration_test_coverage.md
```

---

## 로컬 설치 및 테스트

### 1. 가상환경 설정

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -e ".[dev]"
# 또는
pip install -r requirements.txt
```

### 3. 전체 테스트 실행

```bash
pytest -q
```

### 4. 커버리지 포함 실행

```bash
pytest --cov=src/defense_llm --cov-report=term-missing --cov-report=xml
```

### 5. 단위 테스트만 실행

```bash
pytest tests/unit/ -v
```

### 6. 통합 테스트만 실행

```bash
pytest tests/integration/ -v
```

---

## 표준 응답 스키마

```json
{
  "request_id": "uuid",
  "data": { "answer": "..." },
  "citations": [
    {
      "doc_id": "string",
      "doc_rev": "string",
      "page": 1,
      "section_id": "optional",
      "snippet": "string",
      "snippet_hash": "sha256"
    }
  ],
  "security_label": "PUBLIC|INTERNAL|RESTRICTED|SECRET",
  "version": {
    "model": "qwen2.5-1.5b-instruct",
    "index": "idx-YYYYMMDD-hhmm",
    "db": "schema-v1"
  },
  "hash": "sha256-of-response"
}
```

---

## 상위 모델 전환 방법

`serving/` 어댑터만 교체합니다. 다른 레이어는 변경 불필요.

```python
# 현재: mock
from defense_llm.serving.mock_llm import MockLLMAdapter
adapter = MockLLMAdapter()

# 전환 예시 (vLLM 어댑터 구현 후)
# from defense_llm.serving.vllm_adapter import VLLMAdapter
# adapter = VLLMAdapter(model="Qwen/Qwen2.5-7B-Instruct", ...)
```

상세 전환 포인트는 [todo.md](todo.md) 참고.

---

## 커버리지 목표

| 모듈 | 목표 |
|------|------|
| config, knowledge, rag, agent, serving, eval | ≥ 70% |
| security, audit, agent/tool_schemas | ≥ 80% |
| 통합 시나리오 성공률 | 100% |
