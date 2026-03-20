# todo.md — 미결/유보 항목 및 향후 작업

이 파일은 현재 MVP 구현에서 의도적으로 생략하거나 TODO로 남긴 항목을 정리합니다.

---

## 1. 구현 미완성 항목 (기능 동작 가능하나 MVP 수준)

### 1.1 벡터 인덱스 — FAISS 미적용
- **현재**: `SimpleVectorIndex` (TF-IDF 코사인 유사도, 순수 Python)
- **TODO**: `faiss-cpu` 또는 `hnswlib` 기반 ANN 인덱스로 교체
- **이유 유보**: `faiss` 설치 시 C++ 빌드 도구 필요, 오프라인 MVP 범위 초과
- **파일**: `src/defense_llm/rag/indexer.py` → `SimpleVectorIndex` 교체
- **우선순위**: P1

### 1.2 BM25 — 내장 구현 사용 중
- **현재**: `BM25Index` 직접 구현 (외부 라이브러리 없음)
- **TODO**: `rank-bm25` 라이브러리로 교체하거나 Whoosh 인덱스 연동
- **파일**: `src/defense_llm/rag/indexer.py` → `BM25Index` 교체
- **우선순위**: P1

### ~~1.3 임베딩 — 실제 임베딩 모델 미적용~~ ✅ 완료
- **구현**: `src/defense_llm/rag/embedder.py` — `Qwen25Embedder`(Qwen2.5 mean-pool) + `TFIDFEmbedder`(테스트 폴백)
- `DocumentIndex`에 embedder 주입 지원, L2-정규화 numpy cosine 유사도 사용
- **우선순위**: P0 → **완료**

### 1.4 PDF 파싱 미구현
- **현재**: 텍스트 파일만 처리
- **TODO**: PyMuPDF(`fitz`) 또는 `pdfplumber`를 이용한 PDF 청킹 지원
- **파일**: `src/defense_llm/rag/chunker.py` 또는 별도 `src/defense_llm/rag/pdf_parser.py`
- **우선순위**: P1

### 1.5 FastAPI 엔드포인트 미구현
- **현재**: 직접 파이썬 API만 있고 HTTP 엔드포인트 없음
- **TODO**: `src/defense_llm/api/` 모듈 추가 (FastAPI 라우터, OpenAPI 스펙)
- **우선순위**: P1

---

## 2. 보안 관련 미결 항목

### 2.1 ABAC 정책 파일 외부화 미완성
- **현재**: `security/rbac.py`의 `_ROLE_FIELD_PERMISSIONS`이 코드에 하드코딩
- **TODO**: YAML/JSON 정책 파일로 외부화하여 운영 시 코드 변경 없이 정책 수정 가능하도록
- **파일**: `src/defense_llm/security/policy.yaml` 추가 + 로더 구현
- **우선순위**: P1

### 2.2 출력 마스킹 패턴 확장 필요
- **현재**: 좌표, 주파수, sys_id 3가지 패턴
- **TODO**: 실제 운용 시 도메인 전문가와 협의하여 추가 마스킹 패턴 정의
- **파일**: `src/defense_llm/security/masking.py`의 `_MASK_RULES`
- **우선순위**: P2

### ~~2.3 사용자 인증/세션 관리 미구현~~ ✅ 완료
- **구현**: `src/defense_llm/security/auth.py` — `JWTAuthManager`(HS256) + `extract_user_context()`
- 환경변수 `DEFENSE_LLM_JWT_SECRET` 지원, RBAC 연동 검증
- **우선순위**: P0 → **완료**

---

## 3. 모델 서빙 관련 미결 항목

### ~~3.1 vLLM/TGI 어댑터 미구현~~ ✅ 완료 (Transformers 어댑터)
- **구현**: `src/defense_llm/serving/qwen_adapter.py` — `Qwen25Adapter`
  - `AutoModelForCausalLM` + `apply_chat_template` + lazy 로딩(thread-safe)
  - `device_map="auto"`, `torch_dtype="auto"`, `unload()` 지원
- vLLM 별도 설치(`pip install vllm`) 후 동일 인터페이스로 교체 가능
- **우선순위**: P0 → **완료**

### 3.2 Prompt Template 정교화 미완성
- **현재**: Executor에 기본 시스템 프롬프트 하드코딩
- **TODO**: `src/defense_llm/agent/prompt_templates/` 추가
  - 질의 타입별 프롬프트 템플릿 (STRUCTURED_KB, DOC_RAG, MIXED)
  - Qwen2.5-1.5B에 최적화된 지시 형식
- **우선순위**: P1

### 3.3 모델 스왑(1.5B→7B) 검증 테스트 미작성
- **현재**: 어댑터 인터페이스만 정의됨
- **TODO**: 실제 어댑터 교체 시 회귀 테스트 시나리오 추가
- **우선순위**: P1

---

## 4. 데이터 관리 미결 항목

