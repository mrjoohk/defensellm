"""Unit tests for eval module (UF-070)."""

import pytest

from defense_llm.eval.runner import EvalRunner, E_VALIDATION


def _make_system_fn(answer: str = "테스트 답변", doc_ids: list = None):
    """Create a mock system function that returns a fixed response."""
    doc_ids = doc_ids or ["DOC-001"]

    def system_fn(question: str, user_context: dict) -> dict:
        return {
            "data": {"answer": answer},
            "citations": [{"doc_id": did, "snippet_hash": "abc"} for did in doc_ids],
        }

    return system_fn


class TestEvalRunner:
    def test_report_generated_for_two_samples(self):
        runner = EvalRunner(system_fn=_make_system_fn("답변 텍스트"))
        samples = [
            {"id": "S1", "question": "질문1"},
            {"id": "S2", "question": "질문2"},
        ]
        report = runner.run(samples)
        assert report["total"] == 2
        assert "passed" in report
        assert "failed" in report
        assert "pass_rate" in report
        assert len(report["results"]) == 2

    def test_pass_rate_calculation(self):
        runner = EvalRunner(system_fn=_make_system_fn("답변"))
        samples = [
            {"id": "S1", "question": "q1"},
            {"id": "S2", "question": "q2"},
        ]
        report = runner.run(samples)
        assert 0.0 <= report["pass_rate"] <= 1.0

    def test_empty_samples_raises(self):
        runner = EvalRunner(system_fn=_make_system_fn())
        with pytest.raises(ValueError, match=E_VALIDATION):
            runner.run([])

    def test_keyword_match_pass(self):
        runner = EvalRunner(system_fn=_make_system_fn("KF-21의 최대 고도는 15000m입니다"))
        samples = [
            {
                "id": "S1",
                "question": "KF-21 최대 고도",
                "expected_answer_keywords": ["15000", "고도"],
            }
        ]
        report = runner.run(samples)
        assert report["results"][0]["pass"] is True

    def test_keyword_mismatch_fail(self):
        runner = EvalRunner(system_fn=_make_system_fn("모름"))
        samples = [
            {
                "id": "S1",
                "question": "KF-21 최대 고도",
                "expected_answer_keywords": ["15000m"],
            }
        ]
        report = runner.run(samples)
        assert report["results"][0]["pass"] is False

    def test_citation_match(self):
        runner = EvalRunner(system_fn=_make_system_fn(doc_ids=["DOC-001", "DOC-002"]))
        samples = [
            {
                "id": "S1",
                "question": "q",
                "expected_citation_doc_ids": ["DOC-001"],
            }
        ]
        report = runner.run(samples)
        assert report["results"][0]["citation_match"] is True

    def test_citation_mismatch_fail(self):
        runner = EvalRunner(system_fn=_make_system_fn(doc_ids=["DOC-001"]))
        samples = [
            {
                "id": "S1",
                "question": "q",
                "expected_citation_doc_ids": ["DOC-999"],
            }
        ]
        report = runner.run(samples)
        assert report["results"][0]["citation_match"] is False

    def test_system_exception_marks_fail(self):
        def failing_fn(q, ctx):
            raise RuntimeError("시스템 오류")

        runner = EvalRunner(system_fn=failing_fn)
        samples = [{"id": "S1", "question": "q"}]
        report = runner.run(samples)
        assert report["results"][0]["pass"] is False
        assert "error" in report["results"][0]["details"].lower()

    def test_save_report(self, tmp_path):
        import json
        runner = EvalRunner(system_fn=_make_system_fn())
        samples = [{"id": "S1", "question": "q"}]
        report = runner.run(samples)
        output = str(tmp_path / "report.json")
        runner.save_report(report, output)
        with open(output) as f:
            loaded = json.load(f)
        assert loaded["total"] == 1
