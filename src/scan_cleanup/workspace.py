"""Persistent run workspaces for the interactive ScanTailor workflow."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST_NAME = "workspace.json"


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


def create_workspace(input_stem: str, workspace_root: Path | None = None) -> Path:
    if workspace_root is not None:
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"{input_stem}-", dir=workspace_root))
    else:
        workspace = Path(tempfile.mkdtemp(prefix=f"scan-cleanup-{input_stem}-"))
    (workspace / "input").mkdir()
    (workspace / "out").mkdir()
    return workspace
