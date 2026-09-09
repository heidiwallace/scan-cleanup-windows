import shutil
import sys
from pathlib import Path

import cv2
import img2pdf
import numpy as np
import pymupdf
import pytest
from PIL import Image

from scan_cleanup import pipeline
from scan_cleanup.config import Recipe
from scan_cleanup.scantailor import ScanTailorError
from scan_cleanup.workspace import WorkspaceManifest, create_workspace
from tests.test_scantailor import write_template


def build_pdf(tmp_path: Path, page_count: int = 2) -> Path:
    paths = []
    for index in range(1, page_count + 1):
        path = tmp_path / f"source-{index}.png"
        image = np.full((100, 80), 255, dtype=np.uint8)
        image[10 * index : 10 * index + 5, 10:70] = 0
        assert cv2.imwrite(str(path), image)
        paths.append(str(path))
    pdf = tmp_path / "volume.pdf"
    pdf.write_bytes(img2pdf.convert(paths))
    return pdf


def fake_ocr(source: Path, destination: Path, recipe: Recipe) -> None:
    shutil.copyfile(source, destination)


def test_process_volume_runs_interactive_pipeline_in_order(tmp_path, monkeypatch):
    input_pdf = build_pdf(tmp_path)
    output_dir = tmp_path / "final"
    workspace_root = tmp_path / "workspaces"
    template = write_template(tmp_path / "template.ScanTailor")

    def fake_launch(executable: Path, project: Path) -> None:
        workspace = project.parent
        for png in sorted((workspace / "input").glob("*.png"), reverse=True):
            image = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            Image.fromarray(image).save(workspace / "out" / f"{png.stem}.tif", dpi=(1200, 1200))

    monkeypatch.setattr(pipeline, "launch_scantailor", fake_launch)
    monkeypatch.setattr(pipeline, "add_ocr_layer", fake_ocr)

    result = pipeline.process_volume(
        input_pdf,
        output_dir,
        recipe=Recipe(),
        scantailor_executable=Path(sys.executable),
        workspace_root=workspace_root,
        template_path=template,
    )

    assert result == output_dir / "volume_processed.pdf"
    assert len(pymupdf.open(result)) == 2
    assert list(workspace_root.iterdir()) == []


def test_process_volume_can_retain_successful_workspace(tmp_path, monkeypatch):
    input_pdf = build_pdf(tmp_path)
    workspace_root = tmp_path / "workspaces"
    template = write_template(tmp_path / "template.ScanTailor")

    def fake_launch(executable: Path, project: Path) -> None:
        workspace = project.parent
        for png in sorted((workspace / "input").glob("*.png")):
            image = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            Image.fromarray(image).save(
                workspace / "out" / f"{png.stem}.tif", dpi=(1200, 1200)
            )

    monkeypatch.setattr(pipeline, "launch_scantailor", fake_launch)
    monkeypatch.setattr(pipeline, "add_ocr_layer", fake_ocr)

    pipeline.process_volume(
        input_pdf,
        tmp_path / "final",
        recipe=Recipe(cleanup_workspace_on_success=False),
        scantailor_executable=Path(sys.executable),
        workspace_root=workspace_root,
        template_path=template,
    )

    workspace = next(workspace_root.iterdir())
    manifest = WorkspaceManifest.load(workspace)
    assert manifest.expected_tiffs == ["volume-01.tif", "volume-02.tif"]


def test_process_volume_preserves_workspace_and_prints_resume_on_bad_output(
    tmp_path, monkeypatch
):
    input_pdf = build_pdf(tmp_path)
    workspace_root = tmp_path / "workspaces"
    template = write_template(tmp_path / "template.ScanTailor")
    monkeypatch.setattr(pipeline, "launch_scantailor", lambda executable, project: None)

    with pytest.raises(ScanTailorError) as error:
        pipeline.process_volume(
            input_pdf,
            tmp_path / "final",
            scantailor_executable=Path(sys.executable),
            workspace_root=workspace_root,
            template_path=template,
        )

    workspace = next(workspace_root.iterdir())
    assert workspace.is_dir()
    assert f"scan-cleanup resume {workspace}" in str(error.value)
    assert "missing: volume-01.tif, volume-02.tif" in str(error.value)


