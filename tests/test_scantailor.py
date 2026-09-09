import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from scan_cleanup.scantailor import (
    ScanTailorError,
    _reset_default_geometry,
    default_template_path,
    expected_tiff_names,
    generate_project,
    validate_output,
    validate_tiff_dpi,
)


def write_template(path: Path, page_count: int = 2) -> Path:
    root = ET.Element("project", version="4", outputDirectory="old/out")
    directories = ET.SubElement(root, "directories")
    ET.SubElement(directories, "directory", id="1", path="old/input")
    files = ET.SubElement(root, "files")
    images = ET.SubElement(root, "images")
    pages = ET.SubElement(root, "pages")
    filters = ET.SubElement(root, "filters")
    deskew = ET.SubElement(filters, "deskew")
    output = ET.SubElement(filters, "output")
    for index in range(page_count):
        file_id = str(index * 3 + 2)
        image_id = str(index * 3 + 3)
        page_id = str(index * 3 + 4)
        ET.SubElement(files, "file", id=file_id, dirId="1", name=f"old-{index}.png")
        image = ET.SubElement(
            images, "image", id=image_id, fileId=file_id, fileImage="0", subPages="1"
        )
        ET.SubElement(image, "size", width="100", height="200")
        ET.SubElement(image, "dpi", horizontal="300", vertical="300")
        ET.SubElement(pages, "page", id=page_id, imageId=image_id, subPage="single")
        settings = ET.SubElement(deskew, "page", id=page_id)
        ET.SubElement(settings, "rotation", value=str(index + 0.25))
        output_page = ET.SubElement(output, "page", id=page_id)
        params = ET.SubElement(output_page, "params")
        ET.SubElement(params, "dpi", horizontal="1200", vertical="1200")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def write_page(path: Path, width: int, height: int) -> None:
    assert cv2.imwrite(str(path), np.full((height, width), 255, dtype=np.uint8))


def test_bundled_template_contains_saved_40_page_600_dpi_project():
    root = ET.parse(default_template_path()).getroot()

    assert len(root.findall("./pages/page")) == 40
    output_dpis = {
        int(node.attrib["horizontal"])
        for node in root.findall("./filters/output/page/params/dpi")
    }
    assert output_dpis == {600}


def test_default_geometry_reset_disables_detection_and_clears_saved_layout():
    root = ET.parse(default_template_path()).getroot()

    _reset_default_geometry(root)

    project_page_ids = [page.attrib["id"] for page in root.findall("./pages/page")]
    content_pages = root.findall("./filters/select-content/page")
    assert [page.attrib["id"] for page in content_pages] == project_page_ids
    for params in root.findall("./filters/select-content/page/params"):
        assert params.attrib == {
            "contentDetectionMode": "disabled",
            "fineTuneCorners": "1",
            "pageDetectionMode": "auto",
        }
        assert list(params) == []

    layout_pages = root.findall("./filters/page-layout/page")
    assert [page.attrib["id"] for page in layout_pages] == project_page_ids
    for params in root.findall("./filters/page-layout/page/params"):
        assert params.find("pageRect").attrib == {
            "height": "0",
            "width": "0",
            "x": "0",
            "y": "0",
        }
        assert params.find("contentRect").attrib == {
            "height": "0",
            "width": "0",
            "x": "0",
            "y": "0",
        }
        assert params.find("alignment").attrib["null"] == "1"
    assert root.findall("./filters/output/page/output-params") == []
    assert len(root.findall("./filters/output/page/params")) == 40


