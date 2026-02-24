"""Tool plan builder based on query type (UF-030)."""

from __future__ import annotations

from typing import List

from .classifier import QueryType


def build_plan(query_type: QueryType, context: dict = None) -> List[dict]:
    """Generate a tool execution plan for a given query type (UF-030).

    Args:
        query_type: Classified query type.
        context: Optional context dict (query text, user, etc.).

    Returns:
        List of ToolPlan dicts: [{ "tool": str, "params": dict }]
    """
    context = context or {}
    query = context.get("query", "")
    field_filter = context.get("field_filter", [])
    security_label_filter = context.get("security_label_filter", ["PUBLIC", "INTERNAL"])

    if query_type == QueryType.STRUCTURED_KB_QUERY:
        return [
            {
                "tool": "query_structured_db",
                "params": {
                    "query": query,
                    "field_filter": field_filter,
                    "security_label_filter": security_label_filter,
                },
            },
            {
                "tool": "format_response",
                "params": {"template": "structured_kb"},
            },
        ]

    if query_type == QueryType.DOC_RAG_QUERY:
        return [
            {
                "tool": "search_docs",
                "params": {
                    "query": query,
                    "top_k": 5,
                    "field_filter": field_filter,
                    "security_label_filter": security_label_filter,
                },
            },
            {
                "tool": "generate_answer",
                "params": {"template": "rag_answer"},
            },
        ]

    if query_type == QueryType.MIXED_QUERY:
        return [
            {
                "tool": "query_structured_db",
                "params": {
                    "query": query,
                    "field_filter": field_filter,
                    "security_label_filter": security_label_filter,
                },
            },
            {
                "tool": "search_docs",
                "params": {
                    "query": query,
                    "top_k": 3,
                    "field_filter": field_filter,
                    "security_label_filter": security_label_filter,
                },
            },
            {
                "tool": "generate_answer",
                "params": {"template": "mixed_answer"},
            },
        ]

    if query_type == QueryType.SECURITY_RESTRICTED:
        return [
            {
                "tool": "security_refusal",
                "params": {"reason": "Query matches security restriction rules."},
            }
        ]

    # UNKNOWN
    return [
        {
            "tool": "search_docs",
            "params": {
                "query": query,
                "top_k": 3,
                "field_filter": field_filter,
                "security_label_filter": security_label_filter,
            },
        },
    ]
