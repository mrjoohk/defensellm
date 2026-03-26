# LLM Tool-Use Agent Loop (0.1~0.5) — 전환 필요성 및 설계 분석

**작성일**: 2026-03-26
**작성자**: Defense-LLM Agent
**대상 요청**: todo.md P0 항목 "LLM 주도 Tool-Use Agent 루프" 우선 전환 설계

---

## 1. 현황 진단: Pipeline 모드 vs Agent 루프 모드

### 1.1 현재 구조 (Pipeline 모드, `_run_plan()`)

```
User Query
    │
    ▼
Planner (rule-based classifier → plan_builder)
    │  Python 코드가 tool 순서를 하드코딩 결정
    ▼
[search_docs] → [query_structured_db] → [generate_answer]
    │  각 도구를 Python이 순차 실행
    ▼
LLM  ← 수집된 context를 한 번에 주입받아 텍스트만 생성
    │
    ▼
Response
```

**구조적 한계:**
- LLM은 "정보 생성기" 역할에 한정 — 도구 선택권이 없음
- 플래너가 틀리면 전체 흐름이 잘못된 방향으로 고정
- 멀티-홉 추론(예: A문서 검색 → 결과 기반으로 B DB 조회) 불가
- 새 도구 추가 시 플래너 regex 패턴도 함께 수정 필요 (강결합)

### 1.2 목표 구조 (LLM Tool-Use Agent 루프, `_run_agent_loop()`)

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│  LLM (tool schemas 주입됨)           │
│                                     │
│  Observe: tool 결과 메시지 수신       │
│  Think:   다음 action 결정          │
│  Act:     tool_call JSON 반환       │
└──────────────┬──────────────────────┘
               │ tool_calls 있으면
               ▼
        _dispatch_tool()
               │
    ┌──────────┴──────────┐
    │                     │
search_docs    query_structured_db  ... (확장 가능)
    │                     │
    └──────────┬──────────┘
               │ {"role":"tool","tool_call_id":"...","content":"..."}
               ▼
         LLM 다음 턴으로 피드백 (루프 반복)
               │ tool_calls 없으면 (FINISH)
               ▼
           최종 Answer
