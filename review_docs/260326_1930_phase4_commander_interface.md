# Phase 4 — Commander Interface 구조적 증명 구현 분석

**작성일**: 2026-03-26 14:30
**목적**: Phase 4 Commander Interface 구현 설계 결정 및 판단 근거 기록
**범위**: 최소 구현(Structural Proof) — 5개 도구 체인 연결 구조 증명

---

## 1. Phase 4 목표

Phase 4의 핵심 목표는 **사령관이 한 번의 요청으로 의사결정 지원 패키지 전체를 받을 수 있는 인터페이스**를 제공하는 것이다. 사용자 지침에 따라 "테스트 단계이므로 구조적 증명에 집중"하여 최소 구현으로 제한한다.

---

## 2. 설계 결정

### 2.1 새 파일 vs 기존 파일 확장

**결정**: `commander_interface.py` 신규 파일 생성

**판단 근거**:
- `executor.py`는 이미 750+ 라인. 합성 로직 추가 시 블로트 심화.
- `decision_support.py`는 개별 도구 핸들러 집합. 오케스트레이션 레이어와 분리 필요.
- 독립 파일로 분리하면 독립 테스트 + 향후 교체/확장이 용이하다.

### 2.2 함수 시그니처 설계

```python
def compose_decision_support_response(
    arguments: dict,
    llm_adapter: Any,
    threat_assess_fn: Callable[[dict], dict],
) -> dict:
```

**판단 근거**:
- `threat_assess_fn`을 주입 받는 이유: `_threat_assess()`는 `Executor`의 메서드라 인스턴스에 의존한다. 함수로 주입하면 테스트 시 mock으로 쉽게 교체 가능.
- `llm_adapter`는 `ipb_summary` / `coa_generate`의 LLM 호출에 필요.
- `arguments`는 단일 flat dict — `decision_support_composite` 도구 스키마와 1:1 대응.

### 2.3 체인 데이터 흐름

```
threat_assess(arguments)
    ↓ threat_level 추출
ipb_summary(arguments + 지형/기상 필드)
    ↓ (결과 독립적 — ipb는 COA에 미사용, 구조 증명 단계)
coa_generate(arguments + threat_level ← Step 1)
    ↓ recommended_coa 이름 추출
roe_check(proposed_action=recommended_action, roe_level, ...)
    ↓
fires_plan(arguments) — available_fires 있을 때만
```

**판단 근거**:
- `threat_level`의 Step 1 → Step 3 전파가 핵심 데이터 의존성 체인의 증거.
- `ipb_summary`는 현재 COA 입력으로 미사용 (구조 증명 단계). 향후 Phase 5에서 ipb 결과를 COA 우선순위 조정 인자로 활용 가능.
- `fires_plan`의 조건부 실행: 화력 자산 없는 시나리오(예: 대피 작전)에서 불필요한 실행 방지.

### 2.4 예외 격리 (`_safe_call`)

```python
def _safe_call(tool_name, fn, args, execution_chain, errors):
    try:
        result = fn(args)
        execution_chain.append(tool_name)
        return result
    except Exception as exc:
        errors.append(f"{tool_name}: {exc}")
        execution_chain.append(f"{tool_name}[ERROR]")
        return None
```

**판단 근거**:
- 전장 환경에서 한 도구 실패가 전체 결심 지원 실패로 이어지면 안 된다.
- `errors` 리스트에 기록 → 감사 로그 활용 가능.
- 후속 도구는 `None` 폴백으로 계속 실행 (예: `threat_level`이 None이면 "MEDIUM" 기본값 사용).

### 2.5 도구 스키마 (`decision_support_composite`)

단일 flat 스키마로 5개 도구의 모든 입력 필드를 수용. `required`는 `["threat_type"]` 하나만.

**판단 근거**:
- LLM이 한 번의 도구 호출로 전체 체인을 트리거할 수 있어야 한다.
- 개별 도구의 필수 필드(예: `fires_plan`의 `available_fires`)는 합성 수준에서 선택적으로 처리.

---

## 3. 구현 파일 목록

| 파일 | 유형 | 내용 |
|------|------|------|
| `src/defense_llm/agent/commander_interface.py` | 신규 | `compose_decision_support_response()`, `_safe_call()`, `_extract_recommended_action()` |
| `src/defense_llm/agent/tool_schemas.py` | 수정 | `decision_support_composite` 스키마 + `_TOOL_DESCRIPTIONS` 항목 추가 |
| `src/defense_llm/agent/executor.py` | 수정 | `_compose_dsp` 임포트, `_dispatch_tool` 라우팅, `battle_tools`에 추가 |
| `tests/unit/test_commander_interface.py` | 신규 | 17개 테스트 (F-01~F-12 + helpers) |

---

## 4. 테스트 결과

| 테스트 그룹 | 수 | 결과 |
|---|---|---|
| TestCompositeReturnStructure (F-01~05) | 5 | ✅ 전원 통과 |
| TestChainDataFlow (F-06~08b) | 4 | ✅ 전원 통과 |
| TestExceptionIsolation (F-09~10) | 2 | ✅ 전원 통과 |
| TestExecutorIntegration (F-11~12) | 2 | ✅ 전원 통과 |
| TestExtractRecommendedAction (helpers) | 4 | ✅ 전원 통과 |
| **합계** | **17** | ✅ **17/17** |

전체 스위트: **322 passed / 330 total** (기존 8개 실패 동일 — torch/opendataloader_pdf 미설치)

---

## 5. Phase 4 미구현 항목 (향후 과제)

구조적 증명 단계에서 의도적으로 제외한 항목:

1. **IPB → COA 피드백 루프**: `ipb_summary` 결과(OCOKA)를 `coa_generate`의 `terrain` / `priority_factors`에 자동 주입하여 COA 품질 향상.
2. **CLI `--composite` 플래그**: `python -m defense_llm.cli --agent --composite` 로 단일 명령에서 합성 패키지 출력.
3. **IF-006 통합 테스트**: `battle_context` 주입 → `decision_support_composite` 호출 → 합성 응답 검증 E2E 테스트.
4. **Composite 응답 포매터**: 사령관 화면 출력을 위한 한국어 마크다운 / 텍스트 포맷 렌더링.

---

## 6. 판단 근거 (종합)

> Phase 4의 구조적 증명 목표는 달성되었다.
> `compose_decision_support_response()`는 5개 도구를 순서대로 실행하고,
> 데이터 의존성 체인(threat_level 전파, recommended_action 추출)을 올바르게 구현했으며,
> 예외 격리를 통해 부분 실패에서도 체인이 계속 실행됨을 검증했다.
> `decision_support_composite` 도구는 LLM이 단일 호출로 전체 의사결정 지원 패키지를 요청할 수 있는 인터페이스를 제공한다.
