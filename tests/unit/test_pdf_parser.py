"""Unit tests for UF-025 — pdf_parser.py.

Test strategy
-------------
* All tests run offline (no network access).
* opendataloader_pdf (Java) is called for real text-layer PDFs; mocked otherwise.
* pytesseract / pdf2image are always mocked to avoid Poppler/Tesseract binary
  dependency during CI (only eng language pack guaranteed on test runners).

Success paths tested
--------------------
1. Text-layer PDF  → opendataloader_pdf extracts text correctly.
2. Image-based PDF → OCR fallback triggered automatically (avg chars/page < threshold).
3. force_ocr=True  → OCR is always applied, bypassing text extraction.
4. Page markers    → [PAGE N] tokens present in output.
5. is_image_based_pdf() correctly classifies PDFs.

Failure paths tested
--------------------
6. File not found  → FileNotFoundError.
7. Non-PDF file    → ValueError(E_VALIDATION).
8. Both extraction methods fail → RuntimeError(E_OCR_FAILED).
9. Empty output after extraction → RuntimeError(E_OCR_FAILED).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TEXT_PDF_CONTENT = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R
/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>
endobj
4 0 obj<</Length 50>>
stream
BT /F1 12 Tf 100 700 Td (Defense LLM Test Page) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000350 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
452
%%EOF"""


@pytest.fixture()
def text_pdf(tmp_path: Path) -> Path:
    """A minimal valid PDF with a text layer (used for real opendataloader_pdf calls)."""
    pdf = tmp_path / "text_doc.pdf"
    pdf.write_bytes(SAMPLE_TEXT_PDF_CONTENT)
    return pdf


@pytest.fixture()
def image_pdf(tmp_path: Path) -> Path:
    """A PDF whose text extraction returns an empty string (simulates image-based PDF)."""
    pdf = tmp_path / "image_doc.pdf"
    pdf.write_bytes(SAMPLE_TEXT_PDF_CONTENT)  # bytes don't matter; extraction is mocked
    return pdf


@pytest.fixture()
def txt_file(tmp_path: Path) -> Path:
    txt = tmp_path / "not_a_pdf.txt"
    txt.write_text("hello world", encoding="utf-8")
    return txt


# ---------------------------------------------------------------------------
# Helper — ODL extract mock
# ---------------------------------------------------------------------------

def _mock_odl_extract(text: str):
    """Return a patcher that makes _odl_extract return ``text``."""
    return patch(
        "defense_llm.rag.pdf_parser._odl_extract",
        return_value=text,
    )


def _mock_ocr_extract(text: str):
    """Return a patcher that makes _ocr_extract return ``text``."""
    return patch(
        "defense_llm.rag.pdf_parser._ocr_extract",
        return_value=text,
    )


# ---------------------------------------------------------------------------
# 1. Text-layer PDF — primary extraction succeeds
# ---------------------------------------------------------------------------

class TestTextLayerPDF:
    RICH_TEXT = "[PAGE 1]\n" + "Defense doctrine content. " * 20

    def test_returns_extracted_text(self, text_pdf):
        with _mock_odl_extract(self.RICH_TEXT):
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            result = extract_text_from_pdf(str(text_pdf))
        assert "Defense doctrine content." in result

    def test_page_marker_present(self, text_pdf):
        with _mock_odl_extract(self.RICH_TEXT):
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            result = extract_text_from_pdf(str(text_pdf))
        assert "[PAGE 1]" in result

    def test_ocr_not_called_for_rich_text(self, text_pdf):
        with _mock_odl_extract(self.RICH_TEXT), \
             patch("defense_llm.rag.pdf_parser._ocr_extract") as mock_ocr:
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            extract_text_from_pdf(str(text_pdf))
        mock_ocr.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Image-based PDF — OCR fallback triggered automatically
# ---------------------------------------------------------------------------

class TestImageBasedPDF:
    SPARSE_TEXT = "[PAGE 1]\nABC"          # < 50 chars/page → triggers OCR
    OCR_RESULT = "[PAGE 1]\nScanned text extracted via OCR."

    def test_ocr_called_when_sparse(self, image_pdf):
        with _mock_odl_extract(self.SPARSE_TEXT), \
             _mock_ocr_extract(self.OCR_RESULT) as mock_ocr:
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            result = extract_text_from_pdf(str(image_pdf))
        mock_ocr.assert_called_once()
        assert "Scanned text" in result

    def test_ocr_language_forwarded(self, image_pdf):
        with _mock_odl_extract(self.SPARSE_TEXT), \
             _mock_ocr_extract(self.OCR_RESULT) as mock_ocr:
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            extract_text_from_pdf(str(image_pdf), language="kor+eng")
        mock_ocr.assert_called_once_with(str(image_pdf), language="kor+eng")


# ---------------------------------------------------------------------------
# 3. force_ocr=True — always OCR
# ---------------------------------------------------------------------------

class TestForceOCR:
    OCR_RESULT = "[PAGE 1]\nForced OCR result."

    def test_skips_text_extraction(self, text_pdf):
        with patch("defense_llm.rag.pdf_parser._odl_extract") as mock_odl, \
             _mock_ocr_extract(self.OCR_RESULT):
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            extract_text_from_pdf(str(text_pdf), force_ocr=True)
        mock_odl.assert_not_called()

    def test_returns_ocr_text(self, text_pdf):
        with _mock_ocr_extract(self.OCR_RESULT):
            from defense_llm.rag.pdf_parser import extract_text_from_pdf
            result = extract_text_from_pdf(str(text_pdf), force_ocr=True)
        assert "Forced OCR result." in result


