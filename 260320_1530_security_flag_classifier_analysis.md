# 보안 Flag 추가 및 Classifier 동작 분석
**날짜**: 2026-03-20 15:30
**요청**: 보안 로직을 개발 단계에서 flag로 비활성화 + Classifier 동작 확인

---

## 1. Classifier 동작 분석 — "KF-21의 최대 속도는?"

### 실제 처리 흐름

```
classify_query("KF-21의 최대 속도는?")
  │
  ├─ [1] SECURITY check (security_enabled=True 시에만 동작)
  │       _SECURITY_PATTERNS: 기밀|비밀|classified|secret... → 매칭 없음
  │
  ├─ [2] STRUCTURED check
  │       최대\s*(속도|고도|중량|항속|사거리) → "최대 속도" 매칭 ✅
  │       → has_structured = True
  │
  ├─ [3] DOC check
  │       문서|교범|매뉴얼|검색|조회... → 매칭 없음
  │       → has_doc = False
  │
  └─ → 반환: STRUCTURED_KB_QUERY
```

### 핵심 결론

| 항목 | 결과 |
|---|---|
| "KF-21" 키워드 분류 기여 | **없음** — 어떤 패턴에도 포함 안 됨 |
| "최대 속도" 분류 기여 | **있음** — `_STRUCTURED_PATTERNS[0]` 매칭 |
| 최종 분류 | `STRUCTURED_KB_QUERY` |

### "KF-21"은 어디서 처리되나?

Classifier는 **쿼리 의도(intent)만** 판단. 플랫폼/무기 고유명은 Classifier를 통과한 후
`executor._query_db()`에서 fuzzy matching으로 처리됨.

```python
# _query_db() 내부
query_norm = _normalize_id("KF-21의 최대 속도는?")
# → "KF21의최대속도는" (하이픈/공백 제거, 대문자화)
# → DB row 값과 비교 시 "KF-21", "KF21" 모두 매칭
```

### 분석 결과 vs 내 예측 비교

| 항목 | 예측 | 실제 코드 | 일치 여부 |
|---|---|---|---|
| "최대 속도" 매칭 | `_STRUCTURED_PATTERNS[0]` | 동일 | ✅ |
| "KF-21" 분류 기여 없음 | 없음 | 어떤 패턴에도 없음 | ✅ |
| 최종 분류 | `STRUCTURED_KB_QUERY` | 동일 | ✅ |
| "KF-21" 처리 위치 | `_query_db()` fuzzy | `_normalize_id()` 기반 | ✅ |

분석 결과와 실제 코드가 **완전히 일치**.

---

## 2. Security Flag 수정 내역

### 수정 파일 3개

#### `src/defense_llm/config/settings.py`
- `AppConfig`에 `security_enabled: bool = False` 필드 추가
- `load_config()`에 env 매핑 `DEFENSE_LLM_SECURITY_ENABLED` 추가
- `_bool()` 처리로 환경변수로도 제어 가능

#### `src/defense_llm/agent/planner_rules/classifier.py`
- `classify_query(security_enabled: bool = False)` 파라미터 추가
- `if security_enabled:` 블록으로 `_SECURITY_PATTERNS` 체크 감쌈
- False(기본값)이면 `SECURITY_RESTRICTED` 분류 자체가 발생하지 않음

#### `src/defense_llm/agent/executor.py`
- `Executor.__init__`에 `security_enabled: bool = False` 파라미터 추가
- `_dispatch_tool()` (agent mode) 내 `check_access()` 호출을 `if self._security_enabled:` 조건으로 감쌈
- `_run_plan()` (pipeline mode) 내 동일하게 처리

### 보안 로직 비활성화 범위

| 보안 기능 | Flag 적용 여부 | 비고 |
|---|---|---|
| RBAC clearance check (search_docs 전) | ✅ 적용 | pipeline + agent 모두 |
| SECURITY_RESTRICTED 분류 차단 | ✅ 적용 | classifier 레벨 |
| `masking.py` (좌표/주파수 마스킹) | ❌ 미적용 | executor에서 직접 호출 없음, 필요시 별도 추가 |
| `auth.py` JWT 인증 | ❌ 미적용 | serving 레이어에서 별도 호출 |

### 판단 근거
- 개발 단계에서 보안 로직은 테스트 시 불필요한 PermissionError를 유발하여 기능 검증을 방해함
- Flag 방식은 프로덕션 전환 시 `security_enabled=True` 한 줄로 복구 가능하여 코드 변경 최소화
- 기본값 `False`는 개발 편의성 우선; 환경변수 `DEFENSE_LLM_SECURITY_ENABLED=true`로 개별 서버에서 즉시 활성화 가능
