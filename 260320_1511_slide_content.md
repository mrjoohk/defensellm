# DefenseLLM 슬라이드 구성 자료
## 방산 특화 sLLM 에이전트 시스템 — NotebookLM 슬라이드 생성용

---

## 슬라이드 1: 타이틀

**제목:** DefenseLLM — 방산 특화 sLLM 에이전트 시스템

**부제:** Defense-Domain Small Language Model Agent · RAG · Security · Audit

**핵심 수치 (4개 강조 표시):**
- 8개 Core Modules
- 17개 Unit Functions
- 5개 Integration Scenarios
- 208개 Test Cases

**기반 기술:** Qwen2.5 · BM25 + Dense Hybrid · RBAC/ABAC · Append-Only Audit

---

## 슬라이드 2: 목차

1. 시스템 개요 — 프로젝트 배경 · 핵심 가치
2. 전체 아키텍처 — 계층 구조 · 모듈 관계
3. 핵심 기능 상세 — RAG · Agent · Security · Audit
4. 처리 흐름 — 쿼리 처리 End-to-End 시나리오
5. 테스트 & 평가 — 단위/통합 테스트 · 커버리지
6. 사용 방법 & 확장 — 설치 · 실행 · 모델 업그레이드

---

## 슬라이드 3: 시스템 개요

### DefenseLLM이란?

DefenseLLM은 방산 도메인에 특화된 sLLM(소형 언어 모델) 기반 에이전트 시스템입니다.

**주요 특징:**
- Qwen2.5 기반 (1.5B → 7B+ 확장 가능)
- 완전 오프라인 동작 (네트워크 없이 구동)
- 규칙 기반 플래너 + ReAct 에이전트 루프
- 하이브리드 검색 (BM25 + Dense Vector)
- RBAC/ABAC 이중 보안 체계
- 불변 Append-Only 감사 로그
- 어댑터 패턴으로 LLM 교체 가능

**4대 핵심 가치:**

| 가치 | 설명 |
|------|------|
| 🔒 보안 | RBAC/ABAC + 출력 마스킹 · 비밀/기밀 레벨 접근 제어 |
| 📚 지식 | 문서 청킹·색인·인용 · SHA-256 무결성 검증 |
| 🤖 에이전트 | ReAct 루프 + 툴 호출 · 규칙 기반 쿼리 분류 |
| 📋 감사 | 불변 SQLite 감사 로그 · 요청-응답 전 구간 추적 |

---

## 슬라이드 4: 전체 아키텍처

### 시스템 계층 구조 (위→아래 흐름)

```
[User Query]
     ↓
[UF-030] Rule-Based Classifier → QueryType 분류
     ↓
[UF-031] Executor (ReAct Agent Loop)  ·  [UF-032] Tool Schema Validation
     ↓                          ↓
[UF-020/021/022] RAG          [UF-010/011/012] Knowledge DB
 Chunk · BM25+Dense · Citation     SQLite
     ↓
[UF-040] RBAC/ABAC  ·  [UF-041] Output Masking  ·  [UF-050] Audit Logger
     ↓
[Standard Response Schema]
{answer · citations · security_label · version · hash}
```

### 8대 모듈 요약

| 모듈 | UF-ID | 역할 |
|------|-------|------|
| config | UF-001 | 설정 로드 · 환경변수 오버라이드 |
| knowledge | UF-010~012 | SQLite DB · 문서 등록 · 방산 용어집 |
| rag | UF-020~022 | 청킹 · 하이브리드 검색 · 인용 생성 |
| agent | UF-030~032 | 쿼리 분류 · ReAct 실행 · 툴 스키마 |
| security | UF-040~041 | RBAC/ABAC · 출력 마스킹 |
| audit | UF-050 | Append-Only 감사 로그 |
| serving | UF-060 | LLM 어댑터 (Mock / Qwen25 / vLLM) |
| eval | UF-070 | QA 패스율 평가 리포트 |

---

## 슬라이드 5: 핵심 기능 — Knowledge & RAG

### Knowledge 관리 (UF-010 ~ UF-012)

**UF-010 DB Schema**
- SQLite 테이블: documents, platforms, weapons, constraints, audit_log
- 아이디엠포턴트(idempotent) 초기화 — 중복 실행 안전

**UF-011 Document Metadata**
- 문서 등록·검증: doc_id / doc_rev / title / field / security_label / file_hash
- 중복 감지: E_CONFLICT 에러 코드

**UF-012 Glossary**
- 방산 용어 매핑 15개 이상 (KF-21, AAM, AESA 등)
- normalize_text() 메서드로 텍스트 정규화 지원

---

### RAG 파이프라인

**UF-020 Chunker**
- Heading-Aware 청킹 (H1/H2/H3 계층 추적)
- 최대 512 토큰 · 64 토큰 오버랩
- [PAGE N] 마커로 페이지 범위 추적

