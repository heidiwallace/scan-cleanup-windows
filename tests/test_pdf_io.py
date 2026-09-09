from pathlib import Path

import cv2
import img2pdf
import numpy as np
import pymupdf
import pytest

from scan_cleanup.pdf_io import extract_page_images, extract_pages_to_png, images_to_pdf


def _write_png(image: np.ndarray, path: Path) -> None:
    cv2.imwrite(str(path), image)


def test_extract_page_images_round_trip(tmp_path, text_page):
    png_path = tmp_path / "page.png"
    _write_png(text_page, png_path)
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(img2pdf.convert([str(png_path)]))

    images = extract_page_images(pdf_path)

    assert len(images) == 1
    assert images[0].shape[:2] == text_page.shape[:2]


def test_extract_page_images_rejects_page_without_exactly_one_image(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    blank_pdf = tmp_path / "blank.pdf"
    doc.save(blank_pdf)
    doc.close()

    with pytest.raises(ValueError, match="expected exactly 1"):
        extract_page_images(blank_pdf)


def test_extract_pages_to_png_renders_page_without_embedded_image(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=72, height=72)
    page.insert_text((10, 30), "Rendered page")
    pdf_path = tmp_path / "render.pdf"
    doc.save(pdf_path)
    doc.close()

    paths = extract_pages_to_png(pdf_path, tmp_path / "pages", dpi=100)

    assert [path.name for path in paths] == ["render-01.png"]
    image = cv2.imread(str(paths[0]))
    assert image is not None
    assert image.shape[:2] == pytest.approx((100, 100), abs=1)


def test_images_to_pdf_sets_requested_dpi(tmp_path, text_page):
    png_path = tmp_path / "page-0001.png"
    _write_png(text_page, png_path)
    output_pdf = tmp_path / "output.pdf"

    images_to_pdf([png_path], output_pdf, dpi=300)

    doc = pymupdf.open(output_pdf)
    expected_width_pt = text_page.shape[1] / 300 * 72
    assert doc[0].rect.width == pytest.approx(expected_width_pt, rel=0.01)


def test_images_to_pdf_preserves_page_order(tmp_path, text_page):
    paths = []
    for i in range(3):
        p = tmp_path / f"page-{i:04d}.png"
        _write_png(text_page, p)
        paths.append(p)
    output_pdf = tmp_path / "output.pdf"

    images_to_pdf(paths, output_pdf, dpi=300)

    doc = pymupdf.open(output_pdf)
    assert len(doc) == 3