### 4.1 문서 버전 관리(diff/rollback) 미구현
- **현재**: doc_id + doc_rev 조합으로 고유성만 보장
- **TODO**: 이전 버전 비활성화, 검색에서 최신 rev만 사용하는 로직 구현
- **우선순위**: P1

### ~~4.2 인덱스 영속성(persistence) 미구현~~ ✅ 완료
- **구현**: `DocumentIndex.save(index_dir)` / `DocumentIndex.load(index_dir)` 추가
- BM25 + DenseVectorIndex(numpy) + 메타데이터 JSON 직렬화
- **우선순위**: P0 → **완료**

### 4.3 KG(Knowledge Graph) 연동 미구현
- **현재**: 정형 DB (플랫폼/무장/제약 테이블)만 있음
- **TODO**: 호환성 관계를 그래프로 표현하여 다단계 추론 지원
- **우선순위**: P2

---

## 5. 평가(Eval) 미결 항목

### 5.1 정량 지표 미구현
- **현재**: 키워드 매칭 + citation doc_id 일치 여부만 평가
- **TODO**: ROUGE-L, BERTScore, citation precision/recall 등 정량 지표 추가
- **우선순위**: P2

### 5.2 Eval 데이터셋 확충 필요
- **현재**: `tests/fixtures/dummy_qa_samples.json`에 3개 샘플
- **TODO**: 도메인 전문가와 함께 각 QueryType별 10개 이상의 골든셋 QA 작성
- **우선순위**: P1

---

## 6. 상위 모델(7B/14B/32B) 전환 시 필요한 변경 포인트 (5개 이내)

1. **`serving/vllm_adapter.py` 신규 구현**: `AbstractLLMAdapter` 구현체 추가
2. **`config/settings.py` 모델명 변경**: `model_name` 설정값만 교체
3. **`agent/executor.py` 프롬프트 조정**: 대형 모델에 맞는 시스템 프롬프트 fine-tuning (선택)
4. **`rag/embedder.py` 임베딩 모델 교체**: 고성능 임베딩 모델로 재인덱싱 필요
5. **GPU 메모리/배치 설정**: vLLM의 `tensor_parallel_size`, `gpu_memory_utilization` 조정

---

## 7. 인프라/운영 관련 미결 항목

### 7.1 Postgres 전환 준비
- **현재**: SQLite만 지원
- **TODO**: `db_schema.py`의 `init_db()`를 SQLAlchemy로 추상화하거나, Alembic 마이그레이션 추가
- **우선순위**: P1

### 7.2 인덱스 버전 자동 관리 미구현
- **현재**: `index_version` 수동 설정
- **TODO**: 재인덱싱 시 자동으로 `idx-YYYYMMDD-hhmm` 생성 및 버전 기록
- **우선순위**: P1

### 7.3 Docker/컨테이너 배포 미포함
- **TODO**: `Dockerfile` + `docker-compose.yml` 추가
- **우선순위**: P2

---

---

## 8. [신규] LLM 주도 Tool-Use Agent 루프 — 핵심 개선 방향

> 사용자 지시: "LLM이 tool_use 커맨드를 agent에 전달 →
> agent가 적합한 도구를 실행 → 결과를 분석하여 다음 단계 결정"

### 현재 구조의 문제

```
현재 (Pipeline — LLM은 text gen만 담당):
User → Classifier(regex) → build_plan(static) → Executor(Python 직접 호출) → LLM(답변 생성)

목표 (Agent Loop — LLM이 tool 선택):
User → LLM ─[tool_call JSON]→ ToolDispatcher ─[result]→ LLM ─(반복)→ Final Answer
```

LLM이 어떤 도구를 호출할지 결정하고, 결과를 보고 후속 행동을 결정하는 **ReAct / Function-Calling 루프**가 현재 없음.

---

### 8.1 Tool Schema → LLM 주입 (P0)

- **현재**: `tool_schemas.py`에 스키마가 있으나, LLM 프롬프트에 전달되지 않음
- **TODO**: LLM에게 tool 스키마를 system prompt 또는 `tools` 파라미터로 전달
  - Qwen2.5 function-calling 포맷 지원 여부 확인 (Qwen2.5-Instruct는 지원)
  - 형식: `{"name": "search_docs", "description": "...", "parameters": {...}}`
- **파일**: `src/defense_llm/agent/executor.py`, `src/defense_llm/serving/qwen_adapter.py`
- **우선순위**: P0

### 8.2 LLM tool_call 응답 파싱 및 라우팅 (P0)

- **현재**: LLM 응답은 무조건 `content` 텍스트로만 처리
- **TODO**: LLM이 반환한 `tool_call` JSON을 파싱하여 해당 도구로 라우팅
  ```python
  # 기대 LLM 응답 구조
  {
    "tool_calls": [
      {"name": "search_docs", "arguments": {"query": "KF-21 고도", "top_k": 5}}
    ]
  }
  ```
- **파일**: `src/defense_llm/agent/executor.py` — `_dispatch_tool_call()` 신규 메서드
- **우선순위**: P0

