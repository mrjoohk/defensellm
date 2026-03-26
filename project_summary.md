# project_summary.md — Defense LLM 프로젝트 요약

최초 작성: 2026-03-03 | 최종 수정: 2026-03-25

---

## 1. 프로젝트 핵심 (Project Core)

### 1.1 목표

방산 도메인 특화 sLLM Agent 시스템 구현.
단일 GPU 온프레미스 환경에서 보안·감사 요건을 충족하는 질의응답 시스템을 제공한다.

| 항목 | 내용 |
|------|------|
| 기본 모델 | Qwen2.5-1.5B-Instruct → 7B/14B/32B 업그레이드 경로 확보 |
| 지식 소스 | RAG (하이브리드 BM25+Dense) + 정형 DB (플랫폼/무장/제약 테이블) + 방산 용어사전 |
| 보안 원칙 | 출력 마스킹(좌표/주파수/sys_id), clearance 기반 검색 필터. RBAC는 JWT 인증 레이어 추가 후 재활성화 예정 |
| 감사 원칙 | 모든 요청에 request_id·모델버전·인덱스버전·인용·응답해시 기록 (append-only SQLite) |
| 아키텍처 원칙 | Rule-based Planner + LLM Executor, 어댑터 패턴으로 모델 교체 무중단 |

### 1.2 완성 범위 (Phase 1~6 + PDF OCR)

| Phase | 산출물 | 상태 |
|-------|--------|------|
| 1 요건 형식화 | `docs/01_requirements.md` — REQ-001~020 | ✅ |
| 2 단위기능 분해 | `docs/02_unit_functions.md` — UF-001~070 전 모듈 | ✅ |
| 3 단위 테스트 | `tests/unit/` — pytest + coverage | ✅ |
| 4 통합기능 설계 | `docs/04_integration_functions.md` — IF-001~005 | ✅ |
| 5 통합 테스트 | `tests/integration/` — SQLite temp DB, MockLLM | ✅ |
| 6 Web UI | FastAPI + React/Vite (Query·Index·Audit 3개 페이지) | ✅ |
| 7 Windows 지원 | `scripts/*.bat` 배치 파일, config.yaml 모델 전환 | ✅ |
| 8 PDF OCR 지원 | `rag/pdf_parser.py` — opendataloader_pdf + pytesseract 자동 감지 | ✅ |

### 1.3 핵심 모듈 구성

| 모듈 | 주요 파일 | 역할 |
|------|-----------|------|
| config | `config/settings.py` | 환경변수 기반 설정 로드 |
| knowledge | `knowledge/db_schema.py`, `document_meta.py`, `glossary.py` | SQLite DDL, 문서 메타 등록, 방산 용어 매핑 |
| rag | `rag/chunker.py`, `indexer.py`, `retriever.py`, `embedder.py`, `citation.py`, **`pdf_parser.py`** | 청킹·인덱싱·하이브리드 검색·인용 패키징·**PDF/OCR 텍스트 추출** |
| agent | `agent/planner_rules/classifier.py`, `plan_builder.py`, `executor.py`, `tool_schemas.py` | 분류→플랜→실행→스키마 검증 |
| security | `security/rbac.py`, `masking.py`, `auth.py` | RBAC/ABAC, 출력 마스킹, JWT 인증 |
| audit | `audit/logger.py`, `schema.py` | append-only 감사 로그 |
| serving | `serving/adapter.py`, `mock_llm.py`, `qwen_adapter.py` | LLM 어댑터 인터페이스 + Qwen2.5 구현 |
| eval | `eval/runner.py` | QA pass-rate 평가 |

### 1.4 현재 동작 구조 (Pipeline)

```
User Query
  → Classifier (regex, Python)
  → build_plan() (static, Python)
  → Executor._run_plan() (Python이 직접 도구 호출)
  → LLM.chat() (검색된 컨텍스트를 받아 한국어 답변 생성)
```

LLM은 텍스트 생성 역할만 담당하며, 도구 선택·실행은 Python 코드가 결정한다.

---

## 1-A. PDF OCR 기능 상세 (2026-03-25 추가)

### 배경 및 선택 근거

방산 교범·규격서는 스캔 이미지(글자 그림) 형태로 배포되는 경우가 많다.
기존 `index` 명령은 UTF-8 텍스트 파일(.txt)만 지원하여 PDF 직접 색인이 불가능했다.

**판단 근거:**
- `@opendataloader/pdf` (npm) — Node.js 전용, 이 프로젝트는 순수 Python → **부적합**
- `opendataloader_pdf` (Python) — Java 내장 JAR로 오프라인 동작, RAG 파이프라인 최적화 → **채택**
- Java 11.0.30 (OpenJDK) 이미 시스템 설치 확인 → 추가 의존성 부담 없음
- `pytesseract` + `pdf2image` 이미 시스템에 설치 → OCR 폴백 즉시 사용 가능

### 구현 내용

