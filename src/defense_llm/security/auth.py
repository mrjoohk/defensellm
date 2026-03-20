"""JWT-based user authentication and session validation (P0 — 사용자 인증).

Provides:
- JWTAuthManager: token issuance + verification
- extract_user_context(): decode JWT → user_context dict for Executor
- Integrates with RBAC by returning clearance + role from the token claims

Token payload schema:
  {
    "sub":       str  — user identifier
    "role":      str  — RBAC role (admin / analyst / air_analyst / guest …)
    "clearance": str  — clearance level (PUBLIC / INTERNAL / RESTRICTED / SECRET)
    "exp":       int  — Unix expiry timestamp
    "iat":       int  — issued-at timestamp
  }
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

E_AUTH = "E_AUTH"
E_VALIDATION = "E_VALIDATION"

_DEFAULT_ALGORITHM = "HS256"
_DEFAULT_TTL_SECONDS = 3600  # 1 hour

# Minimum secret key length to prevent weak keys
_MIN_SECRET_LEN = 32


class JWTAuthManager:
    """Issues and verifies HS256 JWT tokens.

    Args:
        secret_key: HMAC signing secret. Must be ≥ 32 characters.
                    If not provided, reads from env var DEFENSE_LLM_JWT_SECRET.
        algorithm: JWT algorithm (default HS256).
        ttl_seconds: Token lifetime in seconds (default 3600).
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = _DEFAULT_ALGORITHM,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        key = secret_key or os.environ.get("DEFENSE_LLM_JWT_SECRET", "")
        if not key or len(key) < _MIN_SECRET_LEN:
            raise ValueError(
                f"{E_VALIDATION}: JWT secret key must be at least {_MIN_SECRET_LEN} characters. "
                "Set via DEFENSE_LLM_JWT_SECRET env var or pass secret_key parameter."
            )
        self._secret = key
        self._algorithm = algorithm
        self._ttl = ttl_seconds

    def issue_token(self, user_id: str, role: str, clearance: str) -> str:
        """Create and sign a JWT for the given user.

        Args:
            user_id: Unique user identifier.
            role: RBAC role string.
            clearance: Security clearance level.

        Returns:
            Signed JWT string.
        """
        try:
            import jwt
        except ImportError as e:
            raise RuntimeError(
                f"{E_INTERNAL}: PyJWT is not installed. Run: pip install PyJWT"
            ) from e

        now = int(time.time())
        payload = {
            "sub": user_id,
            "role": role,
            "clearance": clearance,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_token(self, token: str) -> dict:
        """Verify and decode a JWT token.

        Args:
            token: The JWT string to verify.

        Returns:
            Decoded payload dict.

        Raises:
            PermissionError: (E_AUTH) if token is invalid, expired, or tampered.
        """
        try:
            import jwt
            from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
        except ImportError as e:
            raise RuntimeError("PyJWT is not installed.") from e

        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
            )
            return payload
        except ExpiredSignatureError:
            raise PermissionError(f"{E_AUTH}: Token has expired.")
        except InvalidTokenError as e:
            raise PermissionError(f"{E_AUTH}: Invalid token: {e}")


def extract_user_context(token: str, auth_manager: JWTAuthManager) -> dict:
    """Decode a JWT and return a user_context dict for use with Executor.

    Args:
        token: JWT string from the request.
        auth_manager: JWTAuthManager instance.

    Returns:
        user_context dict: { user_id, role, clearance }

    Raises:
        PermissionError: (E_AUTH) on invalid/expired token.
    """
    payload = auth_manager.verify_token(token)
    return {
        "user_id": payload.get("sub", "unknown"),
        "role": payload.get("role", "guest"),
        "clearance": payload.get("clearance", "PUBLIC"),
    }


# Convenience: reference to E_INTERNAL (avoids circular import)
E_INTERNAL = "E_INTERNAL"
