# Defense-LLM CLI 사용 매뉴얼

> **대상**: 방산 도메인 sLLM/Agent 시스템 운용자 및 분석관
> **버전**: 0.1.0 | **모델**: Qwen2.5-1.5B-Instruct (확장 가능)

---

## 목차

1. [개요](#1-개요)
2. [설치 및 환경 설정](#2-설치-및-환경-설정)
3. [명령 구조](#3-명령-구조)
4. [명령 상세](#4-명령-상세)
   - 4.1 [db init — DB 초기화](#41-db-init--db-초기화)
   - 4.2 [index — 문서 색인](#42-index--문서-색인)
   - 4.3 [query — 질의응답](#43-query--질의응답)
   - 4.4 [eval — 정확도 평가](#44-eval--정확도-평가)
   - 4.5 [config check — 설정 검증](#45-config-check--설정-검증)
5. [환경 변수](#5-환경-변수)
6. [사용 시나리오](#6-사용-시나리오)
7. [보안 등급 체계](#7-보안-등급-체계)
8. [표준 응답 스키마](#8-표준-응답-스키마)
9. [오류 코드](#9-오류-코드)
10. [자주 묻는 질문](#10-자주-묻는-질문)

---

## 1. 개요

`defense-llm`은 방산 도메인 지식베이스를 기반으로 자연어 질의응답을 수행하는
규칙 기반 에이전트 시스템의 CLI 도구입니다.

**주요 기능**

| 기능 | 설명 |
|------|------|
| 문서 색인 | 텍스트 파일을 청킹하여 BM25 + 벡터 하이브리드 인덱스에 등록 |
| 자연어 질의 | 규칙 기반 Planner → LLM Executor → 근거 인용 답변 |
| 보안 접근 제어 | RBAC/ABAC 기반 허가 등급별 문서 접근 필터링 |
| 감사 로그 | 모든 요청에 대해 request_id / 모델버전 / citation 자동 저장 |
| 회귀 평가 | QA 샘플셋 기반 정확도 리포트 생성 |
| 오프라인 동작 | `--mock` 플래그로 실제 GPU/모델 없이 전체 파이프라인 테스트 |

---

## 2. 설치 및 환경 설정

### 2.1 패키지 설치

```bash
# conda 환경 활성화
conda activate defensellm

# 패키지 설치 (개발 모드)
pip install -e ".[dev]"
```

설치 후 `defense-llm` 명령을 바로 사용할 수 있습니다.

```bash
defense-llm --version
# defense-llm, version 0.1.0
```

### 2.2 데이터 디렉토리 구성

CLI는 기본적으로 다음 경로를 사용합니다. 환경변수 또는 옵션으로 변경 가능합니다.

```
./data/
  defense.db      ← SQLite DB (문서 메타, 감사 로그, 플랫폼 제원)
  index/          ← 검색 인덱스 (BM25 + 벡터)
./logs/           ← 로그 디렉토리 (향후 확장)
```

---

## 3. 명령 구조

```
defense-llm
├── db
│   └── init                데이터베이스 초기화
├── index  <파일>            문서 색인
├── query  <질문>            자연어 질의응답
├── eval                    QA 정확도 평가
└── config
    └── check               설정 검증
```

모든 명령에서 `--help` 플래그로 상세 도움말을 확인할 수 있습니다.

```bash
defense-llm query --help
```

---

## 4. 명령 상세

### 4.1 `db init` — DB 초기화

데이터베이스 파일을 생성하고 필수 테이블을 초기화합니다.
이미 초기화된 DB에 재실행해도 안전합니다(idempotent).

**구문**

```bash
defense-llm db init [옵션]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--db-path` | `./data/defense.db` | SQLite DB 파일 경로 |

**예시**

```bash
# 기본 경로에 DB 초기화
defense-llm db init

# 사용자 지정 경로
defense-llm db init --db-path /opt/defense/db/main.db
```

**출력 예시**

```
DB 초기화 중: ./data/defense.db
✓ DB 초기화 완료
  생성된 테이블: schema_version, documents, platforms, weapons, constraints, audit_log
```

---

### 4.2 `index` — 문서 색인

텍스트 파일을 읽어 메타데이터를 등록하고, 청킹 후 인덱스에 추가합니다.

**구문**

```bash
defense-llm index <파일경로> [옵션]
```

**인수**

| 인수 | 설명 |
|------|------|
| `<파일경로>` | 색인할 텍스트 파일 경로 (UTF-8) |

**옵션**

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--doc-id` | ✓ | — | 문서 고유 ID (예: `DOC-001`) |
| `--doc-rev` | | `v1.0` | 문서 버전 |
| `--title` | | 파일명 | 문서 제목 |
| `--field` | ✓ | — | 도메인 필드: `air` \| `weapon` \| `ground` \| `sensor` \| `comm` |
| `--security-label` | | `INTERNAL` | 보안 등급: `PUBLIC` \| `INTERNAL` \| `RESTRICTED` \| `SECRET` |
| `--max-tokens` | | `256` | 청크당 최대 토큰 수 |
| `--overlap` | | `32` | 청크 간 중복 토큰 수 |
| `--db-path` | | `./data/defense.db` | DB 경로 |
| `--index-path` | | `./data/index` | 인덱스 저장 디렉토리 |

**예시**

```bash
# 항공 도메인 교범 색인
defense-llm index docs/kf21_manual.txt \
  --doc-id DOC-KF21-001 \
  --doc-rev v2.1 \
  --title "KF-21 운용 교범" \
  --field air \
  --security-label INTERNAL

# 소규모 청킹 (짧은 문서)
defense-llm index docs/quick_ref.txt \
  --doc-id DOC-REF-001 \
  --field weapon \
  --max-tokens 128 --overlap 16
```

**출력 예시**

```
문서 등록: docs/kf21_manual.txt
  doc_id=DOC-KF21-001, rev=v2.1, field=air, label=INTERNAL
  ✓ 메타데이터 등록 완료
  청크 수: 47
  ✓ 인덱싱 완료 → ./data/index (전체 청크: 47)
```

> **주의**: `--doc-id`와 `--doc-rev` 조합이 이미 등록된 경우 경고가 출력되고 인덱싱은 계속됩니다.
> 새 버전 문서는 `--doc-rev v2.0` 처럼 다른 버전 번호를 사용하십시오.

---

### 4.3 `query` — 질의응답

자연어 질문을 처리하고 인용 출처가 포함된 답변을 반환합니다.

**구문**

```bash
defense-llm query "<질문>" [옵션]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--role` | `analyst` | 사용자 역할 (RBAC) |
| `--clearance` | `INTERNAL` | 허가 등급 (`PUBLIC` \| `INTERNAL` \| `RESTRICTED` \| `SECRET`) |
| `--field` | 전체 | 검색 도메인 필터 (복수 지정 가능) |
| `--top-k` | `5` | 검색 결과 최대 수 |
| `--mock` | — | MockLLMAdapter 사용 (모델 없이 테스트) |
| `--model-id` | `Qwen/Qwen2.5-1.5B-Instruct` | 모델 ID 또는 로컬 경로 |
| `--show-citations` | — | 응답에 인용 출처 표시 |
| `--json-output` | — | 결과를 JSON 형식으로 출력 |
| `--db-path` | `./data/defense.db` | DB 경로 |
| `--index-path` | `./data/index` | 인덱스 경로 |

**예시**

```bash
# 기본 질의 (모델 로딩 필요)
defense-llm query "KF-21의 최대 순항 고도는?"

# 모의 응답 + 인용 출처 표시
defense-llm query "정비 주기 기준" --mock --show-citations

# 특정 도메인만 검색
defense-llm query "미사일 탑재 제한 중량" \
  --field weapon --clearance INTERNAL --show-citations

# JSON 형식 출력 (파이프라인 연동)
defense-llm query "비상 절차" --mock --json-output | python -m json.tool

# SECRET 허가 등급으로 질의
defense-llm query "제한 구역 제원" \
  --role admin --clearance SECRET --show-citations
```

**일반 출력 예시**

```
────────────────────────────────────────────────────
질문:
  KF-21의 최대 순항 고도는?

답변:
  KF-21 항공기의 최대 순항 고도는 15,000m입니다.
  이는 운용 교범 제1장 일반 제원에 명시된 수치입니다.

인용 출처:
  [1] DOC-KF21-001 rev=v2.1 p.1 — KF-21 항공기의 최대 순항 고도는…
  [2] DOC-KF21-001 rev=v2.1 p.3 — 운용 고도 제한 사항…
────────────────────────────────────────────────────

  request_id: 4a8f2b91-…
  model: Qwen/Qwen2.5-1.5B-Instruct  index: idx-20260224-0900
  security_label: INTERNAL
```

**JSON 출력 예시** (`--json-output`)

```json
{
  "request_id": "4a8f2b91-3c2d-...",
  "data": {
    "answer": "KF-21 항공기의 최대 순항 고도는 15,000m입니다."
  },
  "citations": [
    {
      "doc_id": "DOC-KF21-001",
      "doc_rev": "v2.1",
      "page": 1,
      "section_id": "sec-0003",
      "snippet": "최대 순항 고도는 15,000m입니다...",
      "snippet_hash": "a3f8c2..."
    }
  ],
  "security_label": "INTERNAL",
  "version": {
    "model": "Qwen/Qwen2.5-1.5B-Instruct",
    "index": "idx-20260224-0900",
    "db": "schema-v1"
  },
  "hash": "d4e5f6..."
}
```

---

### 4.4 `eval` — 정확도 평가

준비된 QA 샘플셋을 시스템에 실행하고 통과율과 citation 일치율을 평가합니다.

**구문**

```bash
defense-llm eval [옵션]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--samples` | `tests/fixtures/dummy_qa_samples.json` | QA 샘플 JSON 파일 |
| `--output` | `eval_report.json` | 리포트 저장 경로 |
| `--mock` | — | MockLLMAdapter 사용 |
| `--model-id` | `Qwen/Qwen2.5-1.5B-Instruct` | 모델 ID |
| `--db-path` | `./data/defense.db` | DB 경로 |
| `--index-path` | `./data/index` | 인덱스 경로 |

**QA 샘플 파일 형식** (`JSON 배열`)

```json
[
  {
    "id": "QA-001",
    "question": "DUMMY-F1 항공기의 최대 순항 고도는?",
    "expected_answer_keywords": ["15000"],
    "expected_citation_doc_ids": ["DOC-AIR-001"]
  },
  {
    "id": "QA-002",
    "question": "정비 기본 점검 주기는?",
    "expected_answer_keywords": ["50"],
    "expected_citation_doc_ids": ["DOC-AIR-001"]
  }
]
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `id` | ✓ | 샘플 식별자 |
| `question` | ✓ | 질문 텍스트 |
| `expected_answer_keywords` | | 답변에 포함되어야 할 키워드 목록 |
| `expected_citation_doc_ids` | | 응답 citation에 포함되어야 할 doc_id 목록 |

**예시**

```bash
# Mock 어댑터로 오프라인 평가
defense-llm eval --mock \
  --samples tests/fixtures/dummy_qa_samples.json \
  --output reports/eval_20260224.json

# 실제 모델로 평가
defense-llm eval \
  --samples qa_goldenset.json \
  --output reports/production_eval.json
```

**출력 예시**

```
평가 실행 중 (3개 샘플)…

────────────────────────────────────────────────────
평가 결과:
  전체: 3  통과: 2  실패: 1
  통과율: 66.7%

  ✓ [QA-001] 인용OK  OK
  ✓ [QA-002] 인용OK  OK
  ✗ [QA-003] 인용없음  keyword_pass=False, citation_match=False
────────────────────────────────────────────────────

  리포트 저장: eval_report.json
```

---

### 4.5 `config check` — 설정 검증

현재 설정값을 검증하고 요약합니다. 운용 환경 배포 전 확인용으로 사용합니다.

**구문**

```bash
defense-llm config check [옵션]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--model-name` | `Qwen/Qwen2.5-1.5B-Instruct` | 모델 이름 |
| `--db-path` | `./data/defense.db` | DB 경로 |
| `--index-path` | `./data/index` | 인덱스 경로 |
| `--log-path` | `./data/logs` | 로그 경로 |
| `--security-level` | `INTERNAL` | 시스템 기본 보안 등급 |

**예시**

```bash
# 환경변수 기반 검증
export DEFENSE_LLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"
export DEFENSE_LLM_DB_PATH="/opt/defense/db/main.db"
defense-llm config check

# 인자 직접 지정
defense-llm config check \
  --model-name Qwen/Qwen2.5-1.5B-Instruct \
  --security-level RESTRICTED
```

**출력 예시**

```
설정 검증 중…
✓ 설정이 유효합니다

  model_name           Qwen/Qwen2.5-1.5B-Instruct
  db_path              ./data/defense.db
  index_path           ./data/index
  log_path             ./data/logs
  security_level       INTERNAL
  chunk_max_tokens     256
  top_k                5
```

---

## 5. 환경 변수

CLI 옵션보다 환경변수를 통한 설정이 권장됩니다. 운용 환경 `.env` 파일에 정의하십시오.

| 환경변수 | CLI 대응 옵션 | 예시값 |
|----------|--------------|--------|
| `DEFENSE_LLM_MODEL_NAME` | `--model-id` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `DEFENSE_LLM_DB_PATH` | `--db-path` | `/opt/defense/db/main.db` |
| `DEFENSE_LLM_INDEX_PATH` | `--index-path` | `/opt/defense/index` |
| `DEFENSE_LLM_LOG_PATH` | `--log-path` | `/var/log/defense-llm` |
| `DEFENSE_LLM_JWT_SECRET` | — | `your-32-char-secret-key-here!!` |

**`.env` 파일 예시**

```dotenv
DEFENSE_LLM_MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct
DEFENSE_LLM_DB_PATH=./data/defense.db
DEFENSE_LLM_INDEX_PATH=./data/index
DEFENSE_LLM_LOG_PATH=./data/logs
DEFENSE_LLM_JWT_SECRET=your-minimum-32-character-jwt-secret-key
```

> **주의**: `.env` 파일은 반드시 `.gitignore`에 추가하고, 저장소에 커밋하지 마십시오.

---

## 6. 사용 시나리오

### 시나리오 A — 처음 시스템 구성 (Mock 환경)

```bash
# 1. DB 초기화
defense-llm db init

# 2. 테스트 문서 색인
defense-llm index tests/fixtures/dummy_doc_air.txt \
  --doc-id DOC-AIR-001 --field air --security-label INTERNAL

# 3. 설정 검증
defense-llm config check

# 4. 질의 테스트 (Mock LLM)
defense-llm query "최대 순항 고도는?" --mock --show-citations

# 5. 평가 실행
defense-llm eval --mock
```

### 시나리오 B — 실제 모델 운용

```bash
# 1~3은 동일

# 4. 실제 모델로 질의 (첫 실행 시 모델 다운로드 진행)
defense-llm query "KF-21 정비 절차" \
  --role analyst \
  --clearance INTERNAL \
  --field air \
  --show-citations

# 5. JSON 출력으로 외부 시스템 연동
defense-llm query "무장 호환성" \
  --clearance INTERNAL \
  --json-output > response.json
```

### 시나리오 C — 복수 문서 색인

```bash
for file in docs/manuals/*.txt; do
  doc_id="DOC-$(basename $file .txt | tr '[:lower:]' '[:upper:]')"
  defense-llm index "$file" \
    --doc-id "$doc_id" \
    --field air \
    --security-label INTERNAL
done
```

### 시나리오 D — 보안 등급 제한 확인

```bash
# SECRET 문서 색인
defense-llm index docs/classified.txt \
  --doc-id DOC-CLASSIFIED-001 \
  --field air \
  --security-label SECRET

# PUBLIC 사용자 — 결과 0건 반환됨
defense-llm query "기밀 내용" \
  --role guest \
  --clearance PUBLIC \
  --show-citations

# SECRET 허가 사용자 — 정상 응답
defense-llm query "기밀 내용" \
  --role admin \
  --clearance SECRET \
  --show-citations
```

---

## 7. 보안 등급 체계

### 허가 등급(Clearance) 계층

```
PUBLIC < INTERNAL < RESTRICTED < SECRET
  0         1           2           3
```

- 상위 등급 사용자는 하위 등급 문서에 자동으로 접근 가능합니다.
- 사용자 등급이 문서 등급보다 낮으면 검색 결과에서 자동 제외됩니다.

### 역할(Role)별 접근 필드

| 역할 | 접근 가능 도메인 |
|------|----------------|
| `admin` | air, weapon, ground, sensor, comm |
| `analyst` | air, weapon, ground, sensor, comm |
| `air_analyst` | air, sensor |
| `weapon_analyst` | weapon |
| `ground_analyst` | ground |
| `comm_analyst` | comm, sensor |
| `guest` | air |

> 필드 접근은 `--role` 옵션으로 지정하며, 실제 운용 환경에서는 JWT 토큰으로 역할이 결정됩니다.

---

## 8. 표준 응답 스키마

`--json-output` 시 반환되는 JSON의 최상위 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `request_id` | UUID | 요청 고유 식별자 |
| `data.answer` | string | LLM 생성 답변 텍스트 |
| `citations` | array | 근거 문서 인용 목록 |
| `citations[].doc_id` | string | 문서 ID |
| `citations[].doc_rev` | string | 문서 버전 |
| `citations[].page` | int | 페이지 번호 |
| `citations[].snippet` | string | 관련 텍스트 발췌 (최대 300자) |
| `citations[].snippet_hash` | SHA-256 | 발췌 무결성 해시 |
| `security_label` | string | 응답 보안 등급 |
| `version.model` | string | 사용된 모델 |
| `version.index` | string | 인덱스 버전 |
| `version.db` | string | DB 스키마 버전 |
| `hash` | SHA-256 | 응답 전체 무결성 해시 |
| `error` | string | 오류 발생 시 오류 코드 |

---

## 9. 오류 코드

| 코드 | 원인 | 대응 방법 |
|------|------|-----------|
| `E_AUTH` | 허가 등급 부족 또는 보안 제한 질의 | `--clearance` 값 상향 또는 질의 내용 수정 |
| `E_VALIDATION` | Tool schema 위반 또는 잘못된 입력 | 입력값 형식 확인 |
| `E_CONFLICT` | 동일 doc_id + doc_rev 중복 등록 | `--doc-rev` 버전 번호 변경 |
| `E_INTERNAL` | 내부 처리 오류 | 로그 확인 후 재시도 |

---

## 10. 자주 묻는 질문

**Q. 모델을 처음 실행할 때 시간이 오래 걸립니다.**

A. `Qwen/Qwen2.5-1.5B-Instruct` 모델을 HuggingFace Hub에서 최초 다운로드 시
약 3~5GB 파일이 `~/.cache/huggingface/hub/`에 저장됩니다.
이후 실행부터는 로컬 캐시를 사용합니다.

---

**Q. GPU 없이 사용할 수 있나요?**

A. `--mock` 플래그를 사용하면 실제 모델 없이 전체 파이프라인을 테스트할 수 있습니다.
실제 모델 추론은 CPU에서도 동작하지만 속도가 매우 느립니다.

---

**Q. 기존 인덱스에 문서를 추가할 수 있나요?**

A. 가능합니다. `defense-llm index` 명령을 반복 실행하면 기존 인덱스에 청크가 추가됩니다.
단, 동일한 `--doc-id`와 `--doc-rev` 조합은 중복 경고가 표시됩니다.

---

**Q. 응답에 인용 출처가 없는 경우는 언제인가요?**

A. 아래 상황에서 `citations` 가 빈 배열로 반환됩니다.
- 색인된 문서가 없을 때
- 사용자 허가 등급이 부족하여 관련 문서가 필터링될 때
- 질의와 유사도가 높은 청크가 없을 때
- `SECURITY_RESTRICTED` 질의로 보안 거절될 때 (`error: E_AUTH`)

---

**Q. 7B 이상의 모델로 업그레이드하려면 어떻게 하나요?**

A. `--model-id` 옵션(또는 `DEFENSE_LLM_MODEL_NAME` 환경변수)만 변경하면 됩니다.
RAG, 보안, 감사 레이어는 수정이 필요 없습니다.

```bash
# 7B 모델로 전환 예시
defense-llm query "질문" --model-id Qwen/Qwen2.5-7B-Instruct
```

자세한 업그레이드 포인트는 [todo.md](../todo.md) 6절을 참고하십시오.
