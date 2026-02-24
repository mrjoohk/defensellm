"""Defense domain glossary / acronym mapping (UF-012)."""

from __future__ import annotations

from typing import Dict, Optional

# Default seed glossary (dummy / illustrative values — no real classified data)
_DEFAULT_GLOSSARY: Dict[str, str] = {
    "KF-21": "한국형 전투기 KF-21 보라매 (Korea Fighter 21)",
    "AAM": "공대공 미사일 (Air-to-Air Missile)",
    "AGM": "공대지 미사일 (Air-to-Ground Missile)",
    "SAM": "지대공 미사일 (Surface-to-Air Missile)",
    "AESA": "능동 위상 배열 레이더 (Active Electronically Scanned Array)",
    "RCS": "레이더 반사 단면적 (Radar Cross Section)",
    "BVR": "시계 외 교전 (Beyond Visual Range)",
    "HMD": "헬멧 마운트 디스플레이 (Helmet Mounted Display)",
    "IFF": "피아 식별 장치 (Identification Friend or Foe)",
    "TACAN": "전술 항법 장치 (Tactical Air Navigation)",
    "EW": "전자전 (Electronic Warfare)",
    "ISR": "정보·감시·정찰 (Intelligence, Surveillance, Reconnaissance)",
    "C2": "지휘통제 (Command and Control)",
    "FCS": "사격 통제 시스템 (Fire Control System)",
    "MFD": "다기능 디스플레이 (Multi-Function Display)",
}


class Glossary:
    """In-memory glossary with optional DB-backed extension.

    Args:
        entries: Optional additional entries to merge with defaults.
    """

    def __init__(self, entries: Optional[Dict[str, str]] = None) -> None:
        self._data: Dict[str, str] = dict(_DEFAULT_GLOSSARY)
        if entries:
            self._data.update(entries)

    def lookup(self, term: str) -> dict:
        """Lookup a term or acronym (UF-012).

        Args:
            term: The term or acronym to look up.

        Returns:
            dict with keys: term, definition, found.
        """
        definition = self._data.get(term) or self._data.get(term.upper())
        return {
            "term": term,
            "definition": definition,
            "found": definition is not None,
        }

    def add(self, term: str, definition: str) -> None:
        """Add or update a glossary entry."""
        self._data[term] = definition

    def normalize_text(self, text: str) -> str:
        """Replace known acronyms in text with their full forms."""
        for acronym, full in self._data.items():
            text = text.replace(acronym, f"{acronym}({full})")
        return text

    def all_terms(self) -> Dict[str, str]:
        return dict(self._data)
