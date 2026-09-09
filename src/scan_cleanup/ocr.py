"""Adds an invisible, searchable text layer to the final PDF via ocrmypdf."""

import shutil
from pathlib import Path

import ocrmypdf

from scan_cleanup.config import Recipe

# Each required program maps to a human-readable description and the command
# names it may be installed under, in preference order. Ghostscript's console
# executable is "gs" on macOS/Linux but "gswin64c" / "gswin32c" on Windows.
_REQUIRED_BINARIES = {
    "Tesseract": ("the OCR engine", ("tesseract",)),
    "Ghostscript": ("used to process the PDF", ("gswin64c", "gswin32c", "gs")),
}

_INSTALL_INSTRUCTIONS = r"""
scan-cleanup requires two non-Python programs to be installed before OCR can
run: Tesseract (the OCR engine) and Ghostscript. These are NOT installed by
pip/uv — they must be installed separately, like installing an app, and their
folders must be on your PATH.

On Windows:

  1. Tesseract — install the UB Mannheim build from
       https://github.com/UB-Mannheim/tesseract/wiki
     During setup, enable "Add to PATH" (or afterwards add its install folder,
     e.g. C:\Program Files\Tesseract-OCR, to your PATH by hand). English
     language data is included by default.

  2. Ghostscript — install the 64-bit release from
       https://ghostscript.com/releases/gsdnld.html
     Then add its "bin" folder (which contains gswin64c.exe, e.g.
     C:\Program Files\gs\gs10.03.1\bin) to your PATH.

  3. Close and reopen your terminal, then run scan-cleanup again.

With a package manager instead:
  winget install UB-Mannheim.TesseractOCR
  winget install ArtifexSoftware.GhostScript

See the README's Installation section for more detail.
""".strip()


class MissingSystemDependencyError(RuntimeError):
    """Raised when a required non-Python program (Tesseract, Ghostscript) is missing."""


def check_system_dependencies() -> None:
    missing = [
        (label, description)
        for label, (description, commands) in _REQUIRED_BINARIES.items()
        if not any(shutil.which(command) for command in commands)
    ]
    if missing:
        missing_desc = ", ".join(f"{label} ({description})" for label, description in missing)
        raise MissingSystemDependencyError(
            f"Missing required program(s): {missing_desc}.\n\n{_INSTALL_INSTRUCTIONS}"
        )


def add_ocr_layer(pdf_path: Path, output_path: Path, recipe: Recipe) -> None:
    check_system_dependencies()
    ocrmypdf.ocr(
        pdf_path,
        output_path,
        language=recipe.ocr_language,
        output_type=recipe.ocr_output_type,
        # ScanTailor has already processed the page images; avoid changing
        # their pixels again while adding the invisible text layer.
        deskew=False,
        clean=False,
        remove_background=False,
    )