| 구성요소 | 내용 |
|---------|------|
| 신규 파일 | `src/defense_llm/rag/pdf_parser.py` (UF-025) |
| 1차 추출 | `opendataloader_pdf` Java JAR로 텍스트 레이어 PDF 파싱 |
| 자동 감지 | 평균 chars/page < 50 이면 이미지 기반 PDF로 판단 |
| OCR 폴백 | `pdf2image`로 페이지 이미지 변환 → `pytesseract` OCR |
| CLI 연동 | `defense-llm index *.pdf` 자동 감지, `--ocr`, `--ocr-lang` 옵션 추가 |
| 단위 테스트 | `tests/unit/test_pdf_parser.py` — 18/18 통과 |

### 시스템 선행 요건 (시스템 설치 필요, pip 아님)

| 구성요소 | Linux (Ubuntu) | Windows |
|---------|---------------|---------|
| Java 11+ | `apt install default-jre` | https://adoptium.net/ |
| Tesseract | `apt install tesseract-ocr` | https://github.com/UB-Mannheim/tesseract/wiki |
| 한국어 팩 | `apt install tesseract-ocr-kor` | Tesseract 설치 시 kor 팩 선택 |
| Poppler | `apt install poppler-utils` | https://github.com/oschwartz10612/poppler-windows/releases/ |

### 처리 흐름

```
PDF 파일 입력
  → opendataloader_pdf (Java JAR) 텍스트 추출
      ↓ 성공 + avg chars/page ≥ 50
  → 텍스트 반환 (직접 추출)
      ↓ 실패 OR avg chars/page < 50 (이미지 기반 PDF)
  → pdf2image: PDF 페이지 → PIL Image 변환
  → pytesseract: 이미지 → 텍스트 OCR
  → [PAGE N] 마커 포함 텍스트 반환
```

---

## 2. 문제점 (Problems)

### 2.1 구조적 핵심 문제 — LLM이 Agent가 아닌 Generator로만 동작

```
목표 구조 (Agent Loop / ReAct):
[User] → [LLM] ─tool_call→ [Tool Executor] ─result→ [LLM] ─(반복)→ [Final Answer]
```

현재 구조에서 LLM은:
- plan 결정에 참여하지 않는다
- tool 실행 결과를 받아 재질의(re-query)할 수 없다
- tool_call JSON을 생성·파싱·라우팅하는 루프가 없다
- 다단계 추론(multi-step reasoning) 불가

### 2.2 단위 기능(UF) 수준 문제

| 위치 | 문제 | 영향 |
|------|------|------|
| UF-020 벡터 인덱스 | TF-IDF 코사인 유사도만 사용 (FAISS/hnswlib 미적용) | 대량 문서에서 검색 품질·속도 저하 |
| UF-030 Classifier | regex 패턴에만 의존 — 도메인 신조어·문맥적 의도 구분 불가 | MIXED_QUERY 과다 발생, DOC_RAG → UNKNOWN 오분류 |
| UF-031 Executor | `generate_answer`, `format_response` 도구가 plan에 있으나 `pass`로만 처리 | Tool-use 의미 없음, LLM에게 도구 선택권 없음 |
| UF-060 MockLLM | `fixed_response`만 반환, tool_call JSON 포맷 미지원 | 통합 테스트에서 LLM-driven tool 흐름 검증 불가 |
| UF-022 웹 검색 폴백 | `duckduckgo_search` 외부 의존, 오프라인 요구사항 위반 | 빈 청크 인덱스 추가 시도 발생 |

### 2.3 통합 기능(IF) 수준 문제

| 위치 | 문제 | 영향 |
|------|------|------|
| IF-001 인용 누락 | LLM이 "관련 문서 없음" 반환 시 `citations=[]` 강제 초기화 (executor.py:203) | 검색 성공해도 인용 소멸 |
| IF-002 DB 조회 품질 | `_query_db()`가 단순 LIKE 쿼리 — 플랫폼명 변형 처리 없음 | "KF-21" ↔ "KF21" ↔ "KF-21B" 동일 처리 불가 |
| IF-003 접근 차단 세밀도 | `check_access()`가 security_label 기준 단순 허용/거부만 수행 | 다단계 비밀등급 비교 없음 |

---

## 3. 개선 포인트 (Improvement Points)

### 3.1 P0 — LLM 주도 Tool-Use Agent 루프 (핵심 구조 전환)

> 목표: LLM이 tool_use 커맨드를 생성 → Agent가 도구를 실행 → 결과를 분석하여 다음 단계 결정

| 항목 | 작업 | 파일 |
|------|------|------|
| Tool Schema → LLM 주입 | tool 스키마를 system prompt 또는 `tools` 파라미터로 LLM에 전달 | `agent/executor.py`, `serving/qwen_adapter.py` |
| tool_call 응답 파싱·라우팅 | LLM 반환 `tool_call` JSON 파싱 → `_dispatch_tool_call()` 구현 | `agent/executor.py` |
| Agent 루프 구현 | Observe→Think→Act 반복 루프 (FINISH 신호까지) | `agent/executor.py` |
| MockLLM tool_call 시뮬레이션 | `response_fn`으로 tool_call JSON 반환 지원 | `serving/mock_llm.py` |
| Tool 결과 LLM 재전달 포맷 | `{"role":"tool","tool_call_id":"...","content":"..."}` 형식으로 표준화 | `agent/executor.py` |
| 보안 검증 게이트 | tool_call dispatch 직전 `_security_gate()` 삽입 | `agent/executor.py` |

