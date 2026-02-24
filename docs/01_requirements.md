# 01_requirements.md — 방산 도메인 sLLM/Agent 시스템 요구사항

> 각 요구사항은 검증 가능한 형태로 정의됩니다. 추적성 필드(UF-ID, IF-ID)는 02~04 문서 작성 후 채워집니다.

---

## REQ-001 — 설정 로딩 및 검증

- **설명**: 시스템은 시작 시 환경 설정을 로딩하고 필수 필드의 유효성을 검증해야 한다.
- **입력**: 설정 파일(YAML/환경변수), 필수 키 목록
- **출력**: 검증된 설정 객체 또는 `E_VALIDATION` 에러
- **성공 기준**: 필수 키 누락 시 예외 발생, 정상 설정 로딩 시 객체 반환
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-001 / —

---

## REQ-002 — 정형 DB 스키마 초기화

- **설명**: 시스템은 플랫폼/무장/시스템/제약 정보를 저장하는 SQLite DB를 초기화할 수 있어야 한다.
- **입력**: DB 경로, 스키마 버전
- **출력**: 초기화된 DB 파일, 스키마 버전 테이블
- **성공 기준**: 테이블 생성 확인, `schema_version` 테이블에 버전 기록
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-010 / —

---

## REQ-003 — 문서 메타데이터 등록 및 검증

- **설명**: 문서 업로드 시 필수 메타데이터(doc_id, doc_rev, field, security_label, hash)를 검증하고 등록해야 한다.
- **입력**: `{ doc_id, doc_rev, title, field, security_label, file_path }`
- **출력**: 등록된 메타데이터 레코드(DB), 무결성 해시
- **성공 기준**: 필수 필드 누락 시 `E_VALIDATION`, 중복 doc_id+rev 시 `E_CONFLICT`, 정상 등록 시 DB에 저장
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-011 / IF-001

---

## REQ-004 — Glossary(용어/약어) 매핑

- **설명**: 방산 도메인 약어를 표준 용어로 정규화하여 검색 정확도를 높여야 한다.
- **입력**: 입력 텍스트 또는 약어 키
- **출력**: 정규화된 용어 또는 정의
- **성공 기준**: 등록된 약어 조회 시 정의 반환, 미등록 약어 조회 시 `None` 반환
- **테스트 방법**: unit
- **우선순위**: P1
- **추적성**: UF-012 / —

---

## REQ-005 — 문서 청킹 및 인덱싱

- **설명**: 문서를 섹션/단락 단위로 청킹하고 BM25 및 벡터 인덱스에 등록해야 한다.
- **입력**: 문서 텍스트, 청킹 파라미터(max_tokens, overlap), doc_meta
- **출력**: 청크 목록(chunk_id, text, page, section_id, embedding), 인덱스 업데이트
- **성공 기준**: 청크 수 ≥ 1, 각 청크에 doc_id/page 포함, 인덱스에 검색 가능한 상태
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-020 / IF-001

---

## REQ-006 — 하이브리드 검색(BM25 + Vector)

- **설명**: 질의에 대해 BM25와 벡터 유사도 검색을 병행하고, 결과를 융합하여 반환해야 한다.
- **입력**: `{ query: str, field_filter: str[], security_label: str, top_k: int }`
- **출력**: `[{ chunk_id, text, score, doc_id, doc_rev, page, section_id }]`
- **성공 기준**: 결과 수 ≤ top_k, 메타 필터 적용 시 해당 field만 반환, 권한 없는 라벨 문서 미포함
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-021 / IF-001, IF-002, IF-003

---

## REQ-007 — Citation 패키징

- **설명**: 검색 결과로부터 답변 근거(citation)를 패키징해야 한다.
- **입력**: 검색 청크 목록
- **출력**: `[{ doc_id, doc_rev, page, section_id, snippet, snippet_hash }]`
- **성공 기준**: 각 citation에 doc_id, doc_rev, page(또는 section_id), snippet_hash 포함
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-022 / IF-001, IF-002

---

