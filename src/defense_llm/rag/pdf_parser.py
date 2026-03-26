"""PDF text extraction with automatic OCR fallback (UF-025).

Strategy
--------
1. Primary extraction : ``opendataloader_pdf`` (Java-based, embedded JAR)
   - Handles text-layer PDFs with high fidelity
   - Produces page-separated plain text with ``[PAGE N]`` markers
   - Runs entirely offline (Java 11+ required)
2. OCR detection     : if extracted text < ``OCR_CHAR_THRESHOLD`` chars per page
   - Assume the PDF is image-based (scanned document)
3. OCR fallback      : ``pytesseract`` + ``pdf2image`` (poppler required)
   - Converts each PDF page to a PIL image
   - Applies Tesseract OCR per page, appending ``[PAGE N]`` markers
   - Use ``language="kor"`` or ``language="kor+eng"`` for Korean documents
                      (requires Tesseract Korean language pack)

System dependencies
-------------------
* Java 11+ (for opendataloader_pdf)
* Tesseract-OCR binary  (for pytesseract fallback)
* Poppler             (for pdf2image / pdftoppm)

Windows installation notes
--------------------------
* Java  : https://adoptium.net/
* Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
  - Add ``C:\\Program Files\\Tesseract-OCR`` to PATH
  - Install kor/kor_vert data files into tessdata folder
* Poppler: https://github.com/oschwartz10612/poppler-windows/releases/
  - Add ``<poppler>\\Library\\bin`` to PATH
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum average characters per page expected from a text-layer PDF.
#: Pages with fewer characters trigger OCR.
OCR_CHAR_THRESHOLD: int = 50

E_OCR_FAILED = "E_OCR_FAILED"
E_VALIDATION = "E_VALIDATION"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text_from_pdf(
    pdf_path: str,
    *,
    force_ocr: bool = False,
    language: str = "eng",
    keep_line_breaks: bool = True,
    ocr_char_threshold: int = OCR_CHAR_THRESHOLD,
) -> str:
    """Extract text from a PDF file, applying OCR when the document is image-based.

    Args:
        pdf_path: Absolute or relative path to the input PDF file.
        force_ocr: If ``True``, skip text-layer extraction and always apply OCR.
        language: Tesseract language code used during OCR.
            Examples: ``"eng"`` (English), ``"kor"`` (Korean),
            ``"kor+eng"`` (Korean + English).
            Run ``tesseract --list-langs`` to see available language packs.
        keep_line_breaks: Preserve original line breaks in the extracted text.
        ocr_char_threshold: Average characters-per-page below which OCR is
            triggered automatically.

    Returns:
        UTF-8 string with ``[PAGE N]`` markers between pages.

    Raises:
        FileNotFoundError: ``pdf_path`` does not exist.
        ValueError: ``(E_VALIDATION)`` Invalid arguments.
        RuntimeError: ``(E_OCR_FAILED)`` Both extraction methods failed.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"{E_VALIDATION}: File is not a PDF: {pdf_path}")

    if force_ocr:
        return _ocr_extract(str(path), language=language)

    # --- Step 1: primary extraction via opendataloader_pdf ---
    try:
        text = _odl_extract(str(path), keep_line_breaks=keep_line_breaks)
    except Exception as primary_err:  # noqa: BLE001
        # Primary extraction failed — fall through to OCR
        text = ""
        _warn(f"opendataloader_pdf extraction failed ({primary_err}); trying OCR…")

    # --- Step 2: detect image-based PDF ---
    if _needs_ocr(text, threshold=ocr_char_threshold):
        _warn(
            f"PDF appears to be image-based (avg chars/page < {ocr_char_threshold}). "
            "Applying OCR…"
        )
        try:
            text = _ocr_extract(str(path), language=language)
        except Exception as ocr_err:  # noqa: BLE001
            raise RuntimeError(
                f"{E_OCR_FAILED}: OCR extraction failed for {pdf_path}: {ocr_err}"
            ) from ocr_err

    if not text.strip():
        raise RuntimeError(
            f"{E_OCR_FAILED}: No text could be extracted from {pdf_path}. "
            "The file may be empty, password-protected, or corrupted."
        )

    return text


def is_image_based_pdf(pdf_path: str, threshold: int = OCR_CHAR_THRESHOLD) -> bool:
    """Quick check whether a PDF lacks embedded text (heuristic).

    Extracts text via opendataloader_pdf and checks average chars per page.
    Returns ``True`` if OCR would be triggered.
    """
    try:
        text = _odl_extract(pdf_path)
        return _needs_ocr(text, threshold=threshold)
    except Exception:  # noqa: BLE001
        return True  # Assume image-based if extraction fails


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _odl_extract(pdf_path: str, *, keep_line_breaks: bool = True) -> str:
    """Extract text using opendataloader_pdf (Java engine).

    Outputs a temporary text file and reads its contents.
    """
    from opendataloader_pdf import convert  # lazy import

    with tempfile.TemporaryDirectory() as tmpdir:
        convert(
            input_path=pdf_path,
            output_dir=tmpdir,
            format="text",
            quiet=True,
            keep_line_breaks=keep_line_breaks,
            text_page_separator="[PAGE %page-number%]",
        )
        # opendataloader_pdf names output after the stem of the input file
        stem = Path(pdf_path).stem
        out_file = Path(tmpdir) / f"{stem}.txt"
        if not out_file.exists():
            # Fallback: pick the first .txt file in the output dir
            txt_files = list(Path(tmpdir).glob("*.txt"))
            if not txt_files:
                return ""
            out_file = txt_files[0]

        return out_file.read_text(encoding="utf-8", errors="replace")


def _needs_ocr(text: str, threshold: int) -> bool:
    """Return True if ``text`` is too sparse to have come from a text-layer PDF."""
    # Count how many [PAGE N] markers we have to estimate page count
    import re

    pages = re.findall(r"\[PAGE\s+\d+\]", text)
    page_count = max(len(pages), 1)
    char_count = len(text.replace("\n", "").replace(" ", ""))
    avg = char_count / page_count
    return avg < threshold


def _ocr_extract(pdf_path: str, *, language: str = "eng") -> str:
    """Extract text via pytesseract OCR (pdf2image → Pillow → Tesseract).

    Args:
        pdf_path: Path to PDF file.
        language: Tesseract language code (e.g. ``"kor+eng"``).

    Returns:
        Page-separated text string with ``[PAGE N]`` markers.
    """
    try:
        from pdf2image import convert_from_path  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "pdf2image is not installed. Install it with: pip install pdf2image"
        ) from exc

    try:
        import pytesseract  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed. Install it with: pip install pytesseract"
        ) from exc

    # pdf2image / poppler may raise PDFInfoNotInstalledError or similar
    images = convert_from_path(pdf_path)

    parts: list[str] = []
    for page_num, img in enumerate(images, start=1):
        parts.append(f"[PAGE {page_num}]")
        page_text = pytesseract.image_to_string(img, lang=language)
        parts.append(page_text.strip())

    return "\n".join(parts)


def _warn(msg: str) -> None:
    """Emit a warning to stderr without raising."""
    import sys

    print(f"[pdf_parser WARNING] {msg}", file=sys.stderr)
