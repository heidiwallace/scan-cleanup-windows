"""Command-line interface for the interactive ScanTailor workflow."""

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from scan_cleanup.config import Recipe
from scan_cleanup.ocr import MissingSystemDependencyError
from scan_cleanup.pipeline import process_volume, resume_workspace
from scan_cleanup.scantailor import ScanTailorError


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scantailor",
        type=Path,
        help="Path to the ScanTailor Advanced executable",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Directory in which to retain development workspaces",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Override the bundled ScanTailor project template",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="Source scan DPI used for project metadata"
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Retain a successful workspace for development or inspection",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess files even if a matching output already exists",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan-cleanup",
        description="Process scanned PDFs interactively with ScanTailor Advanced, then OCR them.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose progress logging"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="Process one scanned PDF")
    process_parser.add_argument("input_pdf", type=Path)
    process_parser.add_argument("output_dir", type=Path)
    _add_runtime_args(process_parser)

    batch_parser = subparsers.add_parser("batch", help="Process every PDF in a directory")
    batch_parser.add_argument("input_dir", type=Path)
    batch_parser.add_argument("output_dir", type=Path)
    _add_runtime_args(batch_parser)

    resume_parser = subparsers.add_parser("resume", help="Resume a preserved workspace")
    resume_parser.add_argument("workspace", type=Path)
    resume_parser.add_argument("output_dir", type=Path)
    resume_parser.add_argument("--scantailor", type=Path)
    resume_parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Retain the workspace after successful completion",
    )

    return parser


def _confirm_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    answer = input(f"Output already exists: {path}\nReplace it? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _output_path(input_pdf: Path, output_dir: Path) -> Path:
    return output_dir / f"{input_pdf.stem}_processed.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    try:
        if args.command == "resume":
            from scan_cleanup.workspace import WorkspaceManifest

            manifest = WorkspaceManifest.load(args.workspace)
            destination = _output_path(Path(manifest.input_pdf), args.output_dir)
            if not _confirm_overwrite(destination):
                print("Cancelled; existing output was not changed.")
                return 0
            result = resume_workspace(
                args.workspace,
                args.output_dir,
                recipe=replace(
                    Recipe(), cleanup_workspace_on_success=not args.keep_workspace
                ),
                scantailor_executable=args.scantailor,
                overwrite=destination.exists(),
            )
            print(result)
            return 0

        recipe = replace(
            Recipe(),
            source_dpi=args.dpi,
            cleanup_workspace_on_success=not args.keep_workspace,
        )
        if args.command == "process":
            destination = _output_path(args.input_pdf, args.output_dir)
            if not args.overwrite and not _confirm_overwrite(destination):
                print("Cancelled; existing output was not changed.")
                return 0
            result = process_volume(
                args.input_pdf,
                args.output_dir,
                recipe=recipe,
                scantailor_executable=args.scantailor,
                workspace_root=args.workspace_root,
                template_path=args.template,
                overwrite=destination.exists(),
            )
            print(result)
        else:
            if not args.input_dir.is_dir():
                raise ValueError(f"Input directory does not exist: {args.input_dir}")
            pdf_paths = sorted(args.input_dir.glob("*.pdf"))
            if not pdf_paths:
                raise ValueError(f"No PDF files found in {args.input_dir}")
            pending_paths = []
            for pdf_path in pdf_paths:
                destination = _output_path(pdf_path, args.output_dir)
                if destination.exists() and not args.overwrite:
                    print(f"Skipped (output already exists): {pdf_path.name}")
                    continue
                pending_paths.append(pdf_path)
            for pdf_path in pending_paths:
                process_volume(
                    pdf_path,
                    args.output_dir,
                    recipe=recipe,
                    scantailor_executable=args.scantailor,
                    workspace_root=args.workspace_root,
                    template_path=args.template,
                    overwrite=args.overwrite,
                )
    except (MissingSystemDependencyError, ScanTailorError, FileNotFoundError, ValueError) as exc:
        print(f"\nError: {exc}\n", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