## REQ-008 — 규칙 기반 Planner(질의 분류)

- **설명**: 입력 질의를 규칙 기반으로 분류하고, 실행할 도구 플랜을 생성해야 한다.
- **입력**: `{ query: str, user_context: { role, clearance } }`
- **출력**: `{ query_type: QueryType, tool_plan: ToolPlan[] }`
- **성공 기준**: 5가지 QueryType 중 하나로 분류, 보안 제한 질의는 `SECURITY_RESTRICTED` 반환
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-030 / IF-001, IF-002

---

## REQ-009 — LLM Executor(도구 호출 + 검증)

- **설명**: Planner 플랜에 따라 도구를 호출하고, 스키마 검증 후 답변 템플릿을 적용해야 한다.
- **입력**: `{ tool_plan: ToolPlan[], context: dict, user_context: dict }`
- **출력**: 표준 응답 스키마(request_id, data, citations, security_label, version, hash)
- **성공 기준**: 스키마 위반 시 `E_VALIDATION`, 권한 없으면 `E_AUTH`, 정상 시 응답 반환
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-031 / IF-001, IF-002, IF-005

---

## REQ-010 — Tool Schema 검증

- **설명**: 도구 호출 입력/출력의 JSON 스키마를 검증해야 한다.
- **입력**: 도구 이름, 호출 파라미터 딕셔너리
- **출력**: 유효성 결과(True/False), 실패 시 에러 상세
- **성공 기준**: 필수 필드 누락 시 False, 타입 불일치 시 False, 정상 시 True
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-032 / IF-005

---

## REQ-011 — RBAC/ABAC 권한 검사

- **설명**: 검색 전/후 단계 모두에서 사용자 권한을 검사해야 한다.
- **입력**: `{ user: { role, clearance }, resource: { security_label, field } }`
- **출력**: `{ allowed: bool, reason: str }`
- **성공 기준**: clearance < security_label 시 `allowed=False`, 권한 있는 경우 `allowed=True`
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-040 / IF-003

---

## REQ-012 — 출력 마스킹

- **설명**: 응답 텍스트에서 좌표, 주파수, 시스템 식별자 등 민감 정보를 마스킹해야 한다.
- **입력**: 응답 텍스트, 적용 보안 정책
- **출력**: 마스킹된 텍스트
- **성공 기준**: 정규식 패턴에 매칭되는 정보는 `[REDACTED]`로 치환, 비매칭 텍스트는 원문 유지
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-041 / IF-003

---

## REQ-013 — Audit 로그 기록

- **설명**: 각 요청에 대해 request_id, 모델 버전, 인덱스 버전, citation 목록, 응답 해시를 로그로 저장해야 한다.
- **입력**: 요청/응답 객체 전체
- **출력**: DB(또는 파일)에 저장된 감사 레코드
- **성공 기준**: 로그 레코드에 request_id, model_version, index_version, citations, response_hash 모두 포함
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-050 / IF-004

---

## REQ-014 — LLM 어댑터 추상화

- **설명**: LLM 호출은 표준 어댑터 인터페이스를 통해 이루어져야 하며, mock 구현이 가능해야 한다.
- **입력**: `{ messages: [{ role, content }], model: str, max_tokens: int }`
- **출력**: `{ content: str, model: str, usage: dict }`
- **성공 기준**: Mock 어댑터로 실제 모델 없이 테스트 통과, 어댑터 교체 시 다른 레이어 변경 불필요
- **테스트 방법**: unit
- **우선순위**: P0
- **추적성**: UF-060 / —

---

## REQ-015 — Eval Runner(회귀 평가)

- **설명**: 정해진 QA 샘플에 대해 시스템을 실행하고 JSON 리포트를 생성해야 한다.
- **입력**: QA 샘플 목록(question, expected_answer, expected_citations), 시스템 구성
- **출력**: JSON 리포트(샘플별 결과, 전체 성공률)
- **성공 기준**: 리포트에 각 샘플의 pass/fail, citation 일치 여부 포함
- **테스트 방법**: unit, integration
- **우선순위**: P1
- **추적성**: UF-070 / —

