# 온라인/오프라인 모드 구조 분석 및 변경 설계

**작성일**: 2026-03-26
**대상**: Phase 1 — Agent 루프에서의 온라인/오프라인 모드 처리 구조 검토

---

## 1. 현재 구조 문제점

### 1.1 online_mode가 LLM 파라미터로 노출되어 있으나 Agent 모드에서 완전히 무시됨

**tool_schemas.py `search_docs` 정의:**
```python
"online_mode": {"type": bool}  # LLM이 설정 가능
```

**pipeline 모드 (`_run_plan`):**
```python
if params.get("online_mode"):            # ✅ 동작함
    web_results = self._fallback_web_search(params)
```

**agent 모드 (`_dispatch_tool`):**
```python
if tool_name == "search_docs":
    results = self._index.search(...)    # ❌ online_mode 파라미터 완전 무시
    collected_chunks.extend(results)
    return {"chunks_found": len(results), ...}
```

**결론**: LLM이 `search_docs(query=..., online_mode=true)`를 호출해도 agent 모드에서는 아무 효과 없음.
LLM은 올바르게 동작한다고 착각하지만 실제로는 오프라인 RAG만 수행됨.

### 1.2 구조적 설계 오류: online_mode는 서버 설정이지 LLM 판단이 아니어야 함

- **현재**: LLM이 `online_mode=true/false`를 파라미터로 선택 → 서버가 이를 존중
- **문제**: 온라인 접근 가능 여부는 배포 환경, 네트워크 정책, 보안 등급에 따라 서버가 결정해야 함
- LLM이 `online_mode=true`를 설정한다고 해서 네트워크 차단 환경에서 인터넷이 열리는 게 아님
- **올바른 패턴**: 서버가 `web_search` 도구를 등록하면 LLM이 호출 가능, 등록 안 하면 호출 불가

### 1.3 Qwen25Adapter tools 파라미터 지원 현황 (GAP G-3 해소)

**확인 결과**: `qwen_adapter.py::chat()` 에 이미 `tools` 파라미터 완전 구현됨
```python
def chat(self, messages, ..., tools: Optional[List[Dict]] = None) -> Dict:
    if tools:
        template_kwargs["tools"] = tools          # apply_chat_template에 주입
    ...
    tool_calls = self._parse_tool_calls(content) if tools else None  # 파싱
```
- Format A: `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` 지원
- Format B: `✿FUNCTION✿name✿ARGS✿{...}✿` 지원 (구버전 Qwen2.5 호환)
- **GAP G-3 실제로는 이미 해소됨** — 별도 작업 불필요

---

## 2. 변경 설계

### 2.1 search_docs에서 online_mode 제거

**Before (LLM이 네트워크 접근을 직접 제어하는 잘못된 구조):**
```
search_docs(query="KF-21", online_mode=true)
  → Python이 online_mode 플래그 확인
  → _fallback_web_search() 호출
```

**After (서버가 도구 등록을 통해 접근 제어하는 올바른 구조):**
```
[offline only]
search_docs(query="KF-21")       → 내부 RAG 인덱스만 검색

[online enabled at server level]
search_docs(query="KF-21")       → 내부 RAG 인덱스 검색
web_search(query="KF-21 최신")   → 외부 웹 검색 (LLM이 필요 시 판단)
```

### 2.2 web_search 독립 도구 추가

**Schema:**
```python
"web_search": {
    "required": ["query"],
    "properties": {
        "query": {"type": str},
        "top_k": {"type": int},
    },
}
```

**Description:**
```
"내부 문서에 없는 최신 정보나 공개 정보 조회 시 사용.
 내부 RAG(search_docs)로 관련 문서를 찾지 못했을 때만 호출할 것."
```

### 2.3 Executor.online_mode_enabled 서버 레벨 제어

```python
Executor(
    ...
    online_mode_enabled=False,  # 기본값: 오프라인 (방산 보안 환경)
)
```

- `online_mode_enabled=False` (기본): `web_search` 도구가 LLM에 주입되지 않음
- `online_mode_enabled=True`: `web_search` 도구가 주입되고 `_dispatch_tool()`이 처리

### 2.4 _run_plan() 하위 호환성 유지

pipeline 모드의 `online_mode` 파라미터는 유지 (기존 테스트/동작 보호).
단, 서버 레벨 `online_mode_enabled=False`일 때는 pipeline에서도 web 검색 차단.

---

## 3. 파일별 변경 사항 요약

| 파일 | 변경 내용 |
|------|----------|
| `agent/tool_schemas.py` | `search_docs`에서 `online_mode` 제거; `web_search` 신규 등록 |
| `agent/executor.py` | `online_mode_enabled` 생성자 파라미터 추가; `_run_agent_loop()` web_search 조건부 포함; `_dispatch_tool()` web_search 핸들러 추가; `_run_plan()` online_mode를 `online_mode_enabled` 게이트에 종속 |
| `tests/unit/test_agent_loop.py` | web_search 활성/비활성 케이스 추가 |
| `tests/unit/test_tool_definitions.py` | web_search 스키마 등록 확인 추가 |

---

## 4. 판단 근거

> `online_mode`를 LLM 파라미터로 노출하는 것은 "LLM이 서버 정책을 결정"하는 역전된 권한 모델이다.
> 방산 도메인에서는 특히 네트워크 접근이 보안 정책 대상이므로,
> 서버 수준에서 `online_mode_enabled` 플래그로 제어하고
> LLM에게는 `web_search` 도구의 존재 여부로만 접근 가능성을 알려야 한다.
> 이 변경은 LLM Tool-Use Agent 루프의 올바른 설계 원칙(도구 등록 = 권한 부여)과 일치한다.