### 8.3 Agent 루프 구현 (Observe → Think → Act → Observe …) (P0)

- **현재**: `_run_plan()`은 plan 리스트를 순차 실행 (단방향)
- **TODO**: LLM이 `FINISH` 또는 최종 답변을 생성할 때까지 루프 반복
  ```
  while not finished:
      llm_response = llm.chat(messages + tool_results)
      if llm_response.has_tool_call:
          result = execute_tool(llm_response.tool_call)
          messages.append(tool_result_message(result))
      else:
          finished = True; answer = llm_response.content
  ```
- **파일**: `src/defense_llm/agent/executor.py` — `execute()` 재구조화
- **우선순위**: P0

### 8.4 MockLLM에 tool_call 시뮬레이션 추가 (P0)

- **현재**: `MockLLMAdapter.chat()`은 항상 `content` 텍스트만 반환
- **TODO**: `response_fn`을 이용해 tool_call JSON 반환 가능하도록 확장
  ```python
  def tool_call_fn(messages):
      # 첫 번째 호출: tool_call 반환
      if is_first_call(messages):
          return {"tool_calls": [{"name": "search_docs", "arguments": {...}}]}
      # 두 번째 호출: 결과 기반 최종 답변
      return {"content": "KF-21의 최대 순항 고도는 ..."}
  ```
- **파일**: `src/defense_llm/serving/mock_llm.py`
- **우선순위**: P0

### 8.5 Rule-based Planner → LLM Intent Planner로 전환 (P1)

- **현재**: `classifier.py`는 regex 패턴 매칭
- **TODO**: 1단계 — LLM에게 intent 분류를 위임 (query → QueryType 분류 프롬프트)
  - Fallback: LLM 분류 실패 시 기존 regex 사용
  - 2단계 — Planner 자체를 LLM이 tool 선택으로 대체 (8.3과 통합)
- **파일**: `src/defense_llm/agent/planner_rules/classifier.py`
- **우선순위**: P1

### 8.6 Tool 실행 결과 구조화 및 LLM 재전달 포맷 (P0)

- **현재**: `collected_chunks`를 텍스트로 이어붙여 `context_text`로 전달
- **TODO**: tool 실행 결과를 표준 `tool_result` 메시지 포맷으로 LLM에 전달
  ```json
  {"role": "tool", "tool_call_id": "...", "content": "[문서1] KF-21 최대 고도 15,000m..."}
  ```
- **파일**: `src/defense_llm/agent/executor.py` — `_build_tool_result_message()`
- **우선순위**: P0

### 8.7 최대 루프 횟수 및 안전 종료 (P1)

- **TODO**: Agent 루프에 `max_turns` 제한 추가 (기본 5회)
  - 초과 시 `E_LOOP_LIMIT` 에러 코드 반환 + 감사 로그 기록
- **파일**: `src/defense_llm/agent/executor.py`
- **우선순위**: P1

### 8.8 보안 검증을 Tool 실행 직전에 수행 (P0)

- **현재**: `check_access()`는 `search_docs` 단계에서만 호출
- **TODO**: LLM이 tool_call을 생성한 직후, dispatch 전에 보안 검증 게이트 추가
  - LLM이 security_refusal을 호출할 수 없는 경우도 Python 레이어에서 차단
- **파일**: `src/defense_llm/agent/executor.py` — `_security_gate(tool_name, params, user_context)`
- **우선순위**: P0

---

## 우선순위 요약 (업데이트)

| 항목 | 우선순위 | 상태 |
|------|----------|------|
| ~~실제 임베딩 모델 적용~~ | ~~P0~~ | ✅ 완료 |
| ~~인덱스 영속성 구현~~ | ~~P0~~ | ✅ 완료 |
| ~~사용자 인증/세션~~ | ~~P0~~ | ✅ 완료 |
| ~~vLLM 어댑터 구현~~ | ~~P0~~ | ✅ 완료 |
| **Tool Schema → LLM 주입** | **P0** | 미착수 |
| **tool_call 응답 파싱/라우팅** | **P0** | 미착수 |
| **Agent 루프 (ReAct)** | **P0** | 미착수 |
| **MockLLM tool_call 시뮬레이션** | **P0** | 미착수 |
| **Tool 결과 LLM 재전달 포맷** | **P0** | 미착수 |
| **보안 검증 게이트 (dispatch 전)** | **P0** | 미착수 |
| LLM Intent 분류기 (Planner 대체) | P1 | 미착수 |
| Agent 루프 max_turns 제한 | P1 | 미착수 |
| FAISS 인덱스 교체 | P1 | 미착수 |
| ABAC 정책 파일 외부화 | P1 | 미착수 |
| Prompt Template 정교화 | P1 | 미착수 |
| Postgres 전환 | P1 | 미착수 |
| 출력 마스킹 패턴 확장 | P2 | 미착수 |
| KG 연동 | P2 | 미착수 |
| Docker/컨테이너 배포 | P2 | 미착수 |
