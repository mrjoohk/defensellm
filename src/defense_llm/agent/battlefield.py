"""Battlefield data ingestion and briefing formatting.

Provides:
  - ingest_battlefield_data(): CSV/JSON → structured situation dict
  - build_briefing_context():  situation + doctrine chunks → LLM context string
  - Prompt constants for BLUF+SBAR and COA generation
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# LLM prompt templates
# ---------------------------------------------------------------------------

BRIEFING_SYSTEM_PROMPT = (
    "당신은 방산 도메인 전문 브리핑 작성 AI입니다.\n"
    "제공된 전장 상황 데이터를 바탕으로 반드시 아래 포맷에 맞춰 한국어로 브리핑을 작성하십시오.\n\n"
    "[BLUF]\n"
    "핵심 결론 (1~2문장, 가장 중요한 위협 또는 상황 요약)\n\n"
    "[SALUTE 보고]\n"
    "- S (규모/Size): \n"
    "- A (행동/Activity): \n"
    "- L (위치/Location): \n"
    "- U (부대/Unit): \n"
    "- T (시간/Time): \n"
    "- E (장비/Equipment): \n\n"
    "[상황 평가]\n"
    "현재 전장 상황에 대한 종합 분석 (3~5문장)\n\n"
    "[COA 권고안]\n"
    "COA-1 (최우선 권장): \n"
    "COA-2: \n"
    "COA-3: \n\n"
    "[판단 근거]\n"
    "위 권고안의 판단 근거를 간략히 서술하십시오."
)

COA_SYSTEM_PROMPT = (
    "당신은 방산 도메인 전술 분석 AI입니다.\n"
    "제공된 전장 상황과 제약조건을 분석하여 3가지 COA(Course of Action)를 제시하십시오.\n"
    "각 COA에는 다음 항목을 포함하십시오: 행동 방침, 예상 효과, 위험 요소, 우선순위 순위.\n"
    "제약조건이 명시된 경우 반드시 반영하십시오.\n"
    "모든 답변은 한국어로 작성하십시오."
)


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------

def ingest_battlefield_data(
    raw_data: str,
    format_hint: str = "auto",
) -> Dict[str, Any]:
    """Parse raw battlefield data (CSV or JSON) into a structured situation dict.

    Args:
        raw_data:    String content of the CSV or JSON data.
        format_hint: "csv" | "json" | "auto" (auto-detects from first character).

    Returns:
        {
          "records":   list[dict],  # up to 50 rows
          "format":    str,
          "row_count": int,
          "columns":   list[str],
          "summary":   str,         # compact text for LLM context
          "error":     str | None,
        }
    """
    raw_data = raw_data.strip()
    if not raw_data:
        return {"error": "Empty data", "records": [], "format": "unknown",
                "row_count": 0, "columns": [], "summary": ""}

    fmt = format_hint.lower()
    if fmt == "auto":
        fmt = "json" if raw_data.startswith(("{", "[")) else "csv"

    records: List[Dict] = []
    columns: List[str] = []

    if fmt == "json":
        try:
            parsed = json.loads(raw_data)
            if isinstance(parsed, list):
                records = parsed
            elif isinstance(parsed, dict):
                # Try common container keys
                for key in ("records", "data", "items", "units", "threats", "log"):
                    if key in parsed and isinstance(parsed[key], list):
                        records = parsed[key]
                        break
                if not records:
                    records = [parsed]
            columns = list(records[0].keys()) if records else []
        except json.JSONDecodeError as e:
            return {"error": f"JSON 파싱 오류: {e}", "records": [], "format": "json",
                    "row_count": 0, "columns": [], "summary": ""}
    else:
        try:
            reader = csv.DictReader(io.StringIO(raw_data))
            records = [dict(row) for row in reader]
            columns = list(records[0].keys()) if records else []
        except Exception as e:
            return {"error": f"CSV 파싱 오류: {e}", "records": [], "format": "csv",
                    "row_count": 0, "columns": [], "summary": ""}

    # Build compact summary for LLM
    col_preview = ", ".join(columns[:8]) + ("..." if len(columns) > 8 else "")
    lines = [f"전장 데이터 ({fmt.upper()}): {len(records)}개 레코드 | 필드: {col_preview}"]
    for i, rec in enumerate(records[:5]):
        row_str = ", ".join(f"{k}={v}" for k, v in list(rec.items())[:6])
        lines.append(f"  [{i+1}] {row_str}")
    if len(records) > 5:
        lines.append(f"  ... 외 {len(records) - 5}개 레코드")

    return {
        "records":   records[:50],
        "format":    fmt,
        "row_count": len(records),
        "columns":   columns,
        "summary":   "\n".join(lines),
        "error":     None,
    }


# ---------------------------------------------------------------------------
# Context builder for LLM
# ---------------------------------------------------------------------------

def build_briefing_context(
    situation: Dict[str, Any],
    doctrine_chunks: Optional[List[Dict]] = None,
) -> str:
    """Combine parsed situation data + RAG doctrine chunks into an LLM context string.

    Args:
        situation:       Result dict from ingest_battlefield_data().
        doctrine_chunks: Optional list of RAG chunk dicts with 'text' key.

    Returns:
        Formatted context string to inject into the LLM user message.
    """
    parts: List[str] = []

    # Situation summary
    summary = situation.get("summary", "")
    if summary:
        parts.append("=== 전장 상황 데이터 ===\n" + summary)

    # Detailed records (top 10)
    records = situation.get("records", [])
    if records:
        parts.append("=== 상세 데이터 (상위 10건) ===")
        for rec in records[:10]:
            parts.append("  " + json.dumps(rec, ensure_ascii=False))

    # Doctrine / regulation references from RAG
    if doctrine_chunks:
        parts.append("=== 관련 교범·규정 ===")
        for i, chunk in enumerate(doctrine_chunks[:3], 1):
            text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
            parts.append(f"[교범 {i}] {text[:400]}")

    return "\n\n".join(parts)