### 3.2 P1 — RAG 품질 및 인프라 개선

| 항목 | 작업 | 파일 | 상태 |
|------|------|------|------|
| FAISS 벡터 인덱스 교체 | `SimpleVectorIndex` → `faiss-cpu` 또는 `hnswlib` ANN 인덱스 | `rag/indexer.py` | 미완 |
| BM25 라이브러리 교체 | 내장 구현 → `rank-bm25` 또는 Whoosh 연동 | `rag/indexer.py` | 미완 |
| **PDF OCR 지원** | **opendataloader_pdf(Java 엔진) + pytesseract 자동 감지** | **`rag/pdf_parser.py`** | **✅ 완료** |
| LLM Intent 분류기 | regex → LLM 위임 (실패 시 regex fallback) | `agent/planner_rules/classifier.py` | 미완 |
| Agent 루프 max_turns 제한 | 기본 5회, 초과 시 `E_LOOP_LIMIT` + 감사 로그 | `agent/executor.py` |
| Prompt Template 정교화 | QueryType별 프롬프트 템플릿 분리 | `agent/prompt_templates/` |
| ABAC 정책 외부화 | 하드코딩 → `security/policy.yaml` + 로더 | `security/rbac.py` |
| FastAPI HTTP 엔드포인트 | `src/defense_llm/api/` 모듈 추가 (OpenAPI 스펙) | `api/` (신규) |
| Postgres 전환 준비 | SQLAlchemy 추상화 또는 Alembic 마이그레이션 추가 | `knowledge/db_schema.py` |
| 인덱스 버전 자동 관리 | 재인덱싱 시 `idx-YYYYMMDD-hhmm` 자동 생성 | 인덱스 관련 모듈 |
| 모델 스왑 검증 테스트 | 1.5B→7B 교체 시 회귀 테스트 시나리오 | `tests/` |
| Eval 데이터셋 확충 | 각 QueryType별 골든셋 QA 10개 이상 | `tests/fixtures/` |

### 3.3 P2 — 고도화 및 운영 편의

| 항목 | 작업 |
|------|------|
| 출력 마스킹 패턴 확장 | 도메인 전문가 협의하여 추가 마스킹 패턴 정의 |
| KG(Knowledge Graph) 연동 | 호환성 관계를 그래프로 표현하여 다단계 추론 지원 |
| Docker/컨테이너 배포 | `Dockerfile` + `docker-compose.yml` 추가 |
| 정량 평가 지표 | ROUGE-L, BERTScore, citation precision/recall 도입 |
| 문서 버전 관리 | 이전 버전 비활성화, 검색에서 최신 rev만 사용 |

### 3.4 상위 모델(7B/14B/32B) 전환 체크리스트

1. `serving/vllm_adapter.py` 신규 구현 — `AbstractLLMAdapter` 구현체 추가
2. `config/settings.py` `model_name` 값 교체
3. `agent/executor.py` 시스템 프롬프트 fine-tuning (선택)
4. `rag/embedder.py` 고성능 임베딩 모델로 재인덱싱
5. vLLM `tensor_parallel_size`, `gpu_memory_utilization` 조정

---

## 4. 현재 상태 요약

| 영역 | 현황 | 비고 |
|------|------|------|
| RAG 검색 | TF-IDF 코사인 유사도 + BM25 | FAISS 미적용 |
| 임베딩 | Qwen25Embedder + TFIDFEmbedder(테스트 폴백) | ✅ 실 임베딩 적용 |
| LLM 연동 | Qwen2.5-1.5B (transformers) | function-calling 미사용 |
| Agent 루프 | 없음 (단방향 Pipeline) | LLM은 text gen만 담당 |
| Tool 라우팅 | Python 코드 하드코딩 | LLM tool_call 파싱 없음 |
| 인증 | JWTAuthManager (HS256) | ✅ 완료 |
| 보안 강제 | clearance 기반 인덱스 필터 작동 | RBAC 비활성화 (JWT 인증 레이어 추가 후 재활성화 예정) |
| 인덱스 영속성 | `save()` / `load()` 구현 | ✅ 완료 |
| Web UI | FastAPI + React (작동) | 실 모델 응답 연동됨. field 필터 칩 제거, role 배지 단순화 |
| field 분류 | "general" 단일 사용 중 | 규모 확장 시 air/weapon/ground/sensor/comm 부여 예정 |
| Windows 실행 | `scripts/*.bat` 지원 | `start_all.bat` → API+UI 동시 실행 |
| 모델 전환 | `config.yaml` `model_name` 수정 | 1.5B / 7B / 14B 전환 지원 |
| 테스트 | unit + integration (pytest) | MockLLM, SQLite temp DB |
| PDF 문서 ingest | `rag/pdf_parser.py` | ✅ 완료 (opendataloader_pdf + pytesseract OCR) |
| PDF OCR 자동 감지 | 평균 chars/page < 50 → OCR 자동 전환 | ✅ 완료 |
