"""Windows-specific behaviour, exercised on any OS by faking the environment.

These lock in the changes described in WINDOWS_PORT.md (B1-B4, R1-R2, R4). They
do not require a Windows machine, ScanTailor, Tesseract, or Ghostscript.
"""

from __future__ import annotations

import errno
import logging

import cv2
import numpy as np
import pytest

from scan_cleanup import ocr, pipeline, scantailor, workspace
from scan_cleanup._imageio import imread_unicode, imwrite_unicode

# --- B1: Ghostscript command name --------------------------------------------


def test_ghostscript_accepted_under_windows_name(monkeypatch):
    present = {"tesseract", "gswin64c"}
    monkeypatch.setattr(ocr.shutil, "which", lambda name: name if name in present else None)
    ocr.check_system_dependencies()  # must not raise


def test_missing_ghostscript_names_the_program(monkeypatch):
    monkeypatch.setattr(
        ocr.shutil, "which", lambda name: "/usr/bin/tesseract" if name == "tesseract" else None
    )
    with pytest.raises(ocr.MissingSystemDependencyError, match="Ghostscript"):
        ocr.check_system_dependencies()


def test_all_dependencies_present_via_mixed_names(monkeypatch):
    present = {"tesseract", "gs"}
    monkeypatch.setattr(ocr.shutil, "which", lambda name: name if name in present else None)
    ocr.check_system_dependencies()


# --- B2: ScanTailor discovery on Windows ------------------------------------


def test_resolve_scantailor_finds_standard_windows_install(monkeypatch, tmp_path):
    exe = tmp_path / "ScanTailor Advanced" / "scantailor-advanced.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("stub")
    exe.chmod(0o755)  # os.access(X_OK) is meaningful on POSIX, always true on Windows

    monkeypatch.setattr(scantailor.sys, "platform", "win32")
    monkeypatch.setattr(scantailor.shutil, "which", lambda _name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    for other in ("ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
        monkeypatch.delenv(other, raising=False)

    assert scantailor.resolve_scantailor() == exe.resolve()


def test_resolve_scantailor_windows_error_lists_checked_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(scantailor.sys, "platform", "win32")
    monkeypatch.setattr(scantailor.shutil, "which", lambda _name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "nowhere"))
    for other in ("ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
        monkeypatch.delenv(other, raising=False)

    with pytest.raises(scantailor.ScanTailorError, match="scantailor-advanced.exe"):
        scantailor.resolve_scantailor()


# --- B3: cross-drive move fallback ----------------------------------------------


def test_move_replace_uses_rename_when_possible(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"data")
    dst = tmp_path / "dst.pdf"

    pipeline._move_replace(src, dst)

    assert dst.read_bytes() == b"data"
    assert not src.exists()


@pytest.mark.parametrize("simulated", [errno.EXDEV, "winerror-17"])
def test_move_replace_falls_back_across_devices(monkeypatch, tmp_path, simulated):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"payload")
    dst = tmp_path / "sub" / "dst.pdf"
    dst.parent.mkdir()
    dst.write_bytes(b"stale")  # destination already exists

    def fake_replace(_a, _b):
        exc = OSError(errno.EXDEV if simulated == errno.EXDEV else 18, "cross-device")
        if simulated == "winerror-17":
            exc.winerror = 17
        raise exc

    monkeypatch.setattr(pipeline.os, "replace", fake_replace)

    pipeline._move_replace(src, dst)

    assert dst.read_bytes() == b"payload"
    assert not src.exists()


def test_move_replace_reraises_unrelated_oserror(monkeypatch, tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"x")

    def fake_replace(_a, _b):
        raise OSError(errno.EACCES, "denied")

    monkeypatch.setattr(pipeline.os, "replace", fake_replace)

    with pytest.raises(OSError, match="denied"):
        pipeline._move_replace(src, tmp_path / "dst.pdf")


# --- R1: resilient workspace removal ---------------------------------------


def test_remove_workspace_deletes_a_normal_tree(tmp_path):
    ws = tmp_path / "ws"
    (ws / "input").mkdir(parents=True)
    (ws / "input" / "page.png").write_bytes(b"x")

    pipeline._remove_workspace(ws)

    assert not ws.exists()


def test_remove_workspace_warns_instead_of_raising(monkeypatch, tmp_path, caplog):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setattr(pipeline.shutil, "rmtree", lambda *a, **k: None)  # pretend it failed

    with caplog.at_level(logging.WARNING, logger=pipeline.logger.name):
        pipeline._remove_workspace(ws)

    assert "Could not fully remove workspace" in caplog.text


# --- R2 / R4: safe, bounded workspace directory names -----------------------


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ('vol:1?"name*', "vol-1-name"),
        ("MH_1976_vIV_bio_1-40", "MH_1976_vIV_bio_1-40"),
        ("x" * 100, "x" * 40),
        ("///", "volume"),
        ("   ", "volume"),
    ],
)
def test_safe_stem(stem, expected):
    assert workspace.safe_stem(stem) == expected


def test_create_workspace_sanitises_and_shortens_prefix(tmp_path):
    ws = workspace.create_workspace('bad:name?' + "z" * 80, tmp_path)

    assert ws.parent == tmp_path
    assert ws.name.startswith("bad-name")
    assert (ws / "input").is_dir() and (ws / "out").is_dir()
    # mkdtemp appends a random suffix; the stem portion must be capped at 40.
    stem_part = ws.name.rsplit("-", 1)[0]
    assert len(stem_part) <= 40


# --- B4: Unicode-safe image I/O ------------------------------------------------


def test_image_roundtrip_through_non_ascii_path(tmp_path):
    folder = tmp_path / "scans-Ünïcödé-café"
    folder.mkdir()
    path = folder / "page-01.png"
    image = np.full((12, 10), 255, dtype=np.uint8)
    image[3:6, 2:8] = 0

    assert imwrite_unicode(path, image) is True
    assert path.is_file()

    read_back = imread_unicode(path, cv2.IMREAD_UNCHANGED)
    assert read_back is not None
    assert read_back.shape == image.shape
    assert np.array_equal(read_back, image)


def test_imread_unicode_returns_none_for_missing_file(tmp_path):
    assert imread_unicode(tmp_path / "does-not-exist.png", cv2.IMREAD_UNCHANGED) is None