def test_resume_reopens_project_and_finishes(tmp_path, monkeypatch):
    workspace = create_workspace("volume", tmp_path / "workspaces")
    (workspace / "project.ScanTailor").write_text("project", encoding="utf-8")
    manifest = WorkspaceManifest(
        input_pdf=str(tmp_path / "volume.pdf"),
        output_directory=str(tmp_path / "old-output"),
        output_pdf=str(tmp_path / "old-output/volume_processed.pdf"),
        source_dpi=300,
        output_dpi=300,
        page_files=["volume-01.png", "volume-02.png"],
        expected_tiffs=["volume-01.tif", "volume-02.tif"],
        scantailor_executable=sys.executable,
    )
    manifest.save(workspace)

    launched = []

    def fake_launch(executable: Path, project: Path) -> None:
        launched.append(project)
        for name in manifest.expected_tiffs:
            image = np.full((20, 20), 255, dtype=np.uint8)
            Image.fromarray(image).save(workspace / "out" / name, dpi=(300, 300))

    monkeypatch.setattr(pipeline, "launch_scantailor", fake_launch)
    monkeypatch.setattr(pipeline, "add_ocr_layer", fake_ocr)

    result = pipeline.resume_workspace(workspace, tmp_path / "new-output")

    assert launched == [workspace / "project.ScanTailor"]
    assert result == tmp_path / "new-output/volume_processed.pdf"
    assert result.is_file()
    assert not workspace.exists()


def test_process_batch_skips_inputs_with_existing_output(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "final"
    output_dir.mkdir()
    template = write_template(tmp_path / "template.ScanTailor")

    (tmp_path / "done-source").mkdir()
    build_pdf(tmp_path / "done-source", page_count=1).rename(input_dir / "already-done.pdf")
    (tmp_path / "pending-source").mkdir()
    build_pdf(tmp_path / "pending-source", page_count=1).rename(input_dir / "not-done.pdf")

    existing_output = output_dir / "already-done_processed.pdf"
    existing_output.write_bytes(b"pre-existing output, should not be touched")

    def fake_launch(executable: Path, project: Path) -> None:
        workspace = project.parent
        for png in sorted((workspace / "input").glob("*.png")):
            image = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            Image.fromarray(image).save(workspace / "out" / f"{png.stem}.tif", dpi=(1200, 1200))

    monkeypatch.setattr(pipeline, "launch_scantailor", fake_launch)
    monkeypatch.setattr(pipeline, "add_ocr_layer", fake_ocr)

    results = pipeline.process_batch(
        input_dir,
        output_dir,
        recipe=Recipe(),
        scantailor_executable=Path(sys.executable),
        workspace_root=tmp_path / "workspaces",
        template_path=template,
    )

    assert results == [output_dir / "not-done_processed.pdf"]
    assert results[0].is_file()
    assert existing_output.read_bytes() == b"pre-existing output, should not be touched"


def test_process_batch_overwrite_reprocesses_everything(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "final"
    output_dir.mkdir()
    template = write_template(tmp_path / "template.ScanTailor")

    build_pdf(input_dir, page_count=1)
    existing_output = output_dir / "volume_processed.pdf"
    existing_output.write_bytes(b"stale output")

    def fake_launch(executable: Path, project: Path) -> None:
        workspace = project.parent
        for png in sorted((workspace / "input").glob("*.png")):
            image = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            Image.fromarray(image).save(workspace / "out" / f"{png.stem}.tif", dpi=(1200, 1200))

    monkeypatch.setattr(pipeline, "launch_scantailor", fake_launch)
    monkeypatch.setattr(pipeline, "add_ocr_layer", fake_ocr)

    results = pipeline.process_batch(
        input_dir,
        output_dir,
        recipe=Recipe(),
        scantailor_executable=Path(sys.executable),
        workspace_root=tmp_path / "workspaces",
        template_path=template,
        overwrite=True,
    )

    assert results == [existing_output]
    assert existing_output.read_bytes() != b"stale output"
