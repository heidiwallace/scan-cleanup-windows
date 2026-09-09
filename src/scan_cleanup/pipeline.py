"""Interactive orchestration: extract -> ScanTailor -> assemble -> OCR."""

import logging
import shutil
from pathlib import Path

from scan_cleanup.config import Recipe
from scan_cleanup.ocr import add_ocr_layer
from scan_cleanup.pdf_io import extract_pages_to_png, images_to_pdf
from scan_cleanup.scantailor import (
    ScanTailorError,
    expected_tiff_names,
    generate_project,
    launch_scantailor,
    resolve_scantailor,
    validate_output,
    validate_tiff_dpi,
)
from scan_cleanup.workspace import WorkspaceManifest, create_workspace

logger = logging.getLogger(__name__)


def output_path_for(input_pdf: Path, output_dir: Path) -> Path:
    """Return the expected output path for a given input PDF."""
    return output_dir / f"{input_pdf.stem}_processed.pdf"


def process_volume(
    input_pdf: Path,
    output_dir: Path,
    recipe: Recipe | None = None,
    scantailor_executable: Path | None = None,
    workspace_root: Path | None = None,
    template_path: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Create a workspace, run ScanTailor interactively, then assemble and OCR."""
    recipe = recipe or Recipe()
    executable = resolve_scantailor(scantailor_executable)
    output_dir = output_dir.resolve()
    output_pdf = output_path_for(input_pdf, output_dir)
    if output_pdf.exists() and not overwrite:
        raise FileExistsError(f"Output PDF already exists: {output_pdf}")

    workspace = create_workspace(input_pdf.stem, workspace_root)
    logger.info("Workspace: %s", workspace)
    try:
        page_paths = extract_pages_to_png(input_pdf.resolve(), workspace / "input", recipe.source_dpi)
        logger.info("%s: %d pages extracted", input_pdf.name, len(page_paths))
        project_path = workspace / "project.ScanTailor"
        output_dpi = generate_project(
            page_paths,
            workspace / "out",
            project_path,
            recipe.source_dpi,
            template_path,
        )
        manifest = WorkspaceManifest(
            input_pdf=str(input_pdf.resolve()),
            output_directory=str(output_dir),
            output_pdf=str(output_pdf),
            source_dpi=recipe.source_dpi,
            output_dpi=output_dpi,
            page_files=[path.name for path in page_paths],
            expected_tiffs=expected_tiff_names(page_paths),
            scantailor_executable=str(executable),
        )
        manifest.save(workspace)
        launch_scantailor(executable, project_path)
        result = finish_workspace(workspace, output_dir, recipe, overwrite=overwrite)
    except Exception as exc:
        message = f"{exc}\nWorkspace preserved: {workspace}"
        if (workspace / "workspace.json").is_file():
            message += f"\nResume with: scan-cleanup resume {workspace} {output_dir}"
        raise ScanTailorError(message) from exc

    if recipe.cleanup_workspace_on_success:
        shutil.rmtree(workspace)
    else:
        logger.info("Development workspace retained: %s", workspace)
    return result


def finish_workspace(
    workspace: Path,
    output_dir: Path,
    recipe: Recipe | None = None,
    overwrite: bool = False,
) -> Path:
    """Validate an existing workspace, assemble TIFFs in manifest order, and OCR."""
    recipe = recipe or Recipe()
    workspace = workspace.resolve()
    manifest = WorkspaceManifest.load(workspace)
    tiff_paths = validate_output(workspace / "out", manifest.expected_tiffs)
    actual_output_dpi = validate_tiff_dpi(tiff_paths)
    output_dir = output_dir.resolve()
    output_pdf = output_path_for(Path(manifest.input_pdf), output_dir)
    if output_pdf.exists() and not overwrite:
        raise FileExistsError(f"Output PDF already exists: {output_pdf}")

    output_dir.mkdir(parents=True, exist_ok=True)
    assembled_pdf = workspace / "assembled.pdf"
    if actual_output_dpi != manifest.output_dpi:
        logger.info(
            "ScanTailor output DPI differs from the initial project template: %d -> %d; "
            "using TIFF metadata",
            manifest.output_dpi,
            actual_output_dpi,
        )
    images_to_pdf(tiff_paths, assembled_pdf, dpi=actual_output_dpi)
    ocr_pdf = workspace / "ocr-output.pdf"
    if ocr_pdf.exists():
        ocr_pdf.unlink()
    add_ocr_layer(assembled_pdf, ocr_pdf, recipe)
    if output_pdf.exists() and not overwrite:
        raise FileExistsError(f"Output PDF appeared during processing: {output_pdf}")
    ocr_pdf.replace(output_pdf)
    logger.info("Done: %s", output_pdf)
    return output_pdf


def resume_workspace(
    workspace: Path,
    output_dir: Path,
    recipe: Recipe | None = None,
    scantailor_executable: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Reopen a preserved ScanTailor project and retry completion."""
    manifest = WorkspaceManifest.load(workspace)
    executable = resolve_scantailor(
        scantailor_executable or Path(manifest.scantailor_executable)
    )
    launch_scantailor(executable, workspace / manifest.project_file)
    result = finish_workspace(workspace, output_dir, recipe, overwrite=overwrite)
    if (recipe or Recipe()).cleanup_workspace_on_success:
        shutil.rmtree(workspace)
    return result


def process_batch(
    input_dir: Path,
    output_dir: Path,
    recipe: Recipe | None = None,
    scantailor_executable: Path | None = None,
    workspace_root: Path | None = None,
    template_path: Path | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Process every PDF in `input_dir`, writing corresponding outputs into `output_dir`.

    PDFs whose output already exists in `output_dir` are skipped automatically
    (unless `overwrite` is set), so a batch interrupted partway through can be
    re-run to pick up where it left off without redoing finished files.
    """
    recipe = recipe or Recipe()
    pdf_paths = sorted(input_dir.glob("*.pdf"))
    if not pdf_paths:
        raise ValueError(f"No PDF files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        pending_paths = pdf_paths
    else:
        pending_paths = [
            pdf_path
            for pdf_path in pdf_paths
            if not output_path_for(pdf_path, output_dir).exists()
        ]
        skipped = len(pdf_paths) - len(pending_paths)
        if skipped:
            logger.info(
                "Skipping %d file(s) with existing output in %s", skipped, output_dir
            )

    results = []
    for pdf_path in pending_paths:
        results.append(
            process_volume(
                pdf_path,
                output_dir,
                recipe=recipe,
                scantailor_executable=scantailor_executable,
                workspace_root=workspace_root,
                template_path=template_path,
                overwrite=overwrite,
            )
        )
    return results
