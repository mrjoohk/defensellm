"""Deterministic evaluation runner for regression testing (UF-070)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

E_VALIDATION = "E_VALIDATION"


class EvalRunner:
    """Runs QA samples through the system and generates a JSON report (UF-070).

    Args:
        system_fn: Callable(question: str, user_context: dict) -> response_dict.
        user_context: Default user context passed to system_fn.
    """

    def __init__(
        self,
        system_fn: Callable[[str, dict], dict],
        user_context: Optional[dict] = None,
    ) -> None:
        self._system_fn = system_fn
        self._user_context = user_context or {"role": "analyst", "clearance": "INTERNAL"}

    def run(self, samples: List[dict]) -> dict:
        """Execute all samples and return a report dict (UF-070).

        Args:
            samples: List of sample dicts with keys:
                - id (str)
                - question (str)
                - expected_answer_keywords (list of str, optional)
                - expected_citation_doc_ids (list of str, optional)

        Returns:
            dict: { total, passed, failed, pass_rate, results }

        Raises:
            ValueError: (E_VALIDATION) if samples is empty.
        """
        if not samples:
            raise ValueError(f"{E_VALIDATION}: samples must not be empty.")

        results = []
        passed = 0

        for sample in samples:
            result = self._run_sample(sample)
            results.append(result)
            if result["pass"]:
                passed += 1

        total = len(samples)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "results": results,
        }

    def _run_sample(self, sample: dict) -> dict:
        sample_id = sample.get("id", "unknown")
        question = sample.get("question", "")
        
        # Playbook Schema mapping
        expected_answer = sample.get("expected_answer", {})
        expected_keywords = expected_answer.get("must_include", [])
        
        req_evidence = sample.get("required_evidence", [])
        expected_doc_ids = [k.get("doc_id") for k in req_evidence if "doc_id" in k]

        try:
            response = self._system_fn(question, self._user_context)
        except Exception as e:
            return {
                "id": sample_id,
                "pass": False,
                "citation_match": False,
                "details": f"System error: {e}",
            }

        answer = response.get("data", {}).get("answer", "")
        citations = response.get("citations", [])
        returned_doc_ids = {c.get("doc_id") for c in citations}

        # Keyword check
        keyword_pass = all(kw.lower() in answer.lower() for kw in expected_keywords) if expected_keywords else True

        # Citation check
        citation_match = (
            all(doc_id in returned_doc_ids for doc_id in expected_doc_ids)
            if expected_doc_ids
            else True
        )

        overall_pass = keyword_pass and citation_match

        return {
            "id": sample_id,
            "pass": overall_pass,
            "citation_match": citation_match,
            "details": (
                "OK" if overall_pass
                else f"keyword_pass={keyword_pass}, citation_match={citation_match}"
            ),
        }

    def save_report(self, report: dict, output_path: str) -> None:
        """Save report dict to a JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