**UF-021 Indexer & Retriever**
- BM25 인덱스: 어휘 기반 검색 (외부 의존성 없음)
- Dense Vector 인덱스: Numpy 코사인 유사도 · L2 정규화
- DocumentIndex: BM25 + Dense 융합 (α=0.5)
- 메타데이터 필터링: field_filter, security_label_filter

**UF-022 Citation**
- doc_id / doc_rev / page_range / section_id 추출
- SHA-256 스니펫 해시로 무결성 보장
- 스니펫 최대 300자 캡

**Embedder (보조 컴포넌트)**
- Qwen25Embedder: HuggingFace Qwen2.5 · mean-pooling · L2 정규화
- TFIDFEmbedder: 경량 폴백 (테스트용)
- Lazy loading + 스레드 안전 초기화

---

## 슬라이드 6: 핵심 기능 — Agent Layer

### UF-030 Rule-Based Classifier

쿼리를 정규표현식으로 분류 (LLM 불필요)

| QueryType | 트리거 키워드 | 우선순위 |
|-----------|--------------|---------|
| SECURITY_RESTRICTED | 기밀, secret, 주파수, 암호화 | 최우선 |
| STRUCTURED_KB_QUERY | 성능, 최대속도, 무게, 제원 | 높음 |
| DOC_RAG_QUERY | 문서, 절차, 매뉴얼, 점검 | 보통 |
| MIXED_QUERY | 두 유형 복합 | 보통 |
| UNKNOWN | 매칭 없음 | 기본 |

---

### UF-031 Executor — ReAct 에이전트 루프

**두 가지 실행 모드:**
- **Pipeline 모드**: 정적 툴 플랜 실행
- **Agent 모드**: LLM 주도 ReAct 루프

**ReAct 루프 5단계:**
1. **Observe** — 시스템 프롬프트 + 쿼리 + 툴 정의 수신
2. **Think** — LLM이 tool_calls 또는 텍스트 응답 생성
3. **Act** — 툴 스키마 검증 → 보안 게이트 → 실행
4. **Result** — 결과를 'tool' 메시지로 LLM에 피드백
5. **Loop** — 텍스트 반환 또는 최대 10턴까지 반복

**사용 가능 툴:**
search_docs, query_structured_db, generate_answer, format_response, security_refusal, create_script, create_batch_script, execute_batch_script, save_results_csv

**UF-032 Tool Schema Validation**
- 각 툴별 JSON 스키마 정의
- validate_tool_call(tool_name, args) → {valid: bool, errors: list}
- OpenAI 포맷 툴 정의 생성

---

## 슬라이드 7: 핵심 기능 — 보안 체계

### UF-040 RBAC/ABAC 접근 제어

**보안 등급 계층 (숫자가 클수록 높은 등급):**
```
SECRET (3)       ████████████
RESTRICTED (2)   ██████████
INTERNAL (1)     ████████
PUBLIC (0)       ██████
```

**역할별 접근 가능 분야:**

| 역할 | 접근 분야 |
|------|---------|
| admin / analyst | 전체 분야 |
| air_analyst | air, sensor |
| weapon_analyst | weapon |
| comm_analyst | comm, sensor |
| guest | air only |

접근 로직: 사용자 clearance ≥ 리소스 보안등급 AND 역할이 해당 field 허용 시 접근

---

### UF-041 출력 마스킹

민감 정보를 [REDACTED]로 자동 치환

| 마스킹 유형 | 패턴 예시 |
|-----------|---------|
| 좌표 | 위도/경도 (DMS·십진법·한국식) |
| 주파수 | X.XX GHz / X MHz / X kHz 수치 |
| 시스템 ID | KF-21, AA-1234 형식 (대문자+숫자) |

**보안 2중 적용 흐름:**
사전 검색 필터링 (clearance · field) → 실행 → 사후 출력 마스킹

---

## 슬라이드 8: 처리 흐름 — End-to-End 예시

### 시나리오: "KF-21의 최대 속도는?"
사용자: air_analyst 역할, INTERNAL 등급

**처리 단계:**

**Step 1 — Classifier (UF-030)**
- "최대 속도" 키워드 매칭
- → QueryType: STRUCTURED_KB_QUERY

**Step 2 — 보안 게이트 (UF-040)**
- clearance INTERNAL ≥ 리소스 INTERNAL ✅
- air_analyst → air field ✅
- 접근 허용

**Step 3 — DB 쿼리 실행**
- platforms 테이블에서 KF-21 조회
- → max_speed: 1190 km/h

**Step 4 — 문서 보완 검색 (UF-021)**
- BM25 + Dense 하이브리드 검색
- → 관련 문서 청크 반환

**Step 5 — Citation 생성 (UF-022)**
- doc_id · page_range · SHA-256 해시 패키징
- 스니펫 300자 캡 적용

**Step 6 — 감사 로그 기록 (UF-050)**
- request_id · user_id · model_version · response_hash
- append-only SQLite에 불변 기록