---

## REQ-016 — 필드별 DB/문서 분리

- **설명**: 시스템은 air, weapon, ground, sensor, comm 필드별로 데이터를 분리 관리해야 한다.
- **입력**: 필드 식별자(`field` 파라미터)
- **출력**: 해당 필드 데이터만 포함된 검색/조회 결과
- **성공 기준**: 특정 필드 필터 적용 시 다른 필드 데이터 미포함
- **테스트 방법**: unit, integration
- **우선순위**: P1
- **추적성**: UF-011, UF-021 / IF-001, IF-002

---

## REQ-017 — 모델 서빙 어댑터 교체 가능성

- **설명**: 서빙 레이어 어댑터만 교체하면 1.5B → 7B/14B/32B 모델로 전환 가능해야 한다.
- **입력**: 새 어댑터 구현체 (동일 인터페이스)
- **출력**: 동일한 응답 스키마
- **성공 기준**: RAG/Agent/Security/Audit 레이어 코드 변경 없이 어댑터만 교체로 동작
- **테스트 방법**: unit(mock 교체 테스트)
- **우선순위**: P0
- **추적성**: UF-060 / —

---

## REQ-018 — 표준 응답 스키마 준수

- **설명**: 모든 API 응답은 표준 스키마(request_id, data, citations, security_label, version, hash)를 포함해야 한다.
- **입력**: 내부 처리 결과
- **출력**: 표준 스키마 JSON
- **성공 기준**: 응답에 6개 필수 최상위 필드 모두 존재
- **테스트 방법**: unit, integration
- **우선순위**: P0
- **추적성**: UF-031 / IF-001, IF-002, IF-003, IF-004, IF-005

---

## REQ-019 — 오프라인 테스트 재현 가능성

- **설명**: 모든 테스트는 외부 네트워크, 외부 모델 서버 없이 실행 가능해야 한다.
- **입력**: 로컬 환경(mock + SQLite + 로컬 벡터스토어)
- **출력**: pytest 전 통과
- **성공 기준**: `pytest -q` 실행 시 네트워크 없이 통과
- **테스트 방법**: integration(CI 환경)
- **우선순위**: P0
- **추적성**: — / —

---

## 추적성 매트릭스 (REQ ↔ UF ↔ IF)

| REQ-ID  | 설명 요약            | 관련 UF              | 관련 IF              |
|---------|----------------------|----------------------|----------------------|
| REQ-001 | 설정 로딩            | UF-001               | —                    |
| REQ-002 | DB 스키마 초기화     | UF-010               | —                    |
| REQ-003 | 문서 메타 등록       | UF-011               | IF-001               |
| REQ-004 | Glossary 매핑        | UF-012               | —                    |
| REQ-005 | 청킹/인덱싱          | UF-020               | IF-001               |
| REQ-006 | 하이브리드 검색      | UF-021               | IF-001, IF-002, IF-003|
| REQ-007 | Citation 패키징      | UF-022               | IF-001, IF-002       |
| REQ-008 | 규칙 기반 Planner    | UF-030               | IF-001, IF-002       |
| REQ-009 | LLM Executor         | UF-031               | IF-001, IF-002, IF-005|
| REQ-010 | Tool Schema 검증     | UF-032               | IF-005               |
| REQ-011 | RBAC/ABAC 권한       | UF-040               | IF-003               |
| REQ-012 | 출력 마스킹          | UF-041               | IF-003               |
| REQ-013 | Audit 로그           | UF-050               | IF-004               |
| REQ-014 | LLM 어댑터           | UF-060               | —                    |
| REQ-015 | Eval Runner          | UF-070               | —                    |
| REQ-016 | 필드별 분리          | UF-011, UF-021       | IF-001, IF-002       |
| REQ-017 | 어댑터 교체 가능성   | UF-060               | —                    |
| REQ-018 | 표준 응답 스키마     | UF-031               | IF-001~IF-005        |
| REQ-019 | 오프라인 테스트      | 전체                 | 전체                 |
