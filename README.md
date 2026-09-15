# scan-cleanup (Windows)

`scan-cleanup` helps you clean up scanned PDFs (for example, old scanned
documents) so the pages are straightened, cropped, cleaned up, and turned
into a searchable PDF. This is the **Windows version** of the tool. It walks
you through the process step by step:

1. It pulls each page out of your PDF as an image.
2. It opens a program called ScanTailor Advanced, already set up with good
   default settings, so you can look over and adjust each page.
3. Once you close ScanTailor Advanced, it automatically checks that every
   page came out correctly.
4. It puts the cleaned-up pages back together in the right order.
5. It makes the text on the pages searchable and saves the finished PDF.

## Getting set up

This section only needs to be done once. It walks through installing a few
free programs, plus `scan-cleanup` itself. Once it's done, skip down to
"Cleaning up a PDF" for everyday use.

Every step below is run in **PowerShell**, Windows' command-line app. If it's
not already open, click the **Start** button, type "PowerShell", and open
**Windows PowerShell**. Each gray box below is a command: click into the box
to copy it, right-click inside the PowerShell window to paste it (or press
Ctrl+V), press Enter, and wait for it to finish before moving to the next
one.

### Step 1: Install uv

`uv` is the tool `scan-cleanup` uses to set itself up and run. Install it
with:

```powershell
winget install astral-sh.uv
```

`winget` is Windows' built-in app installer (included on Windows 10 and 11).
If it asks you to accept a license agreement, type `Y` and press Enter. If
`winget` isn't recognized at all, open the **Microsoft Store** app, search
for "App Installer", and install that — it adds `winget` — then try the
command above again.

