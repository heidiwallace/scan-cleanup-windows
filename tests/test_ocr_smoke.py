"""End-to-end OCR check (WINDOWS_PORT.md V2).

Runs the real ocrmypdf -> Tesseract -> Ghostscript pipeline. Skipped
automatically when those programs are absent, so it is a no-op in the normal
test run; the dedicated CI job installs them and selects it with `-m ocr_smoke`.
"""

import shutil

import img2pdf
import pymupdf
import pytest

from scan_cleanup._imageio import imwrite_unicode
from scan_cleanup.config import Recipe
from scan_cleanup.ocr import add_ocr_layer
from tests.conftest import make_text_page

_HAVE_TESSERACT = shutil.which("tesseract") is not None
_HAVE_GHOSTSCRIPT = any(shutil.which(name) for name in ("gswin64c", "gswin32c", "gs"))

pytestmark = [
    pytest.mark.ocr_smoke,
    pytest.mark.skipif(
        not (_HAVE_TESSERACT and _HAVE_GHOSTSCRIPT),
        reason="Tesseract and/or Ghostscript not installed",
    ),
]


def test_add_ocr_layer_completes_and_writes_valid_pdf(tmp_path):
    page_png = tmp_path / "page-01.png"
    assert imwrite_unicode(page_png, make_text_page())
    assembled = tmp_path / "assembled.pdf"
    assembled.write_bytes(img2pdf.convert([str(page_png)]))
    out_pdf = tmp_path / "ocr-output.pdf"

    add_ocr_layer(assembled, out_pdf, Recipe())

    assert out_pdf.is_file()
    with pymupdf.open(out_pdf) as doc:
        assert len(doc) == 1
