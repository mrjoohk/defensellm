"""Output masking for sensitive information (UF-041)."""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Tuple

MASK_TOKEN = "[REDACTED]"

# ---------------------------------------------------------------------------
# Masking rule patterns
# ---------------------------------------------------------------------------

_MASK_RULES: Dict[str, Pattern] = {
    # Latitude/Longitude coordinates: e.g. 37.1234, 127.5678 or N37°12'34" E127°34'56"
    "coordinates": re.compile(
        r"(?:"
        r"[NS]?\s*\d{1,3}[°\s]\d{1,2}['′\s]\d{1,2}[\"″\s]?[NS]?[\s,]+"
        r"[EW]?\s*\d{1,3}[°\s]\d{1,2}['′\s]\d{1,2}[\"″\s]?[EW]?"
        r"|위도\s*[-+]?\d{1,3}(?:\.\d+)?[\s,]+경도\s*[-+]?\d{1,3}(?:\.\d+)?"
        r"|[-+]?\d{1,3}\.\d{3,}[,\s]+[-+]?\d{1,3}\.\d{3,}"
        r")",
        re.IGNORECASE,
    ),
    # Frequency values: e.g. 9.75 GHz, 450 MHz, 1.2 THz
    "frequency": re.compile(
        r"\d+(?:\.\d+)?\s*(?:GHz|MHz|kHz|THz|Hz)\b",
        re.IGNORECASE,
    ),
    # System identifiers: alphanumeric codes that look like classified IDs
    # Pattern: 2-4 uppercase letters followed by hyphen and 3-8 digits/letters
    "sys_id": re.compile(
        r"\b[A-Z]{2,4}-\d{3,8}\b",
    ),
}

_ALL_RULE_NAMES = set(_MASK_RULES.keys())


def mask_output(text: str, mask_rules: List[str] = None) -> dict:
    """Apply masking rules to output text (UF-041).

    Args:
        text: The text to mask.
        mask_rules: List of rule names to apply. Defaults to all rules.

    Returns:
        dict: { masked_text: str, masked_count: int }
    """
    if mask_rules is None:
        mask_rules = list(_ALL_RULE_NAMES)

    masked_text = text
    total_count = 0

    for rule_name in mask_rules:
        pattern = _MASK_RULES.get(rule_name)
        if pattern is None:
            continue
        matches = pattern.findall(masked_text)
        total_count += len(matches)
        masked_text = pattern.sub(MASK_TOKEN, masked_text)

    return {"masked_text": masked_text, "masked_count": total_count}
