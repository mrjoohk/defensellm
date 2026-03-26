# todo.md — 미결/유보 항목 및 향후 작업

이 파일은 현재 MVP 구현에서 의도적으로 생략하거나 TODO로 남긴 항목을 정리합니다.

최종 수정: 2026-03-26

---

## 0. P0 — LLM 주도 Tool-Use Agent 루프 (핵심 구조 전환) ⚠️ 신규

> 목표: LLM이 tool_use 커맨드를 생성 → Agent가 도구를 실행 → 결과를 분석하여 다음 단계 결정

현재 구조는 Python 코드가 tool을 하드코딩 실행하며, LLM은 텍스트 생성 역할만 담당.
목표 구조(ReAct / Agent Loop)로 전환이 필요하다.

### ~~0.1 Tool Schema → LLM 주입~~ ✅ 완료 (2026-03-26 확인)
- **구현**: `tool_schemas.py::get_tool_definitions_for_llm()` + `executor.py::_run_agent_loop()` line 204에서 `tool_defs` 주입
- **파일**: `src/defense_llm/agent/executor.py`, `src/defense_llm/agent/tool_schemas.py`
- **우선순위**: P0 → **완료**

### ~~0.2 tool_call 응답 파싱·라우팅~~ ✅ 완료 (2026-03-26 확인)
- **구현**: `executor.py::_dispatch_tool()` (line 286~391) — tool_name 기반 라우팅, PermissionError/Exception 핸들링 포함
- **파일**: `src/defense_llm/agent/executor.py`
- **우선순위**: P0 → **완료**

### ~~0.3 Agent 루프 (Observe→Think→Act)~~ ✅ 완료 (2026-03-26 확인)
- **구현**: `executor.py::_run_agent_loop()` (line 175~284); `max_turns=10`, 초과 시 `E_LOOP_LIMIT` + 감사 로그
- **파일**: `src/defense_llm/agent/executor.py`
- **우선순위**: P0 → **완료**

### ~~0.4 MockLLM tool_call 시뮬레이션~~ ✅ 완료 (2026-03-26 확인)
- **구현**: `mock_llm.py::tool_call_sequence` — 턴별 tool_call JSON 또는 None 반환, `response_fn` dict 반환도 지원
- **테스트**: `tests/unit/test_mock_llm_tool_calls.py` 6케이스 통과
- **파일**: `src/defense_llm/serving/mock_llm.py`
- **우선순위**: P0 → **완료**

### ~~0.5 Tool 결과 LLM 재전달 포맷~~ ✅ 완료 (2026-03-26 확인)
- **구현**: `executor.py` line 266~272: `{"role":"tool","tool_call_id":"...","content":"..."}` 형식으로 messages에 append
- **파일**: `src/defense_llm/agent/executor.py`
- **우선순위**: P0 → **완료**

### 0.6 보안 검증 게이트
- **TODO**: tool_call dispatch 직전 `_security_gate()` 삽입 (RBAC 재활성화 연계)
- **파일**: `src/defense_llm/agent/executor.py`
- **우선순위**: P3 (테스트 단계 — 인증/보안 영역 비활성화 기간 동안 후순위)

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

### ~~1.4 PDF 파싱 미구현~~ ✅ 완료 (2026-03-25)
- **구현**: `src/defense_llm/rag/pdf_parser.py` (UF-025)
  - `opendataloader_pdf` (Java 내장 JAR) — 텍스트 레이어 PDF 고품질 추출
  - `pytesseract` + `pdf2image` — 이미지 기반(스캔) PDF OCR 폴백
  - 평균 50자/페이지 미만 시 OCR 자동 전환, `--ocr` / `--ocr-lang` CLI 옵션
  - 단위 테스트 18/18 통과
- **선행 요건**: Java 11+, Tesseract, Poppler (시스템 설치 필요)
- **우선순위**: P1 → **완료**

### 1.5 FastAPI 엔드포인트 미구현
- **현재**: 직접 파이썬 API만 있고 HTTP 엔드포인트 없음
- **TODO**: `src/defense_llm/api/` 모듈 추가 (FastAPI 라우터, OpenAPI 스펙)
- **우선순위**: P1

