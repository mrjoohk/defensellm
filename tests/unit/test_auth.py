"""Unit tests for security/auth.py — JWT issuance and verification (P0)."""

import time
import pytest

from defense_llm.security.auth import (
    JWTAuthManager,
    extract_user_context,
    E_AUTH,
    E_VALIDATION,
)

_SECRET = "this-is-a-test-secret-key-for-unit-tests-only"


class TestJWTAuthManager:
    def test_issue_and_verify_token(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("user-001", "analyst", "INTERNAL")
        payload = mgr.verify_token(token)
        assert payload["sub"] == "user-001"
        assert payload["role"] == "analyst"
        assert payload["clearance"] == "INTERNAL"

    def test_payload_has_exp_and_iat(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("u1", "guest", "PUBLIC")
        payload = mgr.verify_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_payload_has_jti(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("u1", "admin", "SECRET")
        payload = mgr.verify_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_tampered_token_raises_permission_error(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("u1", "analyst", "INTERNAL")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(PermissionError, match=E_AUTH):
            mgr.verify_token(tampered)

    def test_wrong_secret_raises_permission_error(self):
        mgr1 = JWTAuthManager(secret_key=_SECRET)
        mgr2 = JWTAuthManager(secret_key="different-secret-key-totally-wrong-abcdefgh")
        token = mgr1.issue_token("u1", "analyst", "INTERNAL")
        with pytest.raises(PermissionError, match=E_AUTH):
            mgr2.verify_token(token)

    def test_expired_token_raises_permission_error(self):
        mgr = JWTAuthManager(secret_key=_SECRET, ttl_seconds=1)
        token = mgr.issue_token("u1", "analyst", "INTERNAL")
        time.sleep(2)
        with pytest.raises(PermissionError, match=E_AUTH):
            mgr.verify_token(token)

    def test_short_secret_raises_validation_error(self):
        with pytest.raises(ValueError, match=E_VALIDATION):
            JWTAuthManager(secret_key="tooshort")

    def test_empty_secret_raises_validation_error(self):
        with pytest.raises(ValueError, match=E_VALIDATION):
            JWTAuthManager(secret_key="")

    def test_env_var_secret(self, monkeypatch):
        monkeypatch.setenv(
            "DEFENSE_LLM_JWT_SECRET",
            "env-based-secret-key-long-enough-abcdef"
        )
        mgr = JWTAuthManager()
        token = mgr.issue_token("u1", "guest", "PUBLIC")
        payload = mgr.verify_token(token)
        assert payload["sub"] == "u1"

    def test_two_tokens_have_different_jti(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        t1 = mgr.issue_token("u1", "analyst", "INTERNAL")
        t2 = mgr.issue_token("u1", "analyst", "INTERNAL")
        p1 = mgr.verify_token(t1)
        p2 = mgr.verify_token(t2)
        assert p1["jti"] != p2["jti"]


class TestExtractUserContext:
    def test_returns_correct_fields(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("user-analyst", "analyst", "INTERNAL")
        ctx = extract_user_context(token, mgr)
        assert ctx["user_id"] == "user-analyst"
        assert ctx["role"] == "analyst"
        assert ctx["clearance"] == "INTERNAL"

    def test_invalid_token_raises(self):
        mgr = JWTAuthManager(secret_key=_SECRET)
        with pytest.raises(PermissionError, match=E_AUTH):
            extract_user_context("not.a.valid.token", mgr)

    def test_user_context_integrates_with_rbac(self):
        from defense_llm.security.rbac import check_access
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("u1", "analyst", "INTERNAL")
        ctx = extract_user_context(token, mgr)
        result = check_access(
            user=ctx,
            resource_security_labels=["INTERNAL"],
            resource_field="air",
        )
        assert result["allowed"] is True

    def test_public_context_denied_secret_resource(self):
        from defense_llm.security.rbac import check_access
        mgr = JWTAuthManager(secret_key=_SECRET)
        token = mgr.issue_token("u1", "guest", "PUBLIC")
        ctx = extract_user_context(token, mgr)
        result = check_access(
            user=ctx,
            resource_security_labels=["SECRET"],
        )
        assert result["allowed"] is False
