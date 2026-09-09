# scan-cleanup (Windows)

This is the **Windows build** of `scan-cleanup` (distribution name
`scan-cleanup-windows`; the command is still `scan-cleanup`). It is functionally
identical to the macOS package — the differences are Windows executable
discovery, Ghostscript's command name, cross-drive file moves, and Unicode path
handling. Commands below use PowerShell.

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

On Windows, `resolve_scantailor()` checks the standard Program Files install
locations directly (see "Installing ScanTailor Advanced" below), because the
installer does not add itself to `PATH`. A portable (`.zip`) build has no fixed
location — pass `--scantailor` or set `SCANTAILOR_ADVANCED` for that.

## Requirements

- Python 3.12+ (or let `uv` install it: `uv python install 3.12`)
- ScanTailor Advanced (Windows 10/11 build)
- Tesseract
- Ghostscript

All three non-Python programs must be on your `PATH` (ScanTailor is also found
automatically in its standard install folder).

### Installing uv

```powershell
winget install astral-sh.uv
```

(or the PowerShell bootstrap from <https://astral.sh/uv>).

### Installing ScanTailor Advanced

Install a Windows 10/11 build of ScanTailor Advanced. `scan-cleanup` looks for
the executable at, in order:

1. `--scantailor "C:\Path\To\scantailor-advanced.exe"`
2. the `SCANTAILOR_ADVANCED` environment variable
3. `scantailor-advanced.exe` on `PATH`
4. `%ProgramFiles%\ScanTailor Advanced\scantailor-advanced.exe` (and the
   `ProgramFiles(x86)` / `ProgramW6432` / `LOCALAPPDATA` equivalents)

A normal installer places the executable where step 4 finds it, so no flags are
needed. For a portable `.zip`, extract it somewhere stable and use step 1 or 2.

> Windows SmartScreen or antivirus may warn the first time you launch a freshly
> downloaded ScanTailor Advanced binary. This is expected for an unsigned
> third-party download; allow it to run if you trust the source.

Confirm discovery with:

```powershell
uv run python -c "from scan_cleanup.scantailor import resolve_scantailor; print(resolve_scantailor())"
```

### Installing Tesseract and Ghostscript

```powershell
winget install UB-Mannheim.TesseractOCR
winget install ArtifexSoftware.GhostScript
```

Or install by hand:

- **Tesseract** — the UB Mannheim build
  (<https://github.com/UB-Mannheim/tesseract/wiki>). Enable "Add to PATH" during
  setup, or add its folder (e.g. `C:\Program Files\Tesseract-OCR`) to `PATH`
  afterwards. English language data is included by default.
- **Ghostscript** — the 64-bit release from
  <https://ghostscript.com/releases/gsdnld.html>. Add its `bin` folder (which
  contains `gswin64c.exe`, e.g. `C:\Program Files\gs\gs10.03.1\bin`) to `PATH`.

Close and reopen your terminal after changing `PATH`.

## Installation

From a clone of the repository, create the locked development environment:

```powershell
cd scan-cleanup-windows
uv sync
```

## Process a PDF

```powershell
uv run scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY --scantailor "C:\Path\To\scantailor-advanced.exe"
```

(`--scantailor` can be omitted once ScanTailor Advanced is installed in its
standard folder.) To split a long command across lines in PowerShell, end each
line with a backtick `` ` ``.

The final file is:

```text
OUTPUT_DIRECTORY\INPUT_processed.pdf
```

If that file already exists, the CLI asks before replacing it.

For a portable ScanTailor Advanced build:

```powershell
uv run scan-cleanup process "tests\data\MH_1976_vIV_bio_1-40.pdf" output `
  --scantailor "C:\Tools\scantailor-advanced\scantailor-advanced.exe" `
  --workspace-root C:\sc
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
the OS temp directory (`%TEMP%`, e.g.
`C:\Users\<you>\AppData\Local\Temp\sc-<stem>-<random>\`) regardless of whether
the input or output paths are inside a cloud-synced folder (OneDrive, Google
Drive, Dropbox) — so the hundreds of intermediate PNGs/TIFFs never get written
into a folder a sync client is watching.

**Windows path length.** Windows rejects paths longer than 260 characters by
default. Deep temp paths plus long volume names plus a synced-folder
`--workspace-root` can hit that limit and cause confusing image-read errors. On
Windows, prefer a short, local, non-synced workspace root:

```powershell
uv run scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY --workspace-root C:\sc
```

(or enable long-path support via the `LongPathsEnabled` Group Policy / registry
setting).

## Resume a failed workspace

If ScanTailor closes with missing, extra, or unreadable TIFFs, the command stops
and prints the workspace path. Correct the issue with:

```powershell
uv run scan-cleanup resume WORKSPACE OUTPUT_DIRECTORY
```

The same ScanTailor project reopens. After it closes, validation, PDF assembly,
and OCR are attempted again. A successful resume deletes the workspace unless
`--keep-workspace` is supplied.

## Batch processing

```powershell
uv run scan-cleanup batch INPUT_DIRECTORY OUTPUT_DIRECTORY --scantailor "C:\Path\To\scantailor-advanced.exe"
```

ScanTailor opens once for each PDF, sequentially. Any input PDF whose
corresponding `_processed.pdf` already exists in `OUTPUT_DIRECTORY` is skipped
automatically, without prompting — so if the batch is interrupted partway
through, re-running the same command picks up only the unfinished files. Pass
`--overwrite` to reprocess everything instead.

## Development

```powershell
uv run pytest
uv run ruff check .
uv build
```

The GitHub Actions workflow runs lint, tests, and `uv build` on both
`ubuntu-latest` and `windows-latest`. A separate `ocr-smoke-windows` job
installs Tesseract and Ghostscript and runs `uv run pytest -m ocr_smoke`, the
one test that exercises the real OCR pipeline end to end (it is skipped in the
normal run when those programs are absent).

See `WINDOWS_PORT.md` for the full list of Windows-specific changes and the
verification steps still outstanding (`V1`, `V2`).
