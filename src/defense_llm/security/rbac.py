"""RBAC/ABAC access control (UF-040)."""

from __future__ import annotations

from typing import List, Optional

# Clearance hierarchy: higher index = higher clearance
_CLEARANCE_ORDER = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]

# Role → allowed fields mapping (ABAC)
_ROLE_FIELD_PERMISSIONS: dict = {
    "admin": {"air", "weapon", "ground", "sensor", "comm"},
    "air_analyst": {"air", "sensor"},
    "weapon_analyst": {"weapon"},
    "ground_analyst": {"ground"},
    "comm_analyst": {"comm", "sensor"},
    "analyst": {"air", "weapon", "ground", "sensor", "comm"},
    "guest": {"air"},  # minimal access
}


def _clearance_level(label: str) -> int:
    """Return integer level for a security label (0 = PUBLIC, 3 = SECRET)."""
    label = label.upper()
    return _CLEARANCE_ORDER.index(label) if label in _CLEARANCE_ORDER else 0


def check_access(user: dict, resource_security_labels: List[str], resource_field: Optional[str] = None) -> dict:
    """Check whether a user may access a resource (UF-040).

    Implements RBAC (field-based) + ABAC (clearance-based).

    Args:
        user: Dict with keys: role (str), clearance (str).
        resource_security_labels: List of security labels the resource holds.
        resource_field: Optional domain field of the resource.

    Returns:
        dict: { allowed: bool, reason: str }
    """
    user_clearance = user.get("clearance", "PUBLIC").upper()
    user_role = user.get("role", "guest")

    user_level = _clearance_level(user_clearance)

    # Check clearance against ALL requested resource labels
    for label in resource_security_labels:
        required_level = _clearance_level(label)
        if user_level < required_level:
            return {
                "allowed": False,
                "reason": (
                    f"User clearance '{user_clearance}' (level {user_level}) "
                    f"insufficient for resource label '{label}' (level {required_level})."
                ),
            }

    # Check field-level ABAC if field is specified
    if resource_field:
        allowed_fields = _ROLE_FIELD_PERMISSIONS.get(user_role, set())
        if resource_field not in allowed_fields:
            return {
                "allowed": False,
                "reason": (
                    f"Role '{user_role}' is not permitted to access field '{resource_field}'."
                ),
            }

    return {"allowed": True, "reason": "Access granted."}


def filter_results_by_clearance(results: List[dict], user: dict) -> List[dict]:
    """Post-search filter: remove results the user cannot access."""
    allowed = []
    for result in results:
        label = result.get("security_label", "PUBLIC")
        access = check_access(user, [label], result.get("doc_field"))
        if access["allowed"]:
            allowed.append(result)
    return allowed
