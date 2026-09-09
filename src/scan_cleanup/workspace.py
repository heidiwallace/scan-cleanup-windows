"""Persistent run workspaces for the interactive ScanTailor workflow."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST_NAME = "workspace.json"

# Characters outside this set are stripped from a directory-name stem. Covers
# everything Windows forbids in a path component (< > : " / \ | ? *) plus
# spaces and other punctuation, so the temp folder name is always portable.
_UNSAFE_STEM_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

# Cap the stem so the full workspace path stays clear of Windows' 260-character
# limit even under a deep temp root.
_MAX_STEM_LENGTH = 40


@dataclass(frozen=True)
class WorkspaceManifest:
    input_pdf: str
    output_directory: str
    output_pdf: str
    source_dpi: int
    output_dpi: int
    page_files: list[str]
    expected_tiffs: list[str]
    scantailor_executable: str
    project_file: str = "project.ScanTailor"

    @classmethod
    def load(cls, workspace: Path) -> WorkspaceManifest:
        manifest_path = workspace / MANIFEST_NAME
        if not manifest_path.is_file():
            raise ValueError(f"Workspace manifest not found: {manifest_path}")
        return cls(**json.loads(manifest_path.read_text(encoding="utf-8")))

    def save(self, workspace: Path) -> None:
        (workspace / MANIFEST_NAME).write_text(
            json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8"
        )


def safe_stem(input_stem: str) -> str:
    """A filesystem-safe, length-bounded version of ``input_stem``.

    Strips characters that are invalid in a Windows path component and truncates
    to keep the eventual workspace path well under the 260-character limit.
    Falls back to ``"volume"`` if nothing usable remains.
    """
    cleaned = _UNSAFE_STEM_CHARS.sub("-", input_stem).strip("-")
    return cleaned[:_MAX_STEM_LENGTH] or "volume"


def create_workspace(input_stem: str, workspace_root: Path | None = None) -> Path:
    stem = safe_stem(input_stem)
    if workspace_root is not None:
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"{stem}-", dir=workspace_root))
    else:
        # Short fixed prefix ("sc-", not "scan-cleanup-") to conserve path
        # length; the Windows default temp directory is already deep.
        workspace = Path(tempfile.mkdtemp(prefix=f"sc-{stem}-"))
    (workspace / "input").mkdir()
    (workspace / "out").mkdir()
    return workspace
