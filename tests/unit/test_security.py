"""Unit tests for security module — target ≥80% coverage (UF-040, UF-041)."""

import pytest

from defense_llm.security.rbac import check_access, filter_results_by_clearance
from defense_llm.security.masking import mask_output, MASK_TOKEN


# ---------------------------------------------------------------------------
# UF-040: RBAC/ABAC Access Control
# ---------------------------------------------------------------------------

class TestCheckAccess:
    def test_public_user_public_resource_allowed(self):
        result = check_access(
            user={"role": "guest", "clearance": "PUBLIC"},
            resource_security_labels=["PUBLIC"],
        )
        assert result["allowed"] is True

    def test_public_user_secret_resource_denied(self):
        result = check_access(
            user={"role": "guest", "clearance": "PUBLIC"},
            resource_security_labels=["SECRET"],
        )
        assert result["allowed"] is False
        assert "insufficient" in result["reason"].lower()

    def test_secret_user_restricted_resource_allowed(self):
        result = check_access(
            user={"role": "admin", "clearance": "SECRET"},
            resource_security_labels=["RESTRICTED"],
        )
        assert result["allowed"] is True

    def test_internal_user_restricted_denied(self):
        result = check_access(
            user={"role": "analyst", "clearance": "INTERNAL"},
            resource_security_labels=["RESTRICTED"],
        )
        assert result["allowed"] is False

    def test_role_field_restriction(self):
        result = check_access(
            user={"role": "air_analyst", "clearance": "INTERNAL"},
            resource_security_labels=["INTERNAL"],
            resource_field="weapon",
        )
        assert result["allowed"] is False
        assert "field" in result["reason"].lower()

    def test_admin_all_fields_allowed(self):
        for field in ["air", "weapon", "ground", "sensor", "comm"]:
            result = check_access(
                user={"role": "admin", "clearance": "SECRET"},
                resource_security_labels=["SECRET"],
                resource_field=field,
            )
            assert result["allowed"] is True, f"Admin should access field {field}"

    def test_multiple_labels_all_must_pass(self):
        result = check_access(
            user={"role": "analyst", "clearance": "INTERNAL"},
            resource_security_labels=["PUBLIC", "SECRET"],
        )
        assert result["allowed"] is False

    def test_missing_clearance_defaults_to_public(self):
        result = check_access(
            user={"role": "guest"},
            resource_security_labels=["PUBLIC"],
        )
        assert result["allowed"] is True


class TestFilterResultsByClearance:
    def test_filters_out_higher_labels(self):
        results = [
            {"security_label": "PUBLIC", "doc_field": "air", "text": "공개"},
            {"security_label": "SECRET", "doc_field": "air", "text": "기밀"},
        ]
        user = {"role": "analyst", "clearance": "INTERNAL"}
        filtered = filter_results_by_clearance(results, user)
        assert len(filtered) == 1
        assert filtered[0]["security_label"] == "PUBLIC"

    def test_allows_matching_clearance(self):
        results = [
            {"security_label": "INTERNAL", "doc_field": "air", "text": "내부"},
        ]
        user = {"role": "analyst", "clearance": "INTERNAL"}
        filtered = filter_results_by_clearance(results, user)
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# UF-041: Output Masking
# ---------------------------------------------------------------------------

class TestMaskOutput:
    def test_coordinate_masked(self):
        text = "목표 위도 37.1234, 경도 127.5678에 위치"
        result = mask_output(text, mask_rules=["coordinates"])
        assert MASK_TOKEN in result["masked_text"]
        assert result["masked_count"] >= 1

    def test_frequency_masked(self):
        text = "레이더 운용 주파수 9.75 GHz 대역"
        result = mask_output(text, mask_rules=["frequency"])
        assert MASK_TOKEN in result["masked_text"]
        assert result["masked_count"] >= 1

    def test_non_sensitive_text_unchanged(self):
        text = "항공기 최대 고도 15000m"
        result = mask_output(text, mask_rules=["coordinates", "frequency", "sys_id"])
        assert result["masked_text"] == text
        assert result["masked_count"] == 0

    def test_masked_count_accurate(self):
        text = "주파수 2.4 GHz 및 5.8 GHz 운용"
        result = mask_output(text, mask_rules=["frequency"])
        assert result["masked_count"] == 2

    def test_all_rules_applied_by_default(self):
        text = "좌표 위도 37.1234, 경도 127.5678, 주파수 9.75 GHz"
        result = mask_output(text)
        assert result["masked_count"] >= 2

    def test_unknown_rule_name_ignored(self):
        text = "항공 정보"
        result = mask_output(text, mask_rules=["nonexistent_rule"])
        assert result["masked_text"] == text
        assert result["masked_count"] == 0

    def test_sys_id_masked(self):
        # Pattern: 2-4 uppercase letters + hyphen + 3-8 digits
        text = "시스템 ID AB-12345 참조"
        result = mask_output(text, mask_rules=["sys_id"])
        assert MASK_TOKEN in result["masked_text"]