def test_generate_project_retargets_files_and_preserves_geometry(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()
    page_paths = [input_dir / "volume-01.png", input_dir / "volume-02.png"]
    write_page(page_paths[0], 80, 120)
    write_page(page_paths[1], 90, 130)
    template = write_template(tmp_path / "template.ScanTailor")
    project = tmp_path / "project.ScanTailor"

    output_dpi = generate_project(page_paths, output_dir, project, 400, template)

    root = ET.parse(project).getroot()
    assert output_dpi == 1200
    assert root.attrib["outputDirectory"] == str(output_dir.resolve())
    assert root.find("./directories/directory").attrib["path"] == str(input_dir.resolve())
    assert [node.attrib["name"] for node in root.findall("./files/file")] == [
        "volume-01.png",
        "volume-02.png",
    ]
    assert root.find("./images/image/size").attrib == {"width": "80", "height": "120"}
    assert root.find("./images/image/dpi").attrib == {"horizontal": "400", "vertical": "400"}
    assert root.find("./filters/deskew/page/rotation").attrib["value"] == "0.25"


def test_generate_project_truncates_template_for_fewer_pages(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    page_paths = [input_dir / "volume-01.png"]
    write_page(page_paths[0], 80, 120)
    template = write_template(tmp_path / "template.ScanTailor", page_count=2)
    project = tmp_path / "project.ScanTailor"

    generate_project(page_paths, tmp_path / "out", project, 300, template)

    root = ET.parse(project).getroot()
    assert [f.attrib["name"] for f in root.findall("./files/file")] == ["volume-01.png"]
    assert len(root.findall("./images/image")) == 1
    assert len(root.findall("./pages/page")) == 1
    assert len(root.findall("./filters/deskew/page")) == 1
    assert root.find("./filters/deskew/page").attrib["id"] == root.find("./pages/page").attrib["id"]
    assert len(root.findall("./filters/output/page")) == 1


def test_generate_project_extends_template_for_more_pages_by_cloning_last_page(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    page_paths = [input_dir / f"volume-{i:02d}.png" for i in range(1, 4)]
    for index, page_path in enumerate(page_paths):
        write_page(page_path, 80 + index, 120 + index)
    template = write_template(tmp_path / "template.ScanTailor", page_count=2)
    project = tmp_path / "project.ScanTailor"

    generate_project(page_paths, tmp_path / "out", project, 300, template)

    root = ET.parse(project).getroot()
    assert [f.attrib["name"] for f in root.findall("./files/file")] == [
        "volume-01.png",
        "volume-02.png",
        "volume-03.png",
    ]
    page_ids = [p.attrib["id"] for p in root.findall("./pages/page")]
    assert len(page_ids) == 3
    assert len(set(page_ids)) == 3

    # Page 3 was cloned from page 2 (the template's last page): its deskew and
    # output-recipe settings match page 2's, but its filename/size/dpi are its own.
    deskew_rotations = [p.find("rotation").attrib["value"] for p in root.findall("./filters/deskew/page")]
    assert len(deskew_rotations) == 3
    assert deskew_rotations[1] == deskew_rotations[2]
    assert len(root.findall("./filters/output/page")) == 3
    output_dpis = {
        node.attrib["horizontal"] for node in root.findall("./filters/output/page/params/dpi")
    }
    assert output_dpis == {"1200"}
    assert root.find("./images/image[3]/size").attrib == {"width": "82", "height": "122"}


def test_validate_output_returns_manifest_order_not_directory_order(tmp_path):
    for name, value in (("volume-02.tif", 20), ("volume-01.tif", 10), ("volume-03.tif", 30)):
        assert cv2.imwrite(str(tmp_path / name), np.full((5, 5), value, dtype=np.uint8))

    result = validate_output(
        tmp_path, ["volume-01.tif", "volume-02.tif", "volume-03.tif"]
    )

    assert [path.name for path in result] == [
        "volume-01.tif",
        "volume-02.tif",
        "volume-03.tif",
    ]


def test_validate_output_reports_missing_and_unexpected_pages(tmp_path):
    write_page(tmp_path / "volume-01.tif", 5, 5)
    write_page(tmp_path / "extra.tif", 5, 5)

    with pytest.raises(ScanTailorError) as error:
        validate_output(tmp_path, ["volume-01.tif", "volume-02.tif"])

    assert "missing: volume-02.tif" in str(error.value)
    assert "unexpected: extra.tif" in str(error.value)


def test_expected_tiff_names_follow_extracted_page_names():
    pages = [Path("volume-01.png"), Path("volume-10.png"), Path("volume-100.png")]
    assert expected_tiff_names(pages) == [
        "volume-01.tif",
        "volume-10.tif",
        "volume-100.tif",
    ]


def test_validate_tiff_dpi_reads_actual_metadata(tmp_path):
    paths = []
    for index in range(2):
        path = tmp_path / f"page-{index}.tif"
        Image.fromarray(np.full((5, 5), 255, dtype=np.uint8)).save(path, dpi=(600, 600))
        paths.append(path)

    assert validate_tiff_dpi(paths) == 600


def test_validate_tiff_dpi_rejects_mixed_resolutions(tmp_path):
    paths = []
    for index, dpi in enumerate((300, 600)):
        path = tmp_path / f"page-{index}.tif"
        Image.fromarray(np.full((5, 5), 255, dtype=np.uint8)).save(path, dpi=(dpi, dpi))
        paths.append(path)

    with pytest.raises(ScanTailorError, match="inconsistent DPI"):
        validate_tiff_dpi(paths)
