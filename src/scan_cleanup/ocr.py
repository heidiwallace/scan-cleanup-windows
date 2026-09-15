"""Adds an invisible, searchable text layer to the final PDF via ocrmypdf."""

import os
import shutil
import sys
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
pip/uv — they must be installed separately, like installing an app.

On Windows:

  1. Tesseract — install the UB Mannheim build from
       https://github.com/UB-Mannheim/tesseract/wiki
     A standard install to its default location (C:\Program Files\Tesseract-OCR)
     is found automatically — no PATH changes needed. English language data
     is included by default. A package manager also works:
       winget install UB-Mannheim.TesseractOCR

  2. Ghostscript — install the 64-bit release from
       https://ghostscript.com/releases/gsdnld.html
     A standard install to its default location (C:\Program Files\gs\...) is
     found automatically — no PATH changes needed. Only add its "bin" folder
     to PATH by hand if you installed it somewhere nonstandard.

  3. Close and reopen your terminal, then run scan-cleanup again.

See the README's Installation section for more detail.
""".strip()


class MissingSystemDependencyError(RuntimeError):
    """Raised when a required non-Python program (Tesseract, Ghostscript) is missing."""


def _find_windows_ghostscript_bin_dir() -> Path | None:
    """Locate Ghostscript's "bin" folder in its default Windows install location.

    Unlike the Tesseract build this project documents, Ghostscript's Windows
    installer has no "Add to PATH" option at all (confirmed against its own
    install docs), so a completely standard install still leaves gswin64c.exe
    unreachable by name. Mirrors scantailor.py's resolve_scantailor() fixed-
    location fallback for the same reason: PATH can't be relied on here.
    """
    program_roots = (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
    matches: list[Path] = []
    for root in filter(None, program_roots):
        gs_root = Path(root, "gs")
        matches.extend(gs_root.glob("gs*/bin/gswin64c.exe"))
        matches.extend(gs_root.glob("gs*/bin/gswin32c.exe"))
    if not matches:
        return None
    # If more than one version is installed, prefer the highest version folder
    # name (e.g. "gs10.03.1" over "gs10.02.0").
    matches.sort(key=lambda path: path.parent.parent.name)
    return matches[-1].parent


def _find_windows_tesseract_dir() -> Path | None:
    """Locate Tesseract's install folder in its default Windows location.

    The UB Mannheim installer this project documents does offer an "Add to
    PATH" checkbox, but in practice this has been observed not to take
    effect reliably (confirmed: a user with Tesseract genuinely installed
    still got "not recognized" from a fresh terminal). Falling back to the
    standard install location, the same way Ghostscript already is, avoids
    depending on that checkbox actually working.
    """
    program_roots = (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
    for root in filter(None, program_roots):
        candidate = Path(root, "Tesseract-OCR")
        if (candidate / "tesseract.exe").is_file():
            return candidate
    return None


def _ensure_windows_ghostscript_discoverable() -> None:
    """Make a standard Ghostscript install visible to shutil.which and ocrmypdf.

    ocrmypdf shells out to "gswin64c" by name; if it isn't already on PATH,
    prepending its discovered folder to this process's PATH makes it visible
    both to the check below and to every subprocess ocrmypdf launches
    afterwards (subprocesses inherit the parent's environment).
    """
    if any(shutil.which(command) for command in ("gswin64c", "gswin32c", "gs")):
        return
    bin_dir = _find_windows_ghostscript_bin_dir()
    if bin_dir is not None:
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def _ensure_windows_tesseract_discoverable() -> None:
    """Make a standard Tesseract install visible to shutil.which and ocrmypdf."""
    if shutil.which("tesseract"):
        return
    tesseract_dir = _find_windows_tesseract_dir()
    if tesseract_dir is not None:
        os.environ["PATH"] = str(tesseract_dir) + os.pathsep + os.environ.get("PATH", "")


def check_system_dependencies() -> None:
    if sys.platform == "win32":
        _ensure_windows_ghostscript_discoverable()
        _ensure_windows_tesseract_discoverable()
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
