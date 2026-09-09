# scan-cleanup (Windows) — project memory

## What this repository is

This is the **Windows build** of `scan-cleanup`, forked from the macOS package at
`/Users/heidiwallace/dev/scan-cleanup`. The distribution name is
`scan-cleanup-windows`; the import package (`scan_cleanup`) and the console
command (`scan-cleanup`) are unchanged so fixes port cleanly in either
direction. The macOS package is never edited from here.

`WINDOWS_PORT.md` is the master plan: it lists every change (Step 0, B1–B4,
R1–R4, P1–P4, D1–D2) and the deferred verification items (V1, V2). Read it before
touching anything.

### Windows-specific changes already applied

- **B1** (`ocr.py`) — Ghostscript is detected under `gswin64c` / `gswin32c` / `gs`
  (there is no `gs` on Windows). `_REQUIRED_BINARIES` maps a label to a tuple of
  candidate command names; a program is missing only if none resolve.
- **B2** (`scantailor.py`) — `resolve_scantailor()` has a `sys.platform ==
  "win32"` branch checking `%ProgramFiles%`, `%ProgramFiles(x86)%`,
  `%ProgramW6432%`, `%LOCALAPPDATA%` for `<root>/<folder>/scantailor-advanced.exe`.
  Folder names carry a `TODO(win-verify)` — confirm against the real build (V1).
- **B3** (`pipeline.py`, `_move_replace`) — the final PDF move falls back from
  `os.replace` to `shutil.move` on a cross-drive error (WinError 17 / EXDEV),
  since the workspace is on `C:` and the output may be on another drive.
- **B4** (`_imageio.py`, used in `pdf_io.py` and `scantailor.py`) — image files
  are read/written via `np.fromfile`/`np.tofile` + `cv2.imdecode`/`imencode`,
  because `cv2.imread`/`imwrite` fail silently on non-ASCII paths on Windows.
- **R1** (`pipeline.py`, `_remove_workspace`) — workspace deletion clears the
  read-only bit, retries, and warns instead of raising if a file is still locked.
- **R2 / R4** (`workspace.py`, `safe_stem`) — the temp-folder stem is stripped of
  Windows-invalid characters and capped at 40 chars; the no-root prefix is `sc-`
  (not `scan-cleanup-`) to conserve path length against the 260-char limit.
- **R3** (`.gitattributes`) — line endings pinned to LF so a Windows checkout
  does not rewrite the bundled `.scantailor` template.
- **R4** (`scantailor.py`, `validate_output`) — expected/actual TIFF names are
  compared case-insensitively.
- **R4** (`cli.py`, `_make_streams_lenient`) — stdout/stderr use
  `errors="backslashreplace"` so a non-ASCII path in a message cannot raise a
  secondary `UnicodeEncodeError` when output is redirected.
- **P1** (`pyproject.toml`) — name `scan-cleanup-windows`, version
  `0.3.0.dev0`, classifier `Operating System :: Microsoft :: Windows`,
  `[tool.uv.build-backend] module-name = "scan_cleanup"`.
- **P2** (`.github/workflows/ci.yml`) — matrix `[ubuntu-latest, windows-latest]`,
  plus an `ocr-smoke-windows` job that `choco install`s Tesseract + Ghostscript
  and runs `pytest -m ocr_smoke`.
- **P4** (`.gitignore`) — Windows clutter entries added; `CLAUDE.md` removed from
  the ignore list (it is tracked here).

### Still to do (need a Windows machine or VM — see WINDOWS_PORT.md)

- **V1** — verify the ScanTailor Advanced Windows build opens a `.ScanTailor`
  project passed as its first CLI argument; confirm its install folder for B2;
  settle its provenance before D1 points users at a download. Link on record:
  `https://www.terabox.com/sharing/link?surl=ZlDnuOMokDp747Sehnhk9A` (a TeraBox
  share, not an official source — do not fetch it from an agent environment).
- **V2** — one real `scan-cleanup process` run on Windows to confirm ocrmypdf
  works end to end (the `ocr-smoke-windows` CI job is the automated proxy).
- One manual acceptance pass of the real interactive GUI round-trip.

## Current architecture

This package no longer attempts to reproduce ScanTailor's image processing in
Python. It coordinates ScanTailor Advanced interactively:

```text
PDF -> ordered PNGs -> generated ScanTailor project -> user processing
    -> validated ordered TIFFs -> PDF -> OCR
```

The former Sauvola, deskew, and despeckle implementation was archived before
the revamp in `.snapshots/scan-cleanup-pre-scantailor-revamp-20260814-archive.tar.gz`.
The archive checksum is stored beside it.

## Important guarantees

- Page order comes from `workspace.json`, never directory enumeration.
- Final physical page size uses validated DPI metadata from the actual TIFFs,
  not the template value (users may change output DPI inside ScanTailor).
