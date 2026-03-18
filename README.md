# Defense Domain sLLM/Agent System

방산 도메인 지식·에이전트 시스템 — Qwen2.5 기반, vLLM 지원, ReAct 에이전트 루프

---

## 특징

- **ReAct 에이전트 루프**: LLM이 tool_call을 직접 선택·실행하는 OpenAI Function-Calling 방식
- **Agentic RAG + 코드 실행**: RAG 검색 → 스크립트 생성 → 배치 실행 → CSV 저장 전체 파이프라인 지원
- **vLLM 지원**: `VLLMAdapter`로 `vllm serve` 엔드포인트에 연결, 프로덕션 확장 가능
- **RBAC/ABAC 보안**: 검색 전/후 접근 제어, 스크립트 경로 화이트리스트, AST 기반 코드 검증
- **완전 감사 로그**: request_id, 모델/인덱스 버전, citation, 응답 해시, 스크립트 실행 이력
- **오프라인 동작**: `MockLLMAdapter` + `tool_call_sequence`로 외부 네트워크 없이 전체 에이전트 테스트
- **어댑터 패턴**: `serving/` 레이어만 교체하여 Mock → Qwen(HuggingFace) → vLLM 전환

---

## 에이전트 실행 흐름

```
사용자 프롬프트
  → LLM (tool_call: search_docs)     ← RAG 검색
  → LLM (tool_call: create_script)   ← Python 스크립트 생성
  → LLM (tool_call: create_batch_script) ← 배치 래퍼 생성
  → LLM (tool_call: execute_batch_script) ← 스크립트 실행
  → LLM (tool_call: save_results_csv) ← 결과 CSV 저장
  → LLM (최종 텍스트 응답)
  → 표준 응답 스키마 + 감사 로그
```

---

## 프로젝트 구조

```
src/defense_llm/
├── config/          # 설정 로딩 (UF-001)
├── knowledge/       # DB 스키마, 문서 메타, Glossary (UF-010~012)
├── rag/             # 청킹, 인덱싱, 검색, Citation (UF-020~022)
├── agent/
│   ├── executor.py       # ReAct 에이전트 루프 + 파이프라인 모드 (UF-031)
│   ├── script_tools.py   # 스크립트 생성/실행/CSV 저장 도구 (보안 게이트 포함)
│   ├── tool_schemas.py   # OpenAI 형식 tool definitions (UF-032)
│   └── planner_rules/    # 규칙 기반 플래너 (UF-030)
├── security/        # RBAC/ABAC, 출력 마스킹 (UF-040~041)
├── audit/           # 감사 로그 (UF-050)
├── serving/
│   ├── adapter.py        # AbstractLLMAdapter (tools 파라미터 포함)
│   ├── mock_llm.py       # MockLLMAdapter (tool_call_sequence 지원)
│   ├── qwen_adapter.py   # Qwen2.5 HuggingFace 어댑터 (XML tool_call 파싱)
│   └── vllm_adapter.py   # VLLMAdapter (vllm serve OpenAI 호환 엔드포인트)
└── eval/            # Eval Runner (UF-070)

tests/
├── unit/            # UF 단위 테스트 (208개 전체 통과)
├── integration/     # IF 통합 테스트 (IF-001~006)
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
```

### 3. 전체 테스트 실행

```bash
pytest -q
# 208 passed
```

### 4. 커버리지 포함 실행

```bash
pytest --cov=src/defense_llm --cov-report=term-missing --cov-report=xml
```

### 5. 에이전트 루프 테스트만 실행

```bash
pytest tests/unit/test_agent_loop.py tests/integration/test_agent_script_pipeline.py -v
```

---

## LLM 어댑터 전환

`serving/` 어댑터만 교체합니다. 다른 레이어는 변경 불필요.

```python
# 개발/테스트: MockLLM (tool_call_sequence로 에이전트 루프 시뮬레이션)
from defense_llm.serving.mock_llm import MockLLMAdapter
adapter = MockLLMAdapter(
    fixed_response="분석 완료.",
    tool_call_sequence=[search_tc, create_tc, execute_tc, None],
)

# 로컬 HuggingFace: Qwen2.5 (XML tool_call 파싱 내장)
from defense_llm.serving.qwen_adapter import Qwen25Adapter
adapter = Qwen25Adapter(model_id="Qwen/Qwen2.5-7B-Instruct")

# 프로덕션: vLLM (vllm serve 엔드포인트 연결)
from defense_llm.serving.vllm_adapter import VLLMAdapter
adapter = VLLMAdapter(
    model_id="Qwen/Qwen2.5-7B-Instruct",
    base_url="http://localhost:8000/v1",
)
```

### vLLM 서버 실행 예시

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

---

## Executor 에이전트 모드 사용

```python
from defense_llm.agent.executor import Executor
from defense_llm.serving.vllm_adapter import VLLMAdapter
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger

ex = Executor(
    llm_adapter=VLLMAdapter(model_id="Qwen/Qwen2.5-7B-Instruct"),
    index=DocumentIndex(),
    db_path="kb.db",
    audit_logger=AuditLogger("audit.db"),
    agent_mode=True,
    max_agent_turns=10,
    script_tools_enabled=True,
)

resp = ex.execute(
    [],
    {"role": "analyst", "clearance": "INTERNAL", "user_id": "u001"},
    query="KF-21 속도 분석 후 결과를 CSV로 저장해줘",
)
print(resp["data"]["answer"])
```

### 스크립트 허용 경로 설정

```python
import defense_llm.agent.script_tools as st
st.add_allowed_path(r"C:\User\users\llm_test")
```

또는 환경변수로 설정:

```bash
DEFENSE_LLM_AGENT_MODE=true
DEFENSE_LLM_SCRIPT_TOOLS_ENABLED=true
DEFENSE_LLM_VLLM_BASE_URL=http://localhost:8000/v1
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
      "page": "string",
      "section_id": "optional",
      "snippet": "string",
      "snippet_hash": "sha256"
    }
  ],
  "security_label": "PUBLIC|INTERNAL|RESTRICTED|SECRET",
  "version": {
    "model": "qwen2.5-7b-instruct",
    "index": "idx-YYYYMMDD-hhmm",
    "db": "schema-v1"
  },
  "hash": "sha256-of-response"
}
```

---

## 커버리지 목표

| 모듈 | 목표 |
|------|------|
| config, knowledge, rag, agent, serving, eval | ≥ 70% |
| security, audit, agent/tool_schemas | ≥ 80% |
| 통합 시나리오 성공률 | 100% |
