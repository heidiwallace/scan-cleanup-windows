"""Configuration for the interactive ScanTailor cleanup workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Recipe:
    """Runtime settings not stored in the ScanTailor project template."""

    source_dpi: int = 300
    cleanup_workspace_on_success: bool = True

    ocr_language: str = "eng"
    ocr_output_type: str = "pdf"