(`scan-cleanup` also needs Python, version 3.12 or newer — but you don't need
to install that yourself; `uv` will take care of it automatically the first
time it's needed.)

**Close this PowerShell window and open a new one** before continuing —
newly installed programs are only visible in windows opened after the
install finishes.

### Step 2: Install ScanTailor Advanced

ScanTailor Advanced is the program you'll use to review and adjust each
scanned page. The project's current GitHub repository
(<https://github.com/ScanTailor-Advanced/scantailor-advanced>) only publishes
Linux builds now, so download the installer instead from the original
developer's GitHub project, which still hosts the last Windows release:

- 64-bit (use this on a normal modern PC):
  <https://github.com/4lex4/scantailor-advanced/releases/download/v1.0.16/scantailor-advanced-1.0.16-win64.exe>
- 32-bit (only if you know you're on a 32-bit Windows install):
  <https://github.com/4lex4/scantailor-advanced/releases/download/v1.0.16/scantailor-advanced-1.0.16-win32.exe>

This is an older version (v1.0.16, from 2019 — the last one built for
Windows before the project moved to the Linux-only-releasing repository
above), but it's a genuine official release directly from GitHub, which is
safer to trust than a third-party mirror site. Run the downloaded installer
once it finishes downloading.

> **A security warning is normal.** The first time you launch a freshly
> downloaded ScanTailor Advanced, Windows may show a blue "Windows protected
> your PC" box (SmartScreen), or your antivirus may flag it. This happens
> because the program isn't digitally signed by a large company, not because
> anything is wrong. If you trust where you got it from, click **More info**,
> then **Run anyway**.

Once installed, `scan-cleanup` will be able to find ScanTailor Advanced
automatically — you won't need to point to it manually, as long as it went
into its normal install location. (If you were given a "portable" version
instead — a `.zip` file rather than an installer — see the technical
appendix below for how to point `scan-cleanup` at it directly.)

### Step 3: Install the other required programs

`scan-cleanup` also needs two more small programs: one that reads text out of
scanned pages (Tesseract), and one that helps assemble the final PDF
(Ghostscript).

Install Tesseract with:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Ghostscript isn't available through `winget` anymore, so install it by hand
instead:

1. Go to <https://ghostscript.com/releases/gsdnld.html> and download the
   64-bit Windows release (look for a filename like
   `gs10.xx.x-x64-installer.exe`).
2. Run the downloaded installer, accepting the defaults. `scan-cleanup` will
   find it automatically afterward — there's nothing else to do here.

**Close this PowerShell window and open a new one** afterward, so it picks up
Tesseract. To check it installed correctly, run:

```powershell
tesseract --version
```

It should print a version number. If it says something like "not
recognized," try closing PowerShell and reopening it once more, or
reinstalling Tesseract — if it still doesn't work, see the technical
appendix's "Adding a program to PATH by hand" note.

### Step 4: Install scan-cleanup

Installing `scan-cleanup` uses Git, a program for downloading project code.
If you don't already have it, install it with:

```powershell
winget install Git.Git
```

**Close this PowerShell window and open a new one** afterward, then install
`scan-cleanup` itself:

```powershell
uv tool install git+https://github.com/heidiwallace/scan-cleanup-windows
```

That's it — `scan-cleanup` is now installed and ready to use from any
folder, no project folder to keep track of.

**Close this PowerShell window and open a new one** one more time, so the
`scan-cleanup` command is recognized.

## Using scan-cleanup

In the commands below, replace anything in ALL CAPS with your own file or
folder path — for example, `INPUT.pdf` becomes the actual path to your PDF,
and `OUTPUT_DIRECTORY` becomes the folder you want the result saved in. The
easiest way to get a path right is to type the command up to that point, then
drag the file or folder from File Explorer directly into the PowerShell
window — it will fill in the correct path for you. If a path contains spaces,
wrap it in quotes, like `"C:\Users\you\My Scans\book.pdf"`.

### Cleaning up a PDF

To clean up a single scanned PDF, run:

```powershell
scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY
```

The finished file will appear as:

```text
OUTPUT_DIRECTORY\INPUT_processed.pdf
```

If a file with that name already exists, you'll be asked to confirm before
it gets replaced.

Shortly after you run the command, ScanTailor Advanced will open on its own
with your pages already loaded and good default settings applied. Look
through the pages, make any adjustments you'd like, then process all the
pages and close the ScanTailor Advanced window. `scan-cleanup` will notice
the window closed and automatically finish the job — assembling the pages
and making the text searchable.

When it's done, only your original PDF and the new finished PDF are kept;
everything created along the way is cleaned up automatically. If you'd like
to keep those in-between files (useful for troubleshooting), add
`--keep-workspace` to the command.

> **A note on where to save your files.** Try to keep your PDFs on your
> computer's main drive, in a short folder path, rather than deep inside a
> long chain of folders or a synced folder like OneDrive or Google Drive.
> Windows has an old rule that file locations longer than 260 characters can
> cause confusing errors, and
> the more nested or synced your folders are, the more likely you are to hit
> it. If you do run into strange file-not-found errors partway through,
> this is the first thing to check — see the technical appendix for the
> details and a workaround.

### If something goes wrong partway through

If ScanTailor Advanced closes but a page is missing or didn't come out
right, `scan-cleanup` will stop and tell you where your in-progress files are
being kept (this location is called the "workspace"). Fix the problem, then
pick up where you left off with:

```powershell
scan-cleanup resume WORKSPACE OUTPUT_DIRECTORY
```

(Use the workspace location `scan-cleanup` showed you.) This reopens
ScanTailor Advanced on the same project. Once you close it again,
`scan-cleanup` will check the pages and finish the job.

### Cleaning up many PDFs at once

If you have a whole folder of scanned PDFs to clean up, you can process them
one after another with a single command:

```powershell
scan-cleanup batch INPUT_DIRECTORY OUTPUT_DIRECTORY
```

ScanTailor Advanced will open once for each PDF in turn. If you need to stop
partway through, you can simply run the same command again later — any PDF
that's already been finished will be skipped automatically, so you'll pick up
right where you left off. If you'd like to redo files that were already
finished, add `--overwrite` to the command.

## Technical appendix

The rest of this README is written for contributors working on the
`scan-cleanup` codebase itself — it isn't needed to run the tool day to day.

### What's different about this Windows build

This package is functionally identical to the macOS `scan-cleanup` package —
same command, same pipeline, same options. The differences are entirely
platform plumbing:

- **Ghostscript's command name.** Ghostscript's command-line executable is
  called `gs` on macOS/Linux but `gswin64c` (or `gswin32c` on a 32-bit
  install) on Windows. `ocr.py`'s `_REQUIRED_BINARIES` maps a human-readable
  label to a tuple of acceptable command names, and the dependency check
  passes if any one of them resolves via `shutil.which`.
- **Ghostscript discovery.** Ghostscript's Windows installer never adds
  itself to `PATH` — no checkbox for it exists, unlike Tesseract's UB
  Mannheim build — so even a completely standard install leaves
  `gswin64c.exe` unreachable by name. `ocr.py`'s
  `_ensure_windows_ghostscript_discoverable()` checks the standard install
  location (`%ProgramFiles%\gs\gs<version>\bin\`, also checking
  `%ProgramFiles(x86)%`) and, if `shutil.which` can't already find any of
  Ghostscript's command names, prepends that folder to the current
  process's `PATH` so both the dependency check and every subprocess
  `ocrmypdf` launches afterward (which inherit that environment) can find
  it. This mirrors `resolve_scantailor()`'s fixed-location fallback for the
  same underlying reason — Windows installers vary in whether they touch
  `PATH` at all, and this package can't assume they do.
- **ScanTailor Advanced discovery.** `resolve_scantailor()` in
  `scantailor.py` checks, in order: an explicit `--scantailor` path, the
  `SCANTAILOR_ADVANCED` environment variable, `scantailor-advanced.exe` on
  `PATH`, then — because the Windows installer does not add itself to
  `PATH` — a `sys.platform == "win32"` branch that checks
  `<root>\<folder>\scantailor-advanced.exe` for each of `%ProgramFiles%`,
  `%ProgramFiles(x86)%`, `%ProgramW6432%`, `%LOCALAPPDATA%`, and folder name
  in `ScanTailor Advanced`, `STAdvanced`, `ScanTailor`. (These exact folder
  names carry a `TODO(win-verify)` in the code pending confirmation against a
  real installed build — see `CLAUDE.md`'s "Still to do" list.) A portable
  `.zip` build has no fixed install location, so it must be pointed at
  directly via `--scantailor` or `SCANTAILOR_ADVANCED`.
- **Cross-drive file moves.** The final step moves the finished PDF out of
  the temporary workspace (always on `C:`) into the user's chosen output
  folder, which may be on a different drive, an external disk, or a network
  share. A plain rename (`os.replace`) only works within one drive on
  Windows and raises `WinError 17` across drives, so `pipeline.py`'s
  `_move_replace()` catches that specific error and falls back to
  copy-then-delete (`shutil.move`).
- **Unicode file paths.** OpenCV (`cv2.imread`/`imwrite`) silently fails on
  Windows when a file path contains non-ASCII characters — which can happen
  via a Windows username with an accent, or a source PDF filename with one.
  `_imageio.py` reads and writes image files via `np.fromfile`/`np.tofile`
  combined with `cv2.imdecode`/`imencode` instead, which is Unicode-safe;
  `pdf_io.py` and `scantailor.py` use these helpers for every file-path image
  read/write.
- **Workspace folder cleanup.** Deleting the temporary workspace can fail on
  Windows if another process (antivirus, a leftover ScanTailor instance,
  Explorer showing a thumbnail) still has a file open inside it.
  `pipeline.py`'s `_remove_workspace()` clears the read-only attribute,
  retries, and logs a warning instead of raising if deletion still fails —
  the finished PDF is already safely written by that point.
- **Short workspace folder names.** The temp-folder prefix is `sc-` here
  (rather than `scan-cleanup-` on macOS) to conserve path length against
  Windows' 260-character limit (see below). `workspace.py`'s `safe_stem()`
  also strips characters Windows forbids in filenames (`< > : " | ? *`) and
  caps the stem at 40 characters.
- **Case-insensitive TIFF name matching.** `scantailor.py`'s
  `validate_output()` compares ScanTailor's output filenames against the
  expected list case-insensitively, in case a Windows ScanTailor build ever
  writes e.g. `PAGE-01.TIF` instead of `page-01.tif`.
- **Lenient console output.** `cli.py`'s `_make_streams_lenient()` sets
  `errors="backslashreplace"` on stdout/stderr, so printing an error message
  containing a non-ASCII path can't itself throw a secondary
  `UnicodeEncodeError` when output is redirected to a file or another
  program.
- **Line endings.** `.gitattributes` pins the repo to LF line endings so a
  Windows checkout doesn't rewrite the bundled `.scantailor` XML template
  with CRLF endings (Git on Windows converts line endings on checkout by
  default unless told not to).

None of this affects behavior a user would notice; it's documented here so a
future contributor porting a fix between this repo and the macOS
`scan-cleanup` package knows which lines are Windows-specific plumbing versus
shared logic.

### Windows' 260-character path length limit

By default, Windows rejects any file path longer than 260 characters. This
package's temporary workspace folders nest several levels deep (something
like `...\Temp\sc-<pdf name>-<random>\out\<pdf name>-NN.tif`), and a deep or
already-long `--workspace-root` (especially inside a synced OneDrive/Google
Drive tree, which adds its own long prefix) can push a path over that limit.
When it happens, the symptom is a confusing image-read or image-write error
partway through, not an explicit "path too long" message.

Two mitigations, either is enough on its own:

- Point `--workspace-root` at something short and local, e.g.:

  ```powershell
  scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY --workspace-root C:\sc
  ```

- Or enable long-path support system-wide via the `LongPathsEnabled` Group
  Policy / registry setting (search "enable long paths Windows 10/11" for
  the exact steps for your Windows edition).

### Adding a program to PATH by hand

`PATH` is the list of folders Windows searches when you type a command name.
`winget install` normally adds a new program to `PATH` automatically, but if
`tesseract --version` or `gswin64c --version` says "not recognized" after
reopening PowerShell:

1. Find the program's install folder — Tesseract is typically under
   `C:\Program Files\Tesseract-OCR`; Ghostscript's `bin` folder (containing
   `gswin64c.exe`) is typically under `C:\Program Files\gs\gs<version>\bin`.
2. Search the web for "add a folder to PATH Windows 11" (or 10) for the
   current System Properties dialog steps, or reinstall the program and make
   sure any "Add to PATH" checkbox is ticked during setup.
3. Close and reopen PowerShell — a window opened before the change won't see
   it.

### Using a portable (`.zip`) ScanTailor Advanced build

If you have a portable ScanTailor Advanced — a `.zip` you extracted somewhere
rather than something installed via a `.exe` installer — it has no fixed
location for `scan-cleanup` to find automatically. Either pass its path on
every run:

```powershell
scan-cleanup process INPUT.pdf OUTPUT_DIRECTORY --scantailor "C:\Tools\scantailor-advanced\scantailor-advanced.exe"
```

or set it once per PowerShell session (or in your PowerShell profile, to make
it permanent):

```powershell
$env:SCANTAILOR_ADVANCED = "C:\Tools\scantailor-advanced\scantailor-advanced.exe"
```

### Splitting a command across multiple lines

PowerShell uses a backtick `` ` `` at the end of a line to continue a command
onto the next line (unlike the backslash used in bash/macOS examples). The
example below uses the repo's bundled sample PDF and `uv run`, so it assumes
a local development checkout (see "Development" below) rather than the
`uv tool install` route end users take:

```powershell
uv run scan-cleanup process "tests\data\MH_1976_vIV_bio_1-40.pdf" output `
  --scantailor "C:\Tools\scantailor-advanced\scantailor-advanced.exe" `
  --workspace-root C:\sc
```

### The bundled ScanTailor project template

Rather than generating a bare ScanTailor Advanced project from scratch for
every job, `scan-cleanup` ships a pre-configured project file at
`src/scan_cleanup/templates/scantailor-advanced-default.scantailor` and
adapts it to each input. This gives every job the same sensible Output-stage
starting point without the user having to configure ScanTailor Advanced by
hand each time (see "Default ScanTailor settings" below for exactly what it
sets).

The template itself is just the project file saved at the end of the first
successful end-to-end test, so it reflects one real, human-reviewed 40-page
session (600 DPI output, plus that session's per-page transformations) rather
than being written by hand. Because the per-page geometry it contains (Select
Content, Page Layout) belongs to that specific 40-page scan, `scan-cleanup`
clears it when generating a new project — every job starts from a blank page
layout, while keeping the template's Output-stage recipe intact. Content
detection starts disabled; Page Box detection starts on Auto with Fine Tune
Page Corners enabled; "Match page size with other pages" starts unchecked.

### Default ScanTailor settings

These are the Output-stage settings baked into the bundled project template
and applied to every page by default. Any of them can be changed per-page (or
for the whole batch) inside the interactive ScanTailor Advanced session
before processing:

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

### Input page counts beyond the template

Inputs are not limited to 40 pages. An input with fewer pages uses the
template's first N pages' settings; an input with more pages clones the
template's last page (files, filter settings, and the output recipe) for each
additional page, under fresh ids. Cloned pages inherit the same output recipe
(DPI, binarization, etc.) as the rest of the volume, but their auto-detected
geometry (page split, deskew, fix orientation) is a starting point, not a
guarantee — review it like any other page during the interactive ScanTailor
session.

### Workspace location and lifecycle

Each run creates a "workspace": a directory holding the extracted PNGs, the
generated `.ScanTailor` project, the resulting TIFFs, `workspace.json` (see
"Page ordering guarantee" below), and — once assembled — the pre-OCR PDF.

The workspace location depends only on `--workspace-root`; it is unrelated to
where the input PDF or output directory live (`workspace.py`'s
`create_workspace`). Without `--workspace-root`, the workspace is created
under the OS temp directory (`%TEMP%`, e.g.
`C:\Users\<you>\AppData\Local\Temp\sc-<stem>-<random>\`) regardless of
whether the input or output paths are inside a cloud-synced folder (OneDrive,
Google Drive, Dropbox) — so the hundreds of intermediate PNGs/TIFFs never get
written into a folder a sync client is watching, even with no flag at all.

Successful workspaces are deleted after the final OCR PDF has been written.
Failed or incomplete workspaces are always retained, so their contents can be
inspected to diagnose what went wrong. During development, pass
`--keep-workspace` to retain a successful workspace for inspection too.

### Page ordering guarantee

The package never trusts filesystem iteration (e.g. directory listing order)
to determine page order, since that isn't guaranteed to match the original
PDF's page order across filesystems. Instead, the extraction step records the
authoritative order in `workspace.json`, and the final TIFFs are assembled
only after a complete one-to-one filename validation against that record.

### Development

Contributing requires a local checkout, unlike the `uv tool install` route
end users take:

```powershell
git clone https://github.com/heidiwallace/scan-cleanup-windows.git
cd scan-cleanup-windows
uv sync
```

Before opening a pull request, run the same checks the CI workflow runs:

```powershell
uv run pytest
uv run ruff check .
uv build
```

GitHub Actions runs these checks (lint, test, package build) on both
`ubuntu-latest` and `windows-latest`. A separate `ocr-smoke-windows` job
installs Tesseract and Ghostscript on the Windows runner and runs
`uv run pytest -m ocr_smoke`, the one test that exercises the real OCR
pipeline end to end (it is skipped in the normal run on any machine where
those programs are absent).

### Relationship to the macOS package

This is a fork of the macOS `scan-cleanup` package, forked at
`/Users/heidiwallace/dev/scan-cleanup`, and is published as a separate
distribution (`scan-cleanup-windows`) so both can be installed or published
independently. The import package name (`scan_cleanup`) and the console
command (`scan-cleanup`) are kept identical to the macOS package so fixes
port cleanly between the two codebases. The macOS package is never edited
from here, and this package should not have macOS-specific code re-added to
it.

See `WINDOWS_PORT.md` for the full list of Windows-specific changes and the
verification steps still outstanding (`V1`, `V2`), and `CLAUDE.md` for the
current state of that verification work.