# ---------------------------------------------------------------------------
# 4. is_image_based_pdf helper
# ---------------------------------------------------------------------------

class TestIsImageBasedPDF:
    def test_rich_text_pdf_not_image_based(self, text_pdf):
        rich = "[PAGE 1]\n" + "x " * 200
        with _mock_odl_extract(rich):
            from defense_llm.rag.pdf_parser import is_image_based_pdf
            assert is_image_based_pdf(str(text_pdf)) is False

    def test_sparse_text_pdf_is_image_based(self, image_pdf):
        with _mock_odl_extract("[PAGE 1]\nABC"):
            from defense_llm.rag.pdf_parser import is_image_based_pdf
            assert is_image_based_pdf(str(image_pdf)) is True

    def test_extraction_error_returns_true(self, image_pdf):
        with patch("defense_llm.rag.pdf_parser._odl_extract", side_effect=RuntimeError("fail")):
            from defense_llm.rag.pdf_parser import is_image_based_pdf
            assert is_image_based_pdf(str(image_pdf)) is True


# ---------------------------------------------------------------------------
# 5. Real opendataloader_pdf call (integration-lite, skipped if Java/reportlab missing)
# ---------------------------------------------------------------------------

def _make_reportlab_pdf(path: Path) -> bool:
    """Create a valid PDF with reportlab. Returns False if reportlab not available."""
    try:
        from reportlab.pdfgen import canvas  # type: ignore[import]
        c = canvas.Canvas(str(path))
        c.drawString(72, 720, "Defense LLM OCR Test — Page 1")
        c.drawString(72, 700, "This is a text-layer PDF with extractable content.")
        c.save()
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    os.system("java -version > /dev/null 2>&1") != 0,
    reason="Java not available — opendataloader_pdf requires Java 11+",
)
class TestRealODLExtract:
    def test_real_text_layer_pdf(self, tmp_path):
        """Smoke test: opendataloader_pdf actually extracts text from a valid PDF."""
        pdf_path = tmp_path / "reportlab_test.pdf"
        if not _make_reportlab_pdf(pdf_path):
            pytest.skip("reportlab not installed — cannot create a valid test PDF")

        from defense_llm.rag.pdf_parser import _odl_extract
        result = _odl_extract(str(pdf_path))
        assert isinstance(result, str)
        assert len(result) > 10  # Should have extracted meaningful text


# ---------------------------------------------------------------------------
# 6. Failure — file not found
# ---------------------------------------------------------------------------

def test_file_not_found_raises():
    from defense_llm.rag.pdf_parser import extract_text_from_pdf
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf("/nonexistent/path/file.pdf")


# ---------------------------------------------------------------------------
# 7. Failure — non-PDF file
# ---------------------------------------------------------------------------

def test_non_pdf_raises(txt_file):
    from defense_llm.rag.pdf_parser import extract_text_from_pdf
    with pytest.raises(ValueError, match="E_VALIDATION"):
        extract_text_from_pdf(str(txt_file))


# ---------------------------------------------------------------------------
# 8. Failure — both methods fail → E_OCR_FAILED
# ---------------------------------------------------------------------------

def test_both_methods_fail_raises(image_pdf):
    sparse = "[PAGE 1]\nAB"   # triggers OCR path
    with _mock_odl_extract(sparse), \
         patch("defense_llm.rag.pdf_parser._ocr_extract", side_effect=RuntimeError("OCR fail")):
        from defense_llm.rag.pdf_parser import extract_text_from_pdf
        with pytest.raises(RuntimeError, match="E_OCR_FAILED"):
            extract_text_from_pdf(str(image_pdf))


# ---------------------------------------------------------------------------
# 9. Failure — empty output after all extraction
# ---------------------------------------------------------------------------

def test_empty_output_raises(image_pdf):
    with _mock_odl_extract(""), \
         _mock_ocr_extract(""):
        from defense_llm.rag.pdf_parser import extract_text_from_pdf
        with pytest.raises(RuntimeError, match="E_OCR_FAILED"):
            extract_text_from_pdf(str(image_pdf))


# ---------------------------------------------------------------------------
# 10. _needs_ocr threshold logic
# ---------------------------------------------------------------------------

class TestNeedsOCR:
    def test_below_threshold_triggers_ocr(self):
        from defense_llm.rag.pdf_parser import _needs_ocr
        sparse = "[PAGE 1]\nHi"
        assert _needs_ocr(sparse, threshold=50) is True

    def test_above_threshold_no_ocr(self):
        from defense_llm.rag.pdf_parser import _needs_ocr
        rich = "[PAGE 1]\n" + "a" * 200
        assert _needs_ocr(rich, threshold=50) is False

    def test_multi_page_uses_average(self):
        from defense_llm.rag.pdf_parser import _needs_ocr
        # 2 pages, 200 chars total → 100 avg > 50 threshold
        text = "[PAGE 1]\n" + "a" * 100 + "\n[PAGE 2]\n" + "b" * 100
        assert _needs_ocr(text, threshold=50) is False
