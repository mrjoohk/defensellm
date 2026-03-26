# web_search 도구 → _fallback_web_search 연계 분석

**작성일**: 2026-03-26
**대상**: `executor.py::_fallback_web_search()` — `web_search` 도구 dispatch 후 웹 청크 생성·색인 흐름

---

## 1. 호출 경로 (변경 후)

```
LLM → web_search(query="...", top_k=3)
        │
        ▼  _dispatch_tool()
        if tool_name == "web_search":
            web_params = {"query": ..., "top_k": ...}
            results = self._fallback_web_search(web_params)   ← 진입점
```

---

## 2. 발견된 버그 목록 (5건)

### BUG-1 (Critical) — chunk_document에 잘못된 키워드 인수 전달 → TypeError

**위치**: `executor.py` line ~573

```python
# 현재 (버그):
chunks_result = chunk_document(
    doc_id=doc_id,
    doc_rev="v1",        ← ❌ chunk_document()에 doc_rev 파라미터 없음
    ...
)

# chunk_document 시그니처:
def chunk_document(doc_id: str, version: str, text: str, ...)
#                              ^^^^^^^^ 정확한 파라미터명
```

**영향**: `online_mode_enabled=True` + `web_search` 호출 시 항상 `TypeError: chunk_document() got an unexpected keyword argument 'doc_rev'` 발생 → 웹 청크 생성 불가.

**수정**: `doc_rev="v1"` → `version="v1"`

---

### BUG-2 (Minor) — c.doc_id 재할당: Chunk 데이터클래스에 불필요한 속성 덮어쓰기

**위치**: `executor.py` line ~584

```python
for c in chunks:
    c.doc_id = doc_id  ← ❌ doc_id는 이미 chunk_document()에서 설정됨
```

**영향**: 기능적 버그는 아니지만 (dataclass는 mutable), 코드 의도를 흐림.

**수정**: 해당 라인 제거

---

### BUG-3 (Medium) — source_uri 미설정: 웹 청크에 출처 URL 없음

**위치**: `executor.py` line ~573

```python
chunks_result = chunk_document(
    doc_id=doc_id,
    version="v1",
    text=text[:10000],
    # source_uri 없음 ← ❌ 웹 출처를 추적할 수 없음
)
```

**영향**: 인용(citation) 시 웹 청크의 원본 URL이 기록되지 않아 출처 검증 불가. 방산 도메인에서 정보 출처 추적은 중요한 감사 요건.

**수정**: `source_uri=url` 추가

---

### BUG-4 (Low) — 미사용 import: requests, BeautifulSoup

**위치**: `executor.py` line ~525

```python
import requests        ← ❌ 실제 사용 없음 (duckduckgo_search가 직접 본문 반환)
from bs4 import BeautifulSoup  ← ❌ 실제 사용 없음
```

**영향**: ImportError 잠재 위험 (bs4 미설치 시 함수 진입 즉시 실패). 실제 사용하지 않으므로 제거.

---

### BUG-5 (Low) — 함수 내부에서 최상위 모듈 재임포트

**위치**: `executor.py` line ~528

```python
def _fallback_web_search(self, params: dict) -> List[dict]:
    import requests       ← 최상위에 이미 없지만, 미사용이므로 제거
    from bs4 import ...   ← 동일
    import json           ← 최상위에서 이미 import됨
    import os             ← 최상위에서 이미 import됨
    import datetime       ← 함수 내 유지 가능하나 일관성 위해 정리
    ...
    import re             ← 최상위에서 이미 import됨
    import hashlib        ← 최상위에서 이미 import됨
```

**영향**: 코드 가독성 저하, 일부 불필요한 모듈 로딩 시도.

---

### BUG-6 (Low) — top_k가 웹 검색 결과 수에 반영 안 됨

**위치**: `executor.py` line ~540

```python
search_results = list(ddgs.text(query, max_results=2))  ← 항상 2개
# 하지만 params.get("top_k", 5)는 최종 index.search()에서만 사용됨
```

**영향**: `web_search(query=..., top_k=5)` 요청해도 실제 웹 검색은 항상 2건만 수행.

**수정**: `max_results=max(2, params.get("top_k", 3))`

---

## 3. 판단 근거

> BUG-1(doc_rev)이 Critical인 이유: online_mode_enabled=True로 web_search 도구를 활성화한 상태에서
> LLM이 web_search를 호출하면 반드시 TypeError가 발생해 웹 검색이 전혀 동작하지 않는다.
> 이는 이전 구조 변경(web_search 독립 도구화) 이후에도 잠재해 있던 버그로,
> 웹 소스 연계를 실제 사용하기 전에 반드시 수정되어야 한다.