```

**장점:**
- LLM이 필요한 도구를 스스로 선택 — 플래너 의존도 최소화
- 멀티-홉 추론 가능 (예: 검색 → 해석 → 재검색)
- 새 도구는 schema만 등록하면 LLM이 자동 활용
- `max_turns` 기반 안전장치로 무한루프 방지

---

## 2. 구현 현황 점검 (todo.md vs 실제 코드)

### 2.1 상세 항목별 구현 현황

| 항목 | todo.md 상태 | 실제 코드 상태 | 파일 |
|------|-------------|--------------|------|
| **0.1** Tool Schema → LLM 주입 | TODO (P0) | ✅ **완료** | `tool_schemas.py::get_tool_definitions_for_llm()` + `executor.py::_run_agent_loop()` line 204 |
| **0.2** tool_call 응답 파싱·라우팅 | TODO (P0) | ✅ **완료** | `executor.py::_dispatch_tool()` (line 286~391) |
| **0.3** Agent 루프 (Observe→Think→Act) | TODO (P0) | ✅ **완료** | `executor.py::_run_agent_loop()` (line 175~284), `max_turns=10`, `E_LOOP_LIMIT` |
| **0.4** MockLLM tool_call 시뮬레이션 | TODO (P0) | ✅ **완료** | `mock_llm.py::tool_call_sequence` (line 48~82) |
| **0.5** Tool 결과 LLM 재전달 포맷 | TODO (P0) | ✅ **완료** | `executor.py` line 266~272: `{"role":"tool","tool_call_id":"...","content":"..."}` |

**핵심 발견**: 0.1~0.5 항목은 **이미 모두 구현 완료** 상태임.
todo.md에 여전히 "TODO"로 표기되어 있는 것은 문서 미갱신으로 인한 불일치.

### 2.2 관련 테스트 현황

| 테스트 파일 | 검증 항목 | 상태 |
|------------|----------|------|
| `tests/unit/test_agent_loop.py` | 즉시텍스트, 2턴 검색, RBAC 게이트, 최대턴 초과, sentinel, pipeline 호환 | ✅ 6개 케이스 |
| `tests/unit/test_mock_llm_tool_calls.py` | tool_call_sequence, backward compat, call_count | ✅ 6개 케이스 |
| `tests/unit/test_tool_definitions.py` | (존재 여부 확인 필요) | 미확인 |

---

## 3. 진짜 GAP 분석: 무엇이 아직 부족한가

구현은 완료되었으나, 다음 영역에서 보완이 필요:

### 3.1 통합 테스트 레벨에서 Agent Loop가 미검증
- `tests/integration/` 에는 agent_mode=True 시나리오가 없음
- IF-001~IF-005 모두 pipeline 모드(`_run_plan`) 기준으로 작성됨
- **필요**: IF-006 (Agent 루프 End-to-End) 통합 테스트 추가

### 3.2 `agent_mode` 기본값이 False
- `Executor(agent_mode=False)`가 기본 — 실제 서비스는 여전히 pipeline 모드
- CLI/API 레이어에서 `agent_mode=True` 활성화 경로 미확인

### 3.3 Qwen2.5 어댑터의 `tools` 파라미터 지원 미확인
- `MockLLMAdapter.chat(tools=...)` ✅ 지원
- `Qwen25Adapter.chat(tools=...)` → 실제 구현 확인 필요
- `apply_chat_template`에 tool 스키마를 주입하는 방식이 모델별로 상이

### 3.4 tool_call_log가 응답 스키마에 선택적 포함
- `agent_mode=True`일 때만 `tool_call_log` 키 포함 → 명세 문서에 반영 필요

### 3.5 todo.md 문서 불일치
- 0.1~0.5 항목을 ✅ 완료로 표기하고 우선순위 요약표 업데이트 필요

---

## 4. 전환 설계 방향 (필요 작업)

### Phase A — 문서/상태 동기화 (즉시)
1. `todo.md` 0.1~0.5 항목을 ✅ 완료로 변경
2. 우선순위 요약표 갱신
3. `CLAUDE.md` IMPLEMENTATION STATUS 표에 Agent Loop 완료 항목 추가

### Phase B — 통합 검증 (1순위 실작업)
1. **IF-006**: Agent 루프 통합 테스트 신규 작성
   - 시나리오: query → LLM이 search_docs 선택 → 결과 수신 → 최종 답변
   - MockLLM `tool_call_sequence` 활용
2. **Qwen25Adapter tools 파라미터 지원 확인** 및 필요시 보완

### Phase C — 서비스 활성화 (2순위)
1. CLI `query` 명령에 `--agent` 플래그 추가
2. FastAPI 엔드포인트 구현 시 `agent_mode` 파라미터 노출

### Phase D — 고도화 (추후)
1. 0.6 보안 검증 게이트 (`_security_gate()`) — RBAC 재활성화 후 연계
2. 1.6 LLM Intent 분류기 — Agent 루프에서 초기 의도 파악용

---

## 5. 판단 근거

**판단 근거:**

> 현재 시스템은 구조적으로 Agent Loop 전환이 이미 완료되어 있음에도 불구하고,
> (a) todo.md 문서가 미갱신 상태이고,
> (b) 기본 실행 경로가 여전히 pipeline 모드이며,
> (c) 통합 테스트가 agent_mode를 검증하지 않아,
> "구현은 됐으나 검증·활성화가 안 된" 상태로 볼 수 있다.
>
> 따라서 P0 우선순위 재구조화는 "새 개발"이 아닌
> **"구현 완료 사실 확인 + 통합 검증 + 기본값 전환"** 으로 초점을 맞추는 것이 정확하다.
>
> 방산 도메인 특성상 LLM이 자율적으로 도구를 선택하고
> 멀티-홉 추론을 수행하는 구조가 단순 키워드 매칭 플래너보다
> 복합 질의(예: "KF-21의 무장 호환성 + 최신 운용 규정 검색") 처리에 훨씬 적합하다.

---

## 6. 설계 문서 목차 (승인 후 작성 예정)

출력 문서: `output_docs/260326_agent_loop_design.docx`

1. 전환 배경 및 필요성
2. 현재 구조 vs 목표 구조 비교 다이어그램
3. 항목별 구현 현황 (0.1~0.5 완료 확인)
4. GAP 목록 및 보완 계획
5. IF-006 통합 테스트 설계안
6. Qwen25Adapter tool_call 지원 확인 계획
7. 서비스 활성화 로드맵 (CLI → FastAPI)
8. todo.md 갱신 사항
