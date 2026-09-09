# scan-cleanup

`scan-cleanup` coordinates an interactive ScanTailor Advanced workflow for
scanned PDFs:

1. Extract each PDF page to an ordered PNG in a persistent run workspace.
2. Generate and open a ScanTailor Advanced project using the bundled settings.
3. Wait while the user reviews settings and produces TIFF pages in `out/`.
4. After ScanTailor closes, validate that every source page has exactly one TIFF.
5. Assemble TIFFs in the original PDF page order.
6. Add an invisible OCR layer and write `<input-name>_processed.pdf`.

The package never trusts filesystem iteration for page order. The extraction
order is recorded in `workspace.json`, and TIFFs are assembled only after a
complete one-to-one filename validation.

## Current development scope

The bundled project template contains the settings saved during the first
successful end-to-end test, including 600 DPI output and page-specific
transformations for 40 pages. Saved Select Content and Page Layout
geometry is cleared when a default project is generated. Content detection starts
disabled; Page Box detection starts on Auto with Fine Tune Page Corners enabled.
Page Layout starts with "Match size with other pages" unchecked.

### Default ScanTailor settings

These are the Output-stage settings baked into the bundled project template
and applied to every page by default. Any of them can be changed per-page (or
for the whole batch) inside the interactive ScanTailor Advanced session before
processing:

- Output DPI = 600
- Color mode = Black and white
- Binarization method = Otsu
- Otsu threshold adjustment = -15 (renders text thinner than a plain Otsu threshold)
- Despeckle level = 2 (Normal)
- Morphological smoothing = on
- Normalize illumination (B&W) = on
- Picture shape detection = Free, sensitivity 100
- Dewarping = off
- Content detection = disabled (Page Box detection: Auto, Fine Tune Page Corners = on)
- Match page size with other pages = off

Inputs are not limited to 40 pages. An input with fewer pages uses the
template's first N pages' settings; an input with more pages clones the
template's last page (files, filter settings, and the output recipe) for each
additional page, under fresh ids. Cloned pages inherit the same output recipe
(DPI, binarization, etc.) as the rest of the volume, but their auto-detected
geometry (page split, deskew, fix orientation) is a starting point, not a
guarantee — review it like any other page during the interactive ScanTailor
session.

Successful workspaces are deleted after the final OCR PDF has been written.
Failed or incomplete workspaces are always retained. During development, pass
`--keep-workspace` to retain a successful workspace for inspection.

`resolve_scantailor()`'s fixed-location discovery (see "Installing ScanTailor
Advanced" below) only checks macOS install paths. On Linux and Windows it
still falls back to bare PATH discovery, with no fixed-location safety net —
adding equivalent fixed candidates for those platforms is planned.

## Requirements

- Python 3.12+
- ScanTailor Advanced
- Tesseract
- Ghostscript

### Installing ScanTailor Advanced (macOS)

`scan-cleanup` looks for the `scantailor-advanced` executable at, in order:
1. `--scantailor PATH`
2. the `SCANTAILOR_ADVANCED` environment variable
3. `scantailor-advanced` on `PATH`
4. a fixed, supported install location: `$(brew --prefix)/bin/scantailor-advanced`
5. `/Applications/ScanTailor Advanced.app/Contents/MacOS/scantailor-advanced`
   (the official `.app` distribution, if installed there instead)

Option 4 is the supported install path for this package and requires no flags
or environment variables once set up. There is no upstream Homebrew formula, so
build it from source and install it into the Homebrew prefix directly:

```bash
brew install cmake ninja qt jpeg-turbo libpng libtiff
git clone https://github.com/ScanTailor-Advanced/scantailor-advanced.git
cmake -S scantailor-advanced -B scantailor-advanced/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build scantailor-advanced/build
cmake --install scantailor-advanced/build --prefix "$(brew --prefix)"
```

This installs a real, standalone binary at `$(brew --prefix)/bin/scantailor-advanced`
(dependencies are linked via absolute Homebrew paths, so it does not depend on
the source checkout after this point — the checkout can be deleted or moved
freely). Confirm it resolves with:

```bash
uv run python -c "from scan_cleanup.scantailor import resolve_scantailor; print(resolve_scantailor())"
```

## Installation

From a clone of the repository, create the locked development environment:

```bash
cd scan-cleanup
uv sync
```

On macOS, OCR dependencies can be installed with:

```bash
brew install tesseract ghostscript
```

## Process a PDF

```bash
uv run scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY \
  --scantailor /path/to/scantailor-advanced
```

The final file is:

```text
OUTPUT_DIRECTORY/INPUT_processed.pdf
```

If that file already exists, the CLI asks before replacing it.

For a local ScanTailor Advanced build:

```bash
uv run scan-cleanup process tests/data/MH_1976_vIV_bio_1-40.pdf output \
  --scantailor /path/to/scantailor-advanced \
  --workspace-root development-workspaces
```

ScanTailor opens the generated project automatically. Review or adjust its
settings, process all pages at the Output stage, and then close the application.
The Python command resumes after the ScanTailor process exits.

On success, only the original input PDF and final processed PDF are retained.
Use `--keep-workspace` when intermediate PNGs, TIFFs, the project, and the
pre-OCR assembled PDF are needed for development or inspection.

The workspace location depends only on `--workspace-root`; it is unrelated to
where the input PDF or output directory live (`workspace.py`'s
`create_workspace`). Without `--workspace-root`, the workspace is created under
the OS default temp directory (macOS: `$TMPDIR`, e.g.
`/var/folders/.../T/scan-cleanup-<stem>-<random>/`) regardless of whether the
input or output paths are inside a cloud-synced folder (Google Drive, Dropbox,
etc.) — so the hundreds of intermediate PNGs/TIFFs never get written into a
folder a sync client is watching, even with no flag at all. Passing
`--workspace-root DIR` only changes this for choosing a stable, inspectable
path (e.g. for use with `--keep-workspace`); if `DIR` is itself inside a
cloud-synced folder, prefer a local, non-synced path instead.

## Resume a failed workspace

If ScanTailor closes with missing, extra, or unreadable TIFFs, the command stops
and prints the workspace path. Correct the issue with:

```bash
uv run scan-cleanup resume WORKSPACE OUTPUT_DIRECTORY
```

The same ScanTailor project reopens. After it closes, validation, PDF assembly,
and OCR are attempted again. A successful resume deletes the workspace unless
`--keep-workspace` is supplied.

## Batch processing

```bash
uv run scan-cleanup batch INPUT_DIRECTORY OUTPUT_DIRECTORY \
  --scantailor /path/to/scantailor-advanced
```

ScanTailor opens once for each PDF, sequentially. Any input PDF whose
corresponding `_processed.pdf` already exists in `OUTPUT_DIRECTORY` is skipped
automatically, without prompting — so if the batch is interrupted partway
through, re-running the same command picks up only the unfinished files. Pass
`--overwrite` to reprocess everything instead.

## Development

```bash
uv run pytest
uv run ruff check .
uv build
```

The GitHub Actions workflow performs the same lint, test, and package-build
checks on pushes and pull requests.

The pre-revamp Python image-processing implementation is stored under
`.snapshots/` with a SHA-256 checksum and is not part of the new Git history.
