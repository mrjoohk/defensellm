"""
tests/unit/test_api.py

Phase 5 FastAPI 엔드포인트 단위 테스트 (FastAPI TestClient 사용 — 서버 불필요)

테스트 수: 16개
  H-01 ~ H-04: 기본 엔드포인트 (health, web UI, OpenAPI)
  H-05 ~ H-09: POST /agent — 성공 케이스
  H-10 ~ H-13: POST /agent — 실패/에지 케이스
  H-14 ~ H-16: POST /agent/upload — 파일 업로드
"""

import json
import io
import pytest

from fastapi.testclient import TestClient

from defense_llm.serving.api import app


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient — starts/stops lifespan once per module."""
    with TestClient(app) as c:
        yield c


# Minimal valid BattleSituationPrompt
_MINIMAL_SCENARIO = {
    "scenario_id": "TEST-001",
    "timestamp": "2026-03-26T06:00:00Z",
    "classification": "CONFIDENTIAL",
    "threat": {
        "type": "ARMOR",
        "count": 10,
        "movement": "ADVANCING",
        "confidence": 0.85,
        "description": "테스트 전차 위협"
    },
    "friendly_forces": {
        "unit_id": "1BN",
        "unit_type": "MECH_INF",
    },
    "query": {
        "intent": "THREAT_ASSESS",
        "text": "위협 수준을 평가하라.",
        "roe_level": "RETURN_FIRE"
    }
}


def _agent_request(**kwargs):
    """Build a minimal valid AgentRequest dict, overrideable by kwargs."""
    base = {
        "query": "위협 수준을 평가하라.",
        "battle_situation": _MINIMAL_SCENARIO,
        "agent_mode": True,
        "use_composite": False,
        "user_context": {"role": "analyst", "clearance": "SECRET", "user_id": "test_user"},
    }
    base.update(kwargs)
    return base


# ===========================================================================
# H-01 ~ H-04: 기본 엔드포인트
# ===========================================================================

class TestBasicEndpoints:

    def test_h01_health_returns_ok(self, client):
        """H-01: GET /health → status=ok, executor_ready=true."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["executor_ready"] is True

    def test_h02_root_returns_html(self, client):
        """H-02: GET / → HTML 응답, 200 OK."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_h03_web_ui_contains_submit_button(self, client):
        """H-03: Web UI HTML에 'Run Agent' 텍스트가 포함되어 있다."""
        resp = client.get("/")
        assert "Run Agent" in resp.text

    def test_h04_openapi_json_available(self, client):
        """H-04: /openapi.json 엔드포인트가 JSON을 반환한다."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert "/agent" in schema["paths"]


# ===========================================================================
# H-05 ~ H-09: POST /agent — 성공 케이스
# ===========================================================================

class TestAgentEndpointSuccess:

    def test_h05_agent_returns_200(self, client):
        """H-05: POST /agent → 200 OK."""
        resp = client.post("/agent", json=_agent_request())
        assert resp.status_code == 200

    def test_h06_response_has_required_keys(self, client):
        """H-06: 응답에 request_id, answer, citations, error_code, tool_call_log가 있다."""
        resp = client.post("/agent", json=_agent_request())
        body = resp.json()
        for key in ("request_id", "answer", "citations", "error_code", "tool_call_log"):
            assert key in body, f"Missing key: {key}"

    def test_h07_battle_context_parsed_true(self, client):
        """H-07: battle_situation이 제공되면 battle_context_parsed=true."""
        resp = client.post("/agent", json=_agent_request())
        assert resp.json()["battle_context_parsed"] is True

    def test_h08_no_battle_context_parsed_false(self, client):
        """H-08: battle_situation이 없으면 battle_context_parsed=false."""
        resp = client.post("/agent", json=_agent_request(battle_situation=None))
        assert resp.json()["battle_context_parsed"] is False

    def test_h09_agent_without_battle_context(self, client):
        """H-09: battle_situation 없이도 /agent 호출이 성공한다."""
        resp = client.post("/agent", json={
            "query": "방산 도메인 질의 테스트",
            "agent_mode": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        # answer may be empty when MockLLM returns empty content (no docs indexed)
        # — key existence is sufficient for structural proof
        assert "answer" in body


# ===========================================================================
# H-10 ~ H-13: POST /agent — 실패/에지 케이스
# ===========================================================================

class TestAgentEndpointEdgeCases:

    def test_h10_missing_query_returns_422(self, client):
        """H-10: query 필드가 없으면 422 Unprocessable Entity."""
        resp = client.post("/agent", json={"battle_situation": _MINIMAL_SCENARIO})
        assert resp.status_code == 422

    def test_h11_invalid_battle_situation_returns_422(self, client):
        """H-11: 필수 필드가 없는 battle_situation은 422를 반환한다."""
        bad_scenario = {"scenario_id": "BAD", "timestamp": "2026-03-26T00:00:00Z"}
        # 'threat', 'friendly_forces', 'query' 누락
        resp = client.post("/agent", json=_agent_request(battle_situation=bad_scenario))
        assert resp.status_code == 422

    def test_h12_invalid_threat_type_returns_422(self, client):
        """H-12: threat.type이 허용되지 않은 값이면 422를 반환한다."""
        bad = {**_MINIMAL_SCENARIO}
        bad["threat"] = {**_MINIMAL_SCENARIO["threat"], "type": "ZOMBIE"}
        resp = client.post("/agent", json=_agent_request(battle_situation=bad))
        assert resp.status_code == 422

    def test_h13_use_composite_flag_accepted(self, client):
        """H-13: use_composite=true로 요청해도 200을 반환한다."""
        resp = client.post("/agent", json=_agent_request(use_composite=True))
        assert resp.status_code == 200


# ===========================================================================
# H-14 ~ H-16: POST /agent/upload — 파일 업로드
# ===========================================================================

class TestAgentUploadEndpoint:

    def test_h14_upload_valid_json_file(self, client):
        """H-14: 유효한 JSON 파일 업로드 → 200 OK, battle_context_parsed=true."""
        json_bytes = json.dumps(_MINIMAL_SCENARIO).encode("utf-8")
        resp = client.post(
            "/agent/upload",
            params={"query": "위협을 평가하라", "agent_mode": True},
            files={"battle_situation_file": ("scenario.json", io.BytesIO(json_bytes), "application/json")},
        )
        assert resp.status_code == 200
        assert resp.json()["battle_context_parsed"] is True

    def test_h15_upload_no_file_uses_query_only(self, client):
        """H-15: 파일 없이 query만 전송해도 200을 반환한다."""
        resp = client.post(
            "/agent/upload",
            params={"query": "일반 질의 테스트"},
        )
        assert resp.status_code == 200
        assert resp.json()["battle_context_parsed"] is False

    def test_h16_upload_invalid_json_returns_422(self, client):
        """H-16: JSON이 아닌 파일 업로드 → 422."""
        bad_bytes = b"this is not json {{{"
        resp = client.post(
            "/agent/upload",
            params={"query": "테스트"},
            files={"battle_situation_file": ("bad.json", io.BytesIO(bad_bytes), "application/json")},
        )
        assert resp.status_code == 422