**최종 응답:**
```json
{
  "data": { "answer": "KF-21의 최대 속도는 1190 km/h입니다." },
  "citations": [{ "doc_id": "...", "page": "3", "snippet_hash": "sha256:..." }],
  "security_label": "INTERNAL",
  "version": { "model": "qwen2.5-1.5b", "index": "idx-20260318" }
}
```

---

## 슬라이드 9: 테스트 & 평가

### 테스트 현황

| 지표 | 수치 |
|------|------|
| 총 테스트 케이스 | 208개 (100% 통과) |
| 전체 커버리지 목표 | ≥ 70% |
| 보안·감사 커버리지 목표 | ≥ 80% |
| 통합 시나리오 수 | 5개 (IF-001 ~ IF-005) |

### 단위 테스트 (tests/unit/)

각 UF별 최소 성공/실패 케이스 1쌍 이상:
- config: 로드, 검증, 환경변수 오버라이드
- knowledge: DB 스키마, 문서 등록, 용어집
- rag: 청킹, BM25/Dense 인덱스, 인용 생성
- agent: 쿼리 분류, 툴 스키마 검증
- security: RBAC 접근 제어, 출력 마스킹
- audit: 로그 쓰기, 조회, 검증
- serving: MockLLM 동작, 툴 호출 시퀀스

### 통합 테스트 (tests/integration/)

| IF-ID | 시나리오 |
|-------|---------|
| IF-001 | 문서 업로드 → 색인 → 쿼리 → 인용 응답 |
| IF-002 | 구조화 DB 쿼리 → 제약 적용 → 인용 응답 |
| IF-003 | 권한 없는 접근 → 차단 결과 확인 |
| IF-004 | 감사 로그 생성 및 검증 |
| IF-005 | 툴 스키마 위반 → 안전 실패 처리 |

**테스트 환경 조건:** SQLite 임시 DB · MockLLM · 외부 네트워크 없음

---

## 슬라이드 10: 사용 방법

### 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 테스트 실행

```bash
pytest -q                                    # 208개 테스트 실행
pytest --cov=src/defense_llm \
       --cov-report=term-missing             # 커버리지 포함
```

### 에이전트 실행 코드 예시

```python
from defense_llm.agent.executor import Executor
from defense_llm.serving.qwen_adapter import Qwen25Adapter
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger

ex = Executor(
    llm_adapter=Qwen25Adapter(model_id="Qwen/Qwen2.5-7B-Instruct"),
    index=DocumentIndex(),
    db_path="kb.db",
    audit_logger=AuditLogger("audit.db"),
    agent_mode=True,
    max_agent_turns=10,
    script_tools_enabled=True,
)

user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "u001"}
resp = ex.execute([], user, query="KF-21 속도 분석 후 결과를 CSV로 저장해줘")
```

---

## 슬라이드 11: 확장 경로 — 1.5B → 7B+ 업그레이드

### 모델 교체 시 변경 필요 사항 (4단계)

**Step 1** settings.py 업데이트
```python
model_name = "Qwen/Qwen2.5-7B-Instruct"
```

**Step 2** vLLM 어댑터로 교체
```python
VLLMAdapter(base_url="http://localhost:8000/v1")
```

**Step 3** 문서 재색인
- 고품질 임베더로 전체 문서 재색인 수행

**Step 4** vLLM 파라미터 조정
- tensor_parallel_size, gpu_memory_utilization 최적화

---

### 변경 불필요 모듈 (어댑터 패턴 덕분에)

| 모듈 | 이유 |
|------|------|
| 📚 RAG Layer | 청킹·검색·인용 로직 독립적 |
| 🤖 Agent Layer | Executor·툴 스키마 LLM 무관 |
| 🔒 Security Layer | RBAC/ABAC·마스킹 LLM 무관 |
| 📋 Audit Layer | 감사 로그 구조 불변 |
| 🗄️ Knowledge Layer | SQLite DB 구조 유지 |

---

### P1 향후 계획

- FAISS/hnswlib ANN 색인 (대용량 벡터 검색 고속화)
- PDF/DOCX 문서 파서 통합
- Knowledge Graph 관계 쿼리
- ROUGE-L · BERTScore 평가 지표 추가

---

## 슬라이드 12: 마무리

### DefenseLLM 핵심 요약

- **8개 모듈 · 17개 Unit Function · 5개 통합 시나리오 · 208개 테스트 케이스**
- BM25 + Dense Vector 하이브리드 RAG · SHA-256 인용 무결성 보장
- RBAC/ABAC 이중 보안 + 좌표·주파수·시스템ID 자동 마스킹
- 완전 오프라인 · 어댑터 패턴으로 1.5B → 7B+ 무중단 모델 교체

---

*판단 근거: 코드베이스 전수 분석(src/defense_llm 전체 모듈, tests/, docs/) 기반으로 시스템 아키텍처·기능·사용법을 NotebookLM 슬라이드 생성에 최적화된 계층적 마크다운 구조로 정리. 각 슬라이드는 제목·핵심 포인트·표/코드블록으로 구성하여 자동 슬라이드 변환 시 구조가 유지되도록 작성.*
