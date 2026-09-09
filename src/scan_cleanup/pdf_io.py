"""Extract PDF pages to PNG and assemble ordered ScanTailor TIFFs."""

from pathlib import Path

import cv2
import img2pdf
import numpy as np
import pymupdf


def extract_page_images(pdf_path: Path) -> list[np.ndarray]:
    """Extract each page's embedded scan image, in page order.

    Assumes one embedded raster image per PDF page (a single-page-per-page scan,
    not multi-page spreads or vector content). Reads the image bytes directly
    from the PDF rather than re-rasterizing the page, to preserve the original
    scan resolution and avoid introducing compression artifacts.
    """
    doc = pymupdf.open(pdf_path)
    images: list[np.ndarray] = []
    try:
        for page_index, page in enumerate(doc):
            image_refs = page.get_images(full=True)
            if len(image_refs) != 1:
                raise ValueError(
                    f"{pdf_path}: page {page_index + 1} has {len(image_refs)} "
                    "embedded images, expected exactly 1. This tool assumes each "
                    "PDF page is a single scanned page image."
                )
            xref = image_refs[0][0]
            image_bytes = doc.extract_image(xref)["image"]
            array = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if array is None:
                raise ValueError(
                    f"{pdf_path}: could not decode embedded image on page {page_index + 1}"
                )
            images.append(array)
    finally:
        doc.close()
    return images


def extract_pages_to_png(pdf_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    """Extract embedded scans losslessly, with full-page rendering as a fallback."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    paths: list[Path] = []
    try:
        if len(doc) == 0:
            raise ValueError(f"Input PDF has no pages: {pdf_path}")
        digits = max(2, len(str(len(doc))))
        for index, page in enumerate(doc, start=1):
            output_path = output_dir / f"{pdf_path.stem}-{index:0{digits}d}.png"
            image_refs = page.get_images(full=True)
            wrote = False
            if len(image_refs) == 1:
                image_bytes = doc.extract_image(image_refs[0][0])["image"]
                image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
                if image is not None:
                    wrote = cv2.imwrite(str(output_path), image)
            if not wrote:
                pixmap = page.get_pixmap(dpi=dpi, alpha=False)
                pixmap.save(output_path)
            paths.append(output_path)
    finally:
        doc.close()
    return paths


def images_to_pdf(image_paths: list[Path], output_pdf_path: Path, dpi: int) -> None:
    """Combine processed page images into a single PDF, in the given order.

    The DPI is forced explicitly (rather than trusting each image's embedded
    metadata) so the physical page size in the output PDF is correct.
    """
    layout_fun = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))
    pdf_bytes = img2pdf.convert([str(p) for p in image_paths], layout_fun=layout_fun)
    output_pdf_path.write_bytes(pdf_bytes)