- ScanTailor output must exactly match the expected TIFF list.
- Missing, extra, or unreadable TIFFs preserve the workspace and stop the run.
- `scan-cleanup resume WORKSPACE OUTPUT_DIR` reopens the same project.
- OCR always runs.
- The final name is `<input-stem>_processed.pdf`.
- `scan-cleanup process` asks for interactive confirmation before replacing an
  existing output file. `scan-cleanup batch` instead skips, without prompting,
  any input whose output already exists — so an interrupted batch can be
  re-run to pick up only the unfinished files. Pass `--overwrite` to either
  command to bypass this and force reprocessing.

## Template behavior

The bundled version-4 project is at
`src/scan_cleanup/templates/scantailor-advanced-default.scantailor`.
It preserves page-specific transformations by ordinal. When generating a project
from the bundled template, the package clears saved Select Content and Page
Layout geometry. Content detection remains disabled, while automatic Page Box
detection has Fine Tune Page Corners enabled. Page Layout defaults to not matching
the page size with other pages. The template contains 40 pages, but the
generator (`_resize_pages` in `scantailor.py`) adapts it to any input page
count before applying those defaults:

- Fewer pages: keep the template's first N pages' settings, in scan order.
- More pages: clone the template's last page — its file/image/page nodes and
  every per-page filter entry (`fix-orientation`, `page-split`, `deskew`,
  `select-content`, `page-layout`, `output`) — once per extra page, assigning
  fresh sequential ids. `deskew` carries two parallel page-keyed structures
  (direct `page` children for content-based detection, plus an
  `image-settings/page` wrapper for the legacy image-based path); both are
  resized. `page-split` is keyed by image id, not page id, and is resized on
  that basis.

Cloned pages' auto-detection filters (page split, deskew, fix orientation) carry
forward the *previous* page's geometry as a placeholder — safe because those
filters run in `auto` mode, so a fresh page's content is intended to be
reviewed and re-detected by the user during the interactive ScanTailor session,
same as any other page. The output recipe (DPI, binarization method, etc.) is
the one setting that is genuinely meant to be identical across all pages, so
cloning it for extra pages is correct rather than a placeholder.

The template's run-specific fields are replaced: source directory, filenames,
pixel dimensions, source DPI, and output directory. Internal IDs remain stable,
allowing all filter settings to continue referring to their corresponding page.
Stale rendered-output cache records are removed along with the saved geometry.
The template was updated from the project saved during the first successful
end-to-end test. Its output DPI is 600 and it includes the user's saved settings
from that test session.

The output recipe's Otsu threshold adjustment (`thresholdAdj` on every page's
`<bw>` element) is set to `-15` (previously `0`), which renders text thinner
than the plain Otsu threshold would. See the README's "Default ScanTailor
settings" for the full human-readable list of bundled defaults.

## ScanTailor executable

The executable accepts a `.ScanTailor` project as its first argument.
`resolve_scantailor()` in `scantailor.py` checks, in order:

1. an explicit `--scantailor` path,
2. the `SCANTAILOR_ADVANCED` environment variable,
3. `scantailor-advanced` / `scantailor-advanced.exe` on `PATH`,
4. **Windows** (`sys.platform == "win32"`): `<root>/<folder>/scantailor-advanced.exe`
   for each of `%ProgramFiles%`, `%ProgramFiles(x86)%`, `%ProgramW6432%`,
   `%LOCALAPPDATA%` and folder in `ScanTailor Advanced`, `STAdvanced`,
   `ScanTailor`. Checked directly because the Windows installer does not add
   itself to `PATH`. `TODO(win-verify)`: confirm the real folder name; a
   portable `.zip` build has no fixed location and needs `--scantailor` or the
   env var.
5. **macOS** (`sys.platform == "darwin"`): the Homebrew-prefix binary and the
   `.app` bundle locations (inherited from the macOS package; harmless on
   Windows, never reached).

If nothing matches, `ScanTailorError` lists every path that was checked.

## Workspace lifecycle

Successful workspaces are deleted by default after the final OCR PDF is safely
moved into place (`_remove_workspace`, which tolerates Windows file locking).
The CLI's `--keep-workspace` option disables cleanup for development and
inspection. Failures always retain the workspace. A workspace contains `input/`,
`out/`, `project.ScanTailor`, `workspace.json`, and later `assembled.pdf`.

Without `--workspace-root`, the workspace is created under the OS temp directory
(`%TEMP%` on Windows) with a short `sc-<stem>-` prefix. On Windows, prefer
`--workspace-root C:\sc` (short, local, non-synced) to stay clear of the
260-character path limit; see WINDOWS_PORT.md R2.

## Validation

Run (works on macOS/Linux and Windows):

```bash
uv run pytest          # 42 tests; ocr_smoke tests skip unless Tesseract + Ghostscript present
uv run ruff check .
uv build
```

`uv run pytest -m ocr_smoke` runs the real OCR pipeline (needs Tesseract and
Ghostscript). Manual validation should use a short sample first. Real scan data
lives under `tests/data/` and is git-ignored.