### 1.6 LLM Intent 분류기 미구현 ⚠️ 신규
- **현재**: `agent/planner_rules/classifier.py` — regex 패턴에만 의존 (도메인 신조어·문맥적 의도 구분 불가, MIXED_QUERY 과다 발생)
- **TODO**: LLM에 분류를 위임하고 실패 시 regex fallback 구조로 전환
- **파일**: `src/defense_llm/agent/planner_rules/classifier.py`
- **우선순위**: P1

---

## 2. 보안 관련 미결 항목

> **[테스트 단계 방침]** 인증/보안 영역 기능은 현재 비활성화 상태를 유지한다.
> - RBAC 체크: `executor.py` lines 308–316, 422–428 — 주석 처리됨 (의도적)
> - JWT 인증: `JWTAuthManager` 구현 완료되었으나 파이프라인 미연동 (의도적)
> - 아래 항목들은 테스트 완료 후 재활성화 예정 → 모두 P3(후순위)

### 2.1 RBAC 재활성화 (테스트 완료 후)
- **현재**: `executor.py` `search_docs` 처리 시 `check_access()` 호출 주석 처리됨
- **상태**: JWT(`security/auth.py`) 완료, executor 연동만 남음
- **TODO**:
  1. CLI `query` / FastAPI에서 JWT 토큰 추출 → `extract_user_context()` 호출
  2. `executor.py` RBAC 주석 해제 (`check_access()` 호출 복원)
  3. `_security_gate()` 구현(항목 0.6)과 연계
- **파일**: `src/defense_llm/agent/executor.py`, `src/defense_llm/security/auth.py`, `src/defense_llm/cli.py`
- **우선순위**: P3 (테스트 단계 종료 후 재활성화)

### 2.2 ABAC 정책 파일 외부화 미완성
- **현재**: `security/rbac.py`의 `_ROLE_FIELD_PERMISSIONS`이 코드에 하드코딩
- **TODO**: YAML/JSON 정책 파일로 외부화하여 운영 시 코드 변경 없이 정책 수정 가능하도록
- **파일**: `src/defense_llm/security/policy.yaml` 추가 + 로더 구현
- **우선순위**: P3 (테스트 단계 — RBAC 재활성화 후 진행)

### 2.3 출력 마스킹 패턴 확장 필요
- **현재**: 좌표, 주파수, sys_id 3가지 패턴
- **TODO**: 실제 운용 시 도메인 전문가와 협의하여 추가 마스킹 패턴 정의
- **파일**: `src/defense_llm/security/masking.py`의 `_MASK_RULES`
- **우선순위**: P3

### ~~2.4 사용자 인증/세션 관리 미구현~~ ✅ 완료
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

## 우선순위 요약

| 항목 | 우선순위 | 필요 시점 |
|------|----------|-----------|
| ~~실제 임베딩 모델 적용~~ | ~~P0~~ | ✅ 완료 (`rag/embedder.py`) |
| ~~인덱스 영속성 구현~~ | ~~P0~~ | ✅ 완료 (`DocumentIndex.save/load`) |
| ~~사용자 인증/세션~~ | ~~P0~~ | ✅ 완료 (`security/auth.py`) |
| ~~vLLM 어댑터 구현~~ | ~~P0~~ | ✅ 완료 (`serving/qwen_adapter.py`) |
| ~~PDF 파싱 + OCR~~ | ~~P1~~ | ✅ 완료 (`rag/pdf_parser.py`) — 2026-03-25 |
| ~~LLM Tool-Use Agent 루프 (0.1~0.5)~~ | ~~P0~~ | ✅ 완료 (2026-03-26 구현 확인) |
| FAISS 인덱스 교체 | P1 | 성능 요구 시 |
| LLM Intent 분류기 (1.6) | P1 | Agent 루프 전환 후 |
| FastAPI 엔드포인트 | P1 | HTTP API 필요 시 |
| Postgres 전환 | P1 | 운영 규모 확대 시 |
| KG 연동 | P2 | 고급 추론 필요 시 |
| Docker 배포 | P2 | 운영 환경 구성 시 |
| RBAC 재활성화 (2.1) | P3 | 테스트 단계 종료 후 |
| ABAC 정책 외부화 (2.2) | P3 | RBAC 재활성화 후 |
| 출력 마스킹 패턴 확장 (2.3) | P3 | 도메인 전문가 협의 후 |
| 보안 검증 게이트 (0.6) | P3 | 테스트 단계 종료 후 |
