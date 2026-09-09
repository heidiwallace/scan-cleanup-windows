"""ScanTailor project generation, launching, and output validation."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path

import cv2
from PIL import Image


class ScanTailorError(RuntimeError):
    """Raised when ScanTailor cannot be launched or produces invalid output."""


def default_template_path() -> Path:
    resource = files("scan_cleanup").joinpath("templates/scantailor-advanced-default.scantailor")
    return Path(str(resource))


def resolve_scantailor(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    if env_path := os.environ.get("SCANTAILOR_ADVANCED"):
        candidates.append(Path(env_path).expanduser())

    for command in ("scantailor-advanced", "scantailor-advanced.exe"):
        if found := shutil.which(command):
            candidates.append(Path(found))

    if sys.platform == "darwin":
        candidates.extend(
            [
                # The documented, supported install location (see README): a plain
                # `cmake --install --prefix <homebrew-prefix>` of ScanTailor Advanced,
                # checked directly so discovery does not depend on PATH being set in
                # every execution context (e.g. non-interactive shells, LaunchAgents).
                Path("/opt/homebrew/bin/scantailor-advanced"),  # Apple Silicon Homebrew
                Path("/usr/local/bin/scantailor-advanced"),  # Intel Homebrew
                Path(
                    "/Applications/ScanTailor Advanced.app/Contents/MacOS/"
                    "scantailor-advanced"
                ),
                Path.home()
                / "Applications/ScanTailor Advanced.app/Contents/MacOS/scantailor-advanced",
            ]
        )

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    checked = ", ".join(str(path) for path in candidates) or "the system PATH"
    raise ScanTailorError(
        "ScanTailor Advanced executable was not found. Pass --scantailor PATH or set "
        f"SCANTAILOR_ADVANCED. Checked: {checked}"
    )


def _template_output_dpi(root: ET.Element) -> int:
    output_filter = root.find("./filters/output")
    if output_filter is None:
        raise ScanTailorError("Template has no output filter settings")
    dpi = output_filter.find(".//dpi")
    if dpi is None or "horizontal" not in dpi.attrib:
        raise ScanTailorError("Template has no output DPI setting")
    return int(dpi.attrib["horizontal"])


def _collect_max_id(root: ET.Element) -> int:
    ids = [
        int(value)
        for element in root.iter()
        for key, value in element.attrib.items()
        if key in ("id", "imageId", "fileId") and value.isdigit()
    ]
    return max(ids, default=0)


def _resize_page_list(container: ET.Element, tag: str, keep_ids: set[str]) -> None:
    container[:] = [
        child for child in container if child.tag != tag or child.attrib.get("id") in keep_ids
    ]


def _clone_page_entry(container: ET.Element, tag: str, source_id: str, new_id: str) -> None:
    source = next(
        (child for child in container if child.tag == tag and child.attrib.get("id") == source_id),
        None,
    )
    if source is None:
        return
    clone = copy.deepcopy(source)
    clone.set("id", new_id)
    container.append(clone)


def _resize_pages(root: ET.Element, target_count: int) -> None:
    """Truncate or extend the template's page set to match the input PDF's page count.

    Truncating keeps the first `target_count` template pages, in scan order.
    Extending clones the last template page's files and per-page filter settings
    (including the output recipe) for each additional page, under fresh ids.
    Auto-detected geometry (page split, deskew, fix orientation) on cloned pages
    is stale until the user reviews that page in ScanTailor Advanced, same as any
    other auto-mode page; the output recipe (DPI, binarization, etc.) is meant to
    be identical across pages regardless.
    """
    pages_node = root.find("pages")
    images_node = root.find("images")
    files_node = root.find("files")
    disambiguation_node = root.find("file-name-disambiguation")
    filters_node = root.find("filters")

    page_units = list(pages_node)
    current_count = len(page_units)
    if target_count == current_count:
        return

    if target_count < current_count:
        keep_page_ids = {page.attrib["id"] for page in page_units[:target_count]}
        keep_image_ids = {page.attrib["imageId"] for page in page_units[:target_count]}
        pages_node[:] = page_units[:target_count]
        images_node[:] = [image for image in images_node if image.attrib["id"] in keep_image_ids]
        keep_file_ids = {image.attrib["fileId"] for image in images_node}
        files_node[:] = [file for file in files_node if file.attrib["id"] in keep_file_ids]
        if disambiguation_node is not None:
            disambiguation_node[:] = [
                mapping
                for mapping in disambiguation_node
                if mapping.attrib.get("file") in keep_file_ids
            ]
        for filter_node in filters_node:
            if filter_node.tag == "page-split":
                _resize_page_list(filter_node, "image", keep_image_ids)
                continue
            _resize_page_list(filter_node, "page", keep_page_ids)
            wrapper = filter_node.find("image-settings")
            if wrapper is not None:
                _resize_page_list(wrapper, "page", keep_page_ids)
        return

    last_page = page_units[-1]
    last_page_id = last_page.attrib["id"]
    last_image_id = last_page.attrib["imageId"]
    last_image = next(image for image in images_node if image.attrib["id"] == last_image_id)
    last_file_id = last_image.attrib["fileId"]
    last_file = next(file for file in files_node if file.attrib["id"] == last_file_id)
    last_mapping = None
    if disambiguation_node is not None:
        last_mapping = next(
            (m for m in disambiguation_node if m.attrib.get("file") == last_file_id), None
        )

    next_id = _collect_max_id(root) + 1
    for _ in range(target_count - current_count):
        new_file_id, new_image_id, new_page_id = (
            str(next_id),
            str(next_id + 1),
            str(next_id + 2),
        )
        next_id += 3

        new_file = copy.deepcopy(last_file)
        new_file.set("id", new_file_id)
        files_node.append(new_file)

        new_image = copy.deepcopy(last_image)
        new_image.set("id", new_image_id)
        new_image.set("fileId", new_file_id)
        images_node.append(new_image)

        new_page = copy.deepcopy(last_page)
        new_page.set("id", new_page_id)
        new_page.set("imageId", new_image_id)
        new_page.attrib.pop("selected", None)
        pages_node.append(new_page)

        if disambiguation_node is not None and last_mapping is not None:
            new_mapping = copy.deepcopy(last_mapping)
            new_mapping.set("file", new_file_id)
            disambiguation_node.append(new_mapping)

        for filter_node in filters_node:
            if filter_node.tag == "page-split":
                _clone_page_entry(filter_node, "image", last_image_id, new_image_id)
                continue
            _clone_page_entry(filter_node, "page", last_page_id, new_page_id)
            wrapper = filter_node.find("image-settings")
            if wrapper is not None:
                _clone_page_entry(wrapper, "page", last_page_id, new_page_id)


def _reset_default_geometry(root: ET.Element) -> None:
    """Remove page-specific crop/layout geometry from the bundled defaults."""
    project_pages = root.findall("./pages/page")

    select_content = root.find("./filters/select-content")
    if select_content is None:
        raise ScanTailorError("Default template has no select-content filter")
    select_content[:] = []
    for project_page in project_pages:
        page = ET.SubElement(select_content, "page", id=project_page.attrib["id"])
        ET.SubElement(
            page,
            "params",
            contentDetectionMode="disabled",
            fineTuneCorners="1",
            pageDetectionMode="auto",
        )

    page_layout = root.find("./filters/page-layout")
    if page_layout is None:
        raise ScanTailorError("Default template has no page-layout filter")
    page_layout[:] = []
    for project_page in project_pages:
        page = ET.SubElement(page_layout, "page", id=project_page.attrib["id"])
        params = ET.SubElement(page, "params", autoMargins="0")
        ET.SubElement(
            params,
            "hardMarginsMM",
            bottom="0",
            left="0",
            right="0",
            top="0",
        )
        ET.SubElement(params, "pageRect", height="0", width="0", x="0", y="0")
        ET.SubElement(params, "contentRect", height="0", width="0", x="0", y="0")
        ET.SubElement(params, "contentSizeMM", height="0", width="0")
        ET.SubElement(params, "alignment", hor="center", null="1", vert="center")

    # These are rendered-image cache records, not user output settings.  They
    # depend on the old crop/layout geometry and must not follow it forward.
    for output_page in root.findall("./filters/output/page"):
        cached = output_page.find("output-params")
        if cached is not None:
            output_page.remove(cached)


def generate_project(
    page_paths: list[Path],
    output_dir: Path,
    project_path: Path,
    source_dpi: int,
    template_path: Path | None = None,
) -> int:
    """Generate a project, adapting template settings to the input's page count.

    Pages within the template's original range keep their saved per-page
    settings, page-for-page. Pages beyond that range clone the template's last
    page (files, filter geometry, and output recipe) under fresh ids; fewer
    pages than the template simply drop the trailing ones. See `_resize_pages`.
    """
    using_default_template = template_path is None
    template_path = template_path or default_template_path()
    tree = ET.parse(template_path)
    root = tree.getroot()

    files_node = root.find("files")
    images_node = root.find("images")
    pages_node = root.find("pages")
    directory = root.find("./directories/directory")
    if any(node is None for node in (files_node, images_node, pages_node, directory)):
        raise ScanTailorError("Template is missing required project structure")

    if not (len(files_node) == len(images_node) == len(pages_node)):
        raise ScanTailorError("Template has inconsistent file, image, and page counts")

    _resize_pages(root, len(page_paths))

    if using_default_template:
        _reset_default_geometry(root)

    template_files = list(files_node)
    template_images = list(images_node)

    root.set("outputDirectory", str(output_dir.resolve()))
    directory.set("path", str(page_paths[0].parent.resolve()))

    for file_node, image_node, page_path in zip(
        template_files, template_images, page_paths, strict=True
    ):
        image = cv2.imread(str(page_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ScanTailorError(f"Could not read extracted page: {page_path}")
        height, width = image.shape[:2]
        file_node.set("name", page_path.name)
        size = image_node.find("size")
        dpi = image_node.find("dpi")
        if size is None or dpi is None:
            raise ScanTailorError("Template image record is missing size or DPI")
        size.set("width", str(width))
        size.set("height", str(height))
        dpi.set("horizontal", str(source_dpi))
        dpi.set("vertical", str(source_dpi))

    ET.indent(tree, space="  ")
    tree.write(project_path, encoding="utf-8", xml_declaration=True)
    return _template_output_dpi(root)


def launch_scantailor(executable: Path, project_path: Path) -> None:
    try:
        completed = subprocess.run([str(executable), str(project_path)], check=False)
    except OSError as exc:
        raise ScanTailorError(f"Could not launch ScanTailor Advanced: {exc}") from exc
    if completed.returncode != 0:
        raise ScanTailorError(
            f"ScanTailor Advanced exited with status {completed.returncode}. "
            "The workspace has been preserved."
        )


def expected_tiff_names(page_paths: list[Path]) -> list[str]:
    return [f"{path.stem}.tif" for path in page_paths]


def validate_output(output_dir: Path, expected_names: list[str]) -> list[Path]:
    actual = {
        path.name: path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    }
    expected = set(expected_names)
    missing = sorted(expected - set(actual))
    unexpected = sorted(set(actual) - expected)

    unreadable = []
    for name in expected_names:
        path = actual.get(name)
        if path is not None and cv2.imread(str(path), cv2.IMREAD_UNCHANGED) is None:
            unreadable.append(name)

    if missing or unexpected or unreadable:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        if unreadable:
            details.append("unreadable: " + ", ".join(unreadable))
        raise ScanTailorError(
            "ScanTailor output is incomplete or invalid (" + "; ".join(details) + "). "
            "The workspace has been preserved."
        )

    return [actual[name] for name in expected_names]


def validate_tiff_dpi(tiff_paths: list[Path]) -> int:
    """Return the actual uniform TIFF DPI, rejecting absent or mixed metadata."""
    resolutions = []
    for path in tiff_paths:
        with Image.open(path) as image:
            dpi = image.info.get("dpi")
        if not dpi or len(dpi) != 2:
            raise ScanTailorError(f"TIFF has no usable DPI metadata: {path.name}")
        horizontal, vertical = (round(float(value)) for value in dpi)
        if horizontal <= 0 or vertical <= 0 or horizontal != vertical:
            raise ScanTailorError(
                f"TIFF has invalid or non-square DPI metadata: {path.name} ({dpi})"
            )
        resolutions.append(horizontal)

    unique = sorted(set(resolutions))
    if len(unique) != 1:
        raise ScanTailorError(
            "ScanTailor TIFFs have inconsistent DPI metadata: "
            + ", ".join(str(value) for value in unique)
        )
    return unique[0]
