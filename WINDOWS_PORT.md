# Windows port plan

What has to change to make `scan-cleanup` run on Windows. The existing macOS
package at `/Users/heidiwallace/dev/scan-cleanup` is **not** modified. The Windows
version is built in `/Users/heidiwallace/dev/scan-cleanup-windows`.

Each item below has four parts:

- **Issue** — what's wrong, in plain terms.
- **Current Mac implementation** — what the code does today (with file references).
- **Proposed change for Windows version** — what it should do instead.
- **Instructions to Claude** — concrete steps when building the new package.

Terms used: **PATH** = the operating system's list of folders it searches for
programs; **wheel** = a prebuilt package file that `pip`/`uv` downloads;
**entry point / console script** = the `scan-cleanup` command that gets created
when the package is installed; **drive / volume** = `C:`, `D:`, a USB stick, a
network share — Windows treats each as separate, macOS usually has one;
**CRLF / LF** = Windows ends text lines with two invisible characters, Mac/Linux
with one; **CI runner** = the throwaway machine GitHub uses to test the code.

---

## Step 0 — Create the new package from the current one

**Issue.** The new folder is empty. Work should start from an exact copy of the
current package's tracked files (no virtual environment, no archived snapshots,
no local scan data), as its own fresh Git repository.

**Current Mac implementation.** The macOS package is a Git repo with 23 tracked
files. `.venv/`, `.snapshots/`, `development-workspaces/`, `tests/data/`, `dist/`,
and caches are all git-ignored and must not be carried over.

**Proposed change for Windows version.** Populate
`/Users/heidiwallace/dev/scan-cleanup-windows` with only the tracked files, then
initialise a brand-new Git history there.

**Instructions to Claude.**
1. From `/Users/heidiwallace/dev/scan-cleanup`, export the tracked files into the
   new folder: `git archive HEAD | tar -x -C /Users/heidiwallace/dev/scan-cleanup-windows`
   (this includes only committed content — the ignored junk is automatically left
   behind). Keep this `WINDOWS_PORT.md` in place.
2. In the new folder: `git init`, then an initial commit of the unmodified copy so
   every later change is reviewable as a diff.
3. Keep the copied `uv.lock`. It is platform-independent (uv resolves
   dependencies for all operating systems at once), so it does not need to be
   regenerated — but on a Windows machine run `uv lock --check` to confirm it is
   still valid, then `uv sync`.
4. Do **not** copy `.venv/`. It contains hard-coded macOS paths; `uv sync`
   rebuilds it fresh.
5. Apply the changes below roughly in the order given (blocking items first, then
   robustness, then packaging/CI, then docs).

---

## Development approach — no Windows machine required

The person doing this port does not have a Windows computer. That is fine.

**Building and publishing do not need Windows.** This package contains no
compiled code of its own — `uv build` produces a plain "pure Python" wheel (the
installable package file), and every dependency provides its own prebuilt Windows
wheels. `uv build` and publishing run identically from macOS. The only thing a
Windows machine provides is *verification*, and most of that can be automated.

### 1. Write all the code on macOS

Items B1–B4 and R1–R4 are ordinary Python edits. Nothing about writing them
requires Windows.

### 2. Use GitHub Actions `windows-latest` as the test loop

Switch CI to a `[ubuntu-latest, windows-latest]` matrix now (item P2) and push a
branch. Every push then reports whether Python behaves differently on Windows.
This covers more than it first appears:

- The Windows-only code branches — B1 (Ghostscript command names), B2 (standard
  install-path discovery), B3 (cross-drive move), R2 (path length) — are all
  testable by faking the environment with pytest's `monkeypatch`. Those tests run
  on the real Windows runner and need no ScanTailor, Tesseract, or Ghostscript.
- B4 (non-English characters in paths) runs for real on the Windows runner:
  create a `tmp_path` with an accented folder name and do one
  extract-then-read cycle.
- Add a Windows CI job that installs the real helper programs
  (`choco install ghostscript tesseract`, or the `winget` equivalents) and runs
  one real OCR pass on a tiny sample PDF. That discharges V2 (ocrmypdf's
  best-effort Windows support) automatically, on every push.

### 3. Add a fake ScanTailor executable as a test fixture

ScanTailor Advanced is a GUI application with no batch/command-line mode, so even
a Windows development machine could not fully automate the interactive step. The
solution is a small stub program used only in tests: a short script that reads
the generated project file, copies the input PNGs into the `out/` folder as
TIFFs at the expected DPI, and exits with status 0. Point the pipeline at it via
`--scantailor`. The entire flow — extract → "ScanTailor" → assemble → OCR — then
runs end to end in Windows CI without a real GUI. This is the single most useful
piece of test infrastructure for the port.

### 4. One manual acceptance pass

The only thing CI cannot exercise is the real ScanTailor Advanced GUI being
launched by `subprocess.run`, edited by a person, closed, and the Python process
resuming afterwards. Do this once, by hand. Options, cheapest first:

- **A free virtual machine on the Mac.** VMware Fusion is now free for personal
  use and runs Windows 11 (ARM edition) on Apple Silicon Macs; x64 applications
  such as ScanTailor Advanced, Tesseract, and Ghostscript run under Windows'
  built-in emulation. UTM (also free) is a fallback. On an Intel Mac, VMware
  Fusion, VirtualBox, or Parallels with ordinary 64-bit Windows all work.
- **A Windows-using colleague or one of the intended end users.** Give them a
  pre-release wheel and a short written test script. These users are the reason
  the Windows version exists, so this acceptance step is worth doing regardless
  of the other options.
- **A short-lived cloud Windows instance** (AWS EC2 or Azure) over Remote
  Desktop, roughly USD 0.10–0.20 per hour, deleted when finished.

### 5. Release as a pre-release first

Publish as a pre-release version (for example `0.3.0rc1`), have a real Windows
user run it once end to end, then tag the final release.

### Note on V1

A Windows 10/11 build of ScanTailor Advanced has been identified (see V1 for the
link and caveats). What remains is a hands-on check that it opens a
`.ScanTailor` project passed as its first command-line argument, plus confirming
where it installs (for B2) and its provenance before the README points users at
it. None of that blocks starting the code changes.

---

## Blocking issues (the package will not work correctly on Windows without these)

### B1 — Ghostscript has a different command name on Windows

**Issue.** Before running the OCR step, the package checks that its two required
helper programs — Tesseract (the text-recognition engine) and Ghostscript (a PDF
processor) — are installed, by looking for their command names on the PATH. It
looks for Ghostscript under the name `gs`. On Windows there is no `gs`; the
command is `gswin64c` (64-bit) or `gswin32c` (32-bit). So on every Windows
machine this check wrongly concludes Ghostscript is missing and refuses to run.

**Current Mac implementation.** `src/scan_cleanup/ocr.py`:
`_REQUIRED_BINARIES = {"tesseract": "...", "gs": "..."}`, and
`check_system_dependencies()` does
`missing = [name for name in _REQUIRED_BINARIES if shutil.which(name) is None]`,
raising `MissingSystemDependencyError` if the list is non-empty.

**Proposed change for Windows version.** Treat Ghostscript as present if **any**
of `gswin64c`, `gswin32c`, or `gs` is found. Leave Tesseract as-is — the Windows
command really is `tesseract`, and `shutil.which` finds `tesseract.exe`
automatically.

**Instructions to Claude.**
- Change `_REQUIRED_BINARIES` so each entry maps a human-readable label to a
  tuple of acceptable command names, e.g.
  `"ghostscript": ("Ghostscript, used to process the PDF", ("gswin64c", "gswin32c", "gs"))`
  and `"tesseract": ("the OCR engine", ("tesseract",))`.
- Rewrite `check_system_dependencies()` to mark a program missing only when
  **none** of its candidate names resolve. Keep the error message naming the
  missing program(s) clearly.
- Replace the Homebrew-only `_INSTALL_INSTRUCTIONS` text (see D1).
- Add a unit test that fakes "only `gswin64c` is installed" (monkeypatch
  `shutil.which`) and asserts the check passes; and one that asserts a helpful
  error when neither Tesseract nor any Ghostscript name is found.

### B2 — The package cannot find ScanTailor Advanced automatically on Windows

**Issue.** The package tries several strategies to locate the `scantailor-advanced`
program. The "look in the standard install folder" strategy only has entries for
macOS. On Windows it falls back to searching the PATH only, and the ScanTailor
Advanced Windows installer does not add itself to the PATH — so a normal install
is invisible and the user must pass `--scantailor "C:\...\scantailor-advanced.exe"`
on every single run.

**Current Mac implementation.** `src/scan_cleanup/scantailor.py`,
`resolve_scantailor()` checks, in order: an explicit `--scantailor` path; the
`SCANTAILOR_ADVANCED` environment variable; `scantailor-advanced` /
`scantailor-advanced.exe` on the PATH; then, **only when `sys.platform == "darwin"`**,
a list of fixed macOS locations (`/opt/homebrew/bin/...`, `/usr/local/bin/...`,
the `.app` bundle). If nothing matches it raises `ScanTailorError` listing every
path it tried.

**Proposed change for Windows version.** Add an equivalent block for
`sys.platform == "win32"` that checks the standard Windows install locations,
built from environment variables rather than hard-coded `C:\` paths (Windows can
be installed on any drive, and "Program Files" is localised on some systems).

**Instructions to Claude.**
- In `resolve_scantailor()`, add:
  ```python
  if sys.platform == "win32":
      for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
          root = os.environ.get(var)
          if root:
              candidates.append(Path(root) / "ScanTailor Advanced" / "scantailor-advanced.exe")
  ```
- Confirm the real folder name from an actual ScanTailor Advanced Windows install
  (installer vs. portable `.zip` may differ, e.g. `STAdvanced`) and add any extra
  variants discovered.
- Windows candidates **must** end in `.exe` — the existing
  `candidate.is_file()` check fails on a name without the extension.
- Leave the `os.access(candidate, os.X_OK)` check; on Windows it effectively just
  means "the file exists", which is fine for an `.exe`.
- Update the docstring / comments that currently say discovery is macOS-only.
- Add a unit test that fakes `os.environ["ProgramFiles"]` and a file at the
  expected location and asserts `resolve_scantailor()` returns it.

### B3 — Writing the finished PDF fails when the output folder is on a different drive

**Issue.** The last step moves the finished PDF from the temporary work folder to
the user's chosen output folder using a fast "rename" operation. On Windows a
rename only works **within the same drive**. The work folder is always on `C:`
(inside the system temp area), but people routinely send output to `D:`, an
external drive, a network share, or a Google Drive / OneDrive folder. When the
output is on a different drive, the move throws an error (`WinError 17`) right at
the finish line. This does not bite on macOS because the temp area and the
destination are normally on the same disk.

**Current Mac implementation.** `src/scan_cleanup/pipeline.py`,
`finish_workspace()` ends with `ocr_pdf.replace(output_pdf)` where `ocr_pdf` is
`workspace / "ocr-output.pdf"` (in the temp work folder) and `output_pdf` is
inside the user-supplied `output_dir`. `Path.replace` is a pure rename.

**Proposed change for Windows version.** If the fast rename fails because the two
locations are on different drives, fall back to a copy-then-delete.

**Instructions to Claude.**
- Wrap the final move:
  ```python
  import errno, shutil
  try:
      os.replace(ocr_pdf, output_pdf)
  except OSError as exc:
      if getattr(exc, "winerror", None) == 17 or exc.errno == errno.EXDEV:
          output_pdf.unlink(missing_ok=True)   # shutil.move won't overwrite reliably
          shutil.move(str(ocr_pdf), str(output_pdf))
      else:
          raise
  ```
- Check whether any other spot moves a file out of the work folder into a
  user-chosen location; `finish_workspace` is the only one today, but confirm.
- Keep the existing "does the output already exist?" guard that runs earlier —
  this change is only about the mechanics of the move.
- Add a test that points the output at a path the test makes look cross-device
  (simulate by monkeypatching `os.replace` to raise `OSError(errno.EXDEV, ...)`)
  and asserts the file still ends up in the right place.

### B4 — OpenCV cannot open image files whose path contains non-English characters (Windows only)

**Issue.** The image library used for reading and writing page images (OpenCV,
imported as `cv2`) cannot handle file paths containing accented or non-Latin
characters **on Windows** — it silently returns "nothing" instead of the image,
or silently fails to write. The temp work folder path includes the Windows
account name (`C:\Users\<name>\AppData\Local\Temp\...`), so this breaks for any
user whose Windows profile name has an accent, and also if a source PDF's file
name contains such characters (archival material often does). On macOS this works
fine, so it is currently untested.

**Current Mac implementation.** Three file-path calls to OpenCV:
- `src/scan_cleanup/pdf_io.py`, `extract_pages_to_png()`:
  `cv2.imwrite(str(output_path), image)` — writes an extracted page as `.png`.
- `src/scan_cleanup/scantailor.py`, `generate_project()`:
  `cv2.imread(str(page_path), cv2.IMREAD_UNCHANGED)` — reads a page back to get
  its pixel dimensions.
- `src/scan_cleanup/scantailor.py`, `validate_output()`:
  `cv2.imread(str(path), cv2.IMREAD_UNCHANGED)` — checks each TIFF ScanTailor
  produced is readable.

(The other `cv2` calls decode image bytes already held in memory — `cv2.imdecode`
in `pdf_io.py` — and involve no file path, so they are already safe.)

**Proposed change for Windows version.** Read and write image files through
NumPy, which handles Windows Unicode paths correctly, and hand the raw bytes to
OpenCV for decoding/encoding.

**Instructions to Claude.**
- Add two small helpers (e.g. in a new `src/scan_cleanup/_imageio.py`, or in
  `pdf_io.py`):
  ```python
  def imread_unicode(path: Path, flags: int):
      data = np.fromfile(str(path), dtype=np.uint8)
      if data.size == 0:
          return None
      return cv2.imdecode(data, flags)

  def imwrite_unicode(path: Path, image) -> bool:
      ok, buf = cv2.imencode(path.suffix, image)   # e.g. ".png"
      if ok:
          buf.tofile(str(path))
      return ok
  ```
- Replace the three call sites above with these helpers.
- `imwrite_unicode` is only ever used for `.png` here; `imencode(".png", ...)`
  is always available. `imread_unicode` is used for `.png` and `.tif`; the
  bundled OpenCV (`opencv-python-headless`) includes TIFF support, so `.tif`
  decoding works.
- Keep the existing "image came back as None → raise a clear error" checks; the
  helpers preserve that contract (`None` on failure, `False` on write failure).
- Add a test that runs an extract → read cycle under a `tmp_path` containing a
  non-ASCII directory component and asserts it succeeds. (This will pass on macOS
  too; its purpose is to lock in the Windows-safe behaviour.)

---

## Robustness issues (works most of the time, fails in specific identifiable cases)

### R1 — Deleting the temporary work folder can fail on Windows

**Issue.** On success the package deletes its temporary work folder. On Windows,
folder deletion intermittently fails with a "permission denied" error when
another program still has a file open — antivirus real-time scanning, a leftover
ScanTailor process, or Windows Explorer showing a preview. The finished PDF is
already saved by this point, so a failed cleanup should be a warning, not a
crash.

**Current Mac implementation.** `src/scan_cleanup/pipeline.py`: both
`process_volume()` and `resume_workspace()` call `shutil.rmtree(workspace)`
directly when `recipe.cleanup_workspace_on_success` is true. Any error propagates
and fails the run.

**Proposed change for Windows version.** Retry the delete briefly (clearing the
Windows "read-only" attribute, which blocks deletion), and if it still fails,
log a warning telling the user where the leftover folder is instead of raising.

**Instructions to Claude.**
- Add a helper that calls `shutil.rmtree(path, onexc=handler)` (use `onerror=`
  for Python < 3.12) where `handler` does `os.chmod(p, stat.S_IWRITE)` then
  retries the operation, swallowing a final failure.
- On a final failure, `logger.warning("Could not remove work folder: %s", path)`
  and continue — the output PDF is already in place.
- Use this helper everywhere `shutil.rmtree` is currently called on the
  workspace.

### R2 — Windows' 260-character path length limit

**Issue.** By default Windows rejects file paths longer than 260 characters.
The package's temp work folders nest several levels deep
(`...\Temp\scan-cleanup-<pdf name>-<random>\out\<pdf name>-NN.tif`), and if the
user points `--workspace-root` at a folder inside a synced Google Drive / OneDrive
tree the base path is already long. Past the limit, image reads/writes fail with
confusing errors.

**Current Mac implementation.** `src/scan_cleanup/workspace.py`,
`create_workspace()` uses
`tempfile.mkdtemp(prefix=f"scan-cleanup-{input_stem}-", ...)`. macOS has no
practical path-length limit, so this is not a concern there. The README already
recommends `--workspace-root` for a stable, local, non-synced path.

**Proposed change for Windows version.** Reduce the default path length and
document the limit; optionally detect and warn.

**Instructions to Claude.**
- Shorten the default prefix on Windows (e.g. `sc-{input_stem}-` instead of
  `scan-cleanup-{input_stem}-`).
- In the Windows README section, recommend `--workspace-root C:\sc` (a short,
  local, non-synced folder) as the normal way to run, and explain the 260-char
  limit and the option to enable "Win32 long paths" via Group Policy / the
  `LongPathsEnabled` registry value.
- Optionally: if the computed workspace path length is already within ~40
  characters of 260, log a warning up front.

### R3 — No line-ending policy; Git may rewrite files on Windows checkout  *[added in 2nd pass]*

**Issue.** Windows tools traditionally end each line of a text file with two
invisible characters (CRLF); macOS/Linux use one (LF). Git on Windows is often
configured to convert LF to CRLF automatically when files are checked out. There
is no `.gitattributes` file to prevent this, so on a Windows clone the Python
source, the `.gitignore`, and — most importantly — the bundled ScanTailor project
template could be silently rewritten with CRLF endings. Python and the tests
tolerate CRLF, but a rewritten template is a needless source of "works on my
machine" differences and could confuse a byte-for-byte comparison later.

**Current Mac implementation.** No `.gitattributes` file exists. All files are
LF. macOS Git does no conversion, so the omission is invisible today.

**Proposed change for Windows version.** Add a `.gitattributes` that pins line
endings so a checkout is identical on every OS.

**Instructions to Claude.**
- Create `.gitattributes` at the repo root:
  ```
  * text=auto eol=lf
  *.scantailor text eol=lf
  *.png binary
  *.pdf binary
  *.tif binary
  *.tiff binary
  *.tar.gz binary
  ```
- Verify the bundled template
  `src/scan_cleanup/templates/scantailor-advanced-default.scantailor` is treated
  as LF text (ScanTailor Advanced writes and reads LF).

### R4 — Minor filesystem and console hardening  *[added in 2nd pass]*

**Issue.** Three small Windows-specific rough edges:
1. **Output filename casing.** Validation compares ScanTailor's output TIFF names
   to the expected names using an exact, case-sensitive string match. If a
   Windows ScanTailor build ever writes `PAGE-01.TIF` instead of `page-01.tif`,
   the package would report the page as both "missing" and "unexpected".
2. **Console text encoding.** When the command's output is redirected to a file
   or piped, Windows defaults to a legacy text encoding; printing an error
   message that contains an accented file path can then throw a secondary
   `UnicodeEncodeError` that masks the real error.
3. **Illegal characters in the temp folder name.** The temp folder name is built
   from the input PDF's file name. Windows forbids `< > : " | ? *` in names; a
   PDF whose name contains one (possible if it came from another OS) would make
   folder creation fail with an unclear error.

**Current Mac implementation.**
1. `src/scan_cleanup/scantailor.py`, `validate_output()` builds
   `actual = {path.name: path ...}` and compares against `set(expected_names)`
   with exact strings. It already lowercases *extensions* when scanning
   (`path.suffix.lower() in {".tif", ".tiff"}`) but not the full name.
2. `src/scan_cleanup/cli.py`, `main()` prints errors with
   `print(f"\nError: {exc}\n", file=sys.stderr)`.
3. `src/scan_cleanup/workspace.py`, `create_workspace()` passes
   `input_stem` straight into `tempfile.mkdtemp(prefix=...)`.

**Proposed change for Windows version.**
1. Match output filenames case-insensitively.
2. Make stdout/stderr tolerant of characters they can't encode.
3. Sanitise the folder-name prefix.

**Instructions to Claude.**
- In `validate_output()`, build the `actual` map with lower-cased keys and
  compare against lower-cased `expected_names` (keep the original names for the
  returned paths and for error messages).
- Early in `cli.py`'s `main()`, reconfigure the streams:
  `sys.stdout.reconfigure(errors="backslashreplace")` and the same for
  `sys.stderr` (guard with `hasattr(sys.stdout, "reconfigure")`).
- In `create_workspace()`, strip characters not in a safe set
  (`A–Z a–z 0–9 . _ -`) from `input_stem` before using it as the prefix; fall
  back to `"volume"` if nothing is left.
- Add small unit tests for each (case-mismatched TIFF name accepted; prefix with
  `:` sanitised).

---

## Packaging and continuous-integration changes

### P1 — Package metadata still says "any operating system"

**Issue.** The package description advertises itself as OS-independent and, if
published, would clash on the package index with the macOS package under the same
name. Someone needs to decide whether the Windows version is a separate
distribution or the same one, and the "supported OS" label should be accurate.

**Current Mac implementation.** `pyproject.toml`: `name = "scan-cleanup"`,
`classifiers = [... "Operating System :: OS Independent" ...]`.

**Proposed change for Windows version.** Decide the name; set an accurate OS
classifier.

**Instructions to Claude.**
- **Decision needed from Heidi:** keep `name = "scan-cleanup"` (the Windows
  version simply *replaces* the Mac one for Windows users, never published side by
  side) **or** use a distinct name such as `scan-cleanup-windows` (both can be
  installed / published independently). Default recommendation: keep
  `scan-cleanup` unless both will be on PyPI at once.
- Change the classifier to `"Operating System :: Microsoft :: Windows"` (or list
  both Windows and POSIX explicitly if the intent is one codebase for both).
- No dependency version changes are required — all six runtime dependencies
  (`pymupdf`, `opencv-python-headless`, `numpy`, `img2pdf`, `ocrmypdf`,
  `pillow`) and `ocrmypdf`'s own sub-dependency `pikepdf` publish ready-made
  Windows packages for Python 3.12. Keep `opencv-python-headless` (not the
  full `opencv-python`) — it avoids pulling in extra display libraries.
- Update `[project.description]` wording if it mentions macOS.

### P2 — Automated tests only run on Linux

**Issue.** The project's automated checks (lint, tests, package build) run only
on a Linux machine. Nothing verifies the code works on Windows, which is the
whole point of this version.

**Current Mac implementation.** `.github/workflows/ci.yml`:
`runs-on: ubuntu-latest`, then install `uv`, `uv sync`, `uv run ruff check .`,
`uv run pytest`, `uv build`.

**Proposed change for Windows version.** Run the same checks on Windows (either
switch the runner, or test both Linux and Windows in a matrix).

**Instructions to Claude.**
- Change `runs-on:` to `windows-latest`, or use
  `strategy: matrix: os: [ubuntu-latest, windows-latest]` with
  `runs-on: ${{ matrix.os }}`.
- The `astral-sh/setup-uv` action and every `uv ...` command work unchanged on
  the Windows runner.
- The test suite needs **no changes** to pass on Windows (see "Verified
  non-issues"), because no test launches ScanTailor, Tesseract, or Ghostscript.
- If an end-to-end OCR smoke test is added later, install the helpers on the
  runner first (`choco install ghostscript tesseract` or the `winget`
  equivalents) and skip the test when they are absent
  (`@pytest.mark.skipif(shutil.which(...) is None, ...)`).

### P3 — Tell Windows users how to get Python

**Issue.** The repo pins Python 3.12 but assumes it is already installed. Many
Windows machines have no Python at all.

**Current Mac implementation.** `.python-version` contains `3.12`; the README
assumes `python`/`uv` exist.

**Proposed change for Windows version.** Keep the pin; document that `uv` can
install Python itself.

**Instructions to Claude.**
- Keep `.python-version` as `3.12`.
- In the README, add: install `uv` first, then `uv python install 3.12` if
  needed; `uv sync` and `uv run` handle the rest.

### P4 — `.gitignore` and lockfile housekeeping

**Issue.** The ignore list has macOS clutter entries but not the Windows
equivalents, and the lockfile carried over from macOS should be sanity-checked on
Windows.

**Current Mac implementation.** `.gitignore` ignores `.DS_Store` (macOS) plus the
usual Python/build/dev entries. `uv.lock` is committed and was generated on
macOS.

**Proposed change for Windows version.** Add Windows clutter entries; verify the
lockfile on Windows.

**Instructions to Claude.**
- Append to `.gitignore`: `Thumbs.db`, `ehthumbs.db`, `desktop.ini`,
  `$RECYCLE.BIN/`. Leave the `.DS_Store` line (harmless, and useful if anyone
  works on this from a Mac).
- Run `uv lock --check` on a Windows machine to confirm `uv.lock` still resolves;
  only regenerate if it complains.

---

## Documentation changes

### D1 — Installation instructions are macOS/Homebrew only

**Issue.** Every setup instruction — for ScanTailor Advanced, Tesseract,
Ghostscript, and the Python environment — is written for macOS with Homebrew.
None of it applies on Windows.

**Current Mac implementation.** `README.md` sections "Installing ScanTailor
Advanced (macOS)" (a from-source CMake build into the Homebrew prefix) and
"Installation" (`brew install tesseract ghostscript`). `ocr.py`'s
`_INSTALL_INSTRUCTIONS` string is likewise Homebrew-only.

**Proposed change for Windows version.** Rewrite these for the Windows toolchain.

**Instructions to Claude.**
- **ScanTailor Advanced:** a Windows 10/11 build has been identified (see V1 for
  the link and the provenance checks to do first). No build-from-source step is
  needed on Windows (unlike macOS). Document the download location that survives
  the V1 review (an official source if one is found, otherwise the vetted share),
  the exact version, and — if it is a portable `.zip` with no installer — where
  the user should place it. State that item B2 auto-detects a standard install;
  otherwise the user passes
  `--scantailor "C:\Path\To\scantailor-advanced.exe"` or sets the
  `SCANTAILOR_ADVANCED` environment variable. Warn that Windows SmartScreen /
  antivirus will likely flag the binary on first launch and explain how to
  proceed.
- **Tesseract:** the UB Mannheim installer; **tick "Add to PATH"** during setup
  (or add `C:\Program Files\Tesseract-OCR` to PATH by hand). English language
  data is included by default, which matches the package's `language="eng"`
  setting. Alternative: `winget install UB-Mannheim.TesseractOCR`.
- **Ghostscript:** the official 64-bit installer from ghostscript.com; its `bin\`
  folder (containing `gswin64c.exe`) must be on PATH. Alternative:
  `winget install ArtifexSoftware.GhostScript`. Any reasonably recent version is
  fine.
- **uv:** `winget install astral-sh.uv` or the PowerShell bootstrap from
  astral.sh/uv.
- Convert the command examples to PowerShell: backslash paths, wrap paths
  containing spaces in quotes, and either join the multi-line `\` examples onto
  one line or use PowerShell's backtick continuation.
- Keep the existing guidance about keeping work folders out of synced
  (Google Drive / OneDrive) locations, and add the 260-character path note from
  R2.
- Rewrite `ocr.py`'s `_INSTALL_INSTRUCTIONS` to give the Tesseract and
  Ghostscript install steps above instead of the Homebrew ones.

### D2 — Project-memory notes reference macOS-only behaviour

**Issue.** `CLAUDE.md` describes the executable-discovery logic as macOS-only and
lists cross-platform support as a deferred task. After this port those notes are
stale.

**Current Mac implementation.** `CLAUDE.md`, "ScanTailor executable" section and
the line "Cross-platform automatic discovery and installation (Linux, Windows) is
the final deferred task".

**Proposed change for Windows version.** Update the notes to describe the Windows
discovery path and the Windows-specific behaviours added here.

**Instructions to Claude.**
- Rewrite the "ScanTailor executable" section to include the Windows standard
  install locations (B2).
- Note the Windows-specific handling added: Ghostscript command names (B1),
  cross-drive move fallback (B3), Unicode-safe image I/O (B4), resilient
  work-folder cleanup (R1).
- Remove or rescope the "deferred task" line.
- Note: `CLAUDE.md` is currently listed in `.gitignore` but is also already
  committed, so edits to it are tracked — leave that arrangement as-is.

---

## Verify before starting (project-level risks) *[added in 2nd pass]*

### V1 — Confirm a usable Windows build of ScanTailor Advanced exists

**Status: a Windows build exists.** Heidi has identified a ScanTailor Advanced
build reported to run on Windows 10 and 11, shared here:
`https://www.terabox.com/sharing/link?surl=ZlDnuOMokDp747Sehnhk9A`

**Issue / what still needs checking.** The workflow depends on a
`scantailor-advanced.exe` that (a) runs on Windows 10/11 — apparently satisfied —
and (b) accepts a `.ScanTailor` project file as its first command-line argument
and opens it, the same way the macOS build does. That second property is **not
yet confirmed** and must be tested by hand on Windows.

Provenance also needs attention: the link above is a TeraBox file share, not the
official `ScanTailor-Advanced/scantailor-advanced` GitHub releases page. Before
the package documentation points end users at a download:

- Prefer an official or otherwise verifiable source if one exists for a
  comparable version (check the upstream GitHub releases first).
- If this share is the source used, record which exact version/build it is, note
  where it came from, run it through a malware scan, and — if the uploader
  provides one — verify a checksum. Capture all of this in `CLAUDE.md`.
- Expect Windows SmartScreen / antivirus to flag a binary from a file share on
  first launch; the README should tell users this is expected and how to proceed.

**Instructions to Claude.**
- Do not download or fetch the linked file from this environment. It is for a
  human to retrieve and test on a real Windows machine (or VM).
- On Windows, verify by hand that
  `scantailor-advanced.exe "some\project.ScanTailor"` launches and opens that
  project (this is the assumption the whole pipeline rests on — see
  `launch_scantailor()` in `scantailor.py`).
- Identify the version string and confirm B2's standard install-path discovery
  matches where this build actually installs (or note that it is a portable
  `.zip` with no fixed install location, in which case users must pass
  `--scantailor` or set `SCANTAILOR_ADVANCED`).
- Record the chosen build, its origin, and the verification result in
  `CLAUDE.md`.

### V2 — Confirm ocrmypdf runs end to end on Windows

**Issue.** The OCR step is performed by the `ocrmypdf` library. Its Windows
support is officially "best effort" / not covered by its own automated testing.
It shells out to Tesseract and Ghostscript and coordinates multiple worker
processes, which is the area most likely to misbehave on Windows.

**Current Mac implementation.** `src/scan_cleanup/ocr.py`, `add_ocr_layer()`
calls `ocrmypdf.ocr(pdf_path, output_path, language=..., output_type="pdf",
deskew=False, clean=False, remove_background=False)`. With these settings it
needs only Tesseract and Ghostscript (no `unpaper`, no `jbig2enc`).

**Instructions to Claude.** Early in the port, run one real
`scan-cleanup process` on a short sample PDF on an actual Windows machine and
confirm the OCR step completes. If it fails or hangs, try `ocrmypdf`'s
single-process mode (pass `jobs=1` to `ocrmypdf.ocr`) and/or pin a known-good
`ocrmypdf` version. Capture the outcome in `CLAUDE.md`.

---

## Verified non-issues (already cross-platform — do not change)

- **Launching ScanTailor and waiting for it to close.**
  `subprocess.run([str(exe), str(project)], check=False)` in `scantailor.py`
  behaves identically on Windows: it starts the GUI and blocks until the user
  quits it. No shell, no quoting problems (the list form handles paths with
  spaces).
- **The `scan-cleanup` command.** `[project.scripts]` in `pyproject.toml`
  produces a working `scan-cleanup.exe` on Windows automatically.
- **Temp folder location.** `tempfile.mkdtemp` resolves to the Windows temp area
  correctly (path *content* caveats are covered by B4 and R2).
- **Paths written into the ScanTailor project file.** `Path.resolve()` produces
  `C:\...\` backslash paths, which is exactly what the Windows ScanTailor build
  expects.
- **Writing the project XML.** `xml.etree.ElementTree.write(..., encoding="utf-8")`
  in `scantailor.py` uses LF line endings; ScanTailor on Windows reads that
  fine.
- **Loading the bundled template.**
  `importlib.resources.files("scan_cleanup").joinpath("templates/...")` works for
  a normal (unzipped) install, which is what `uv sync` and `uv build` produce.
- **PDF and image reads via PyMuPDF and Pillow.** `pymupdf.open`,
  `pixmap.save`, and `PIL.Image.open` all handle Windows Unicode paths correctly
  — only the OpenCV calls (B4) do not.
- **Environment variables and the home directory.**
  `os.environ["SCANTAILOR_ADVANCED"]` and `Path.home()` are cross-platform.
- **The test suite.** Every test uses pytest's `tmp_path` and synthetic images
  from `tests/conftest.py`; none launches ScanTailor, Tesseract, or Ghostscript.
  `tests/test_workspace.py` line 14's
  `scantailor_executable="/bin/scantailor-advanced"` is only a string stored in
  and read back from a manifest — it is never executed or checked as a path.
  Expect the suite to pass on `windows-latest` with zero test changes.

---

## Suggested order of work

1. Step 0 — copy the package, `git init`, first commit.
2. V1, V2 — confirm the external pieces (ScanTailor Windows build, ocrmypdf on
   Windows) actually work; these can invalidate the plan.
3. B1 → B2 → B3 → B4 — the blocking code fixes.
4. R1, R2, R3, R4 — robustness.
5. P2 — switch CI to Windows; this proves steps 3–4 on a real Windows machine.
6. P1, P3, P4 — packaging metadata and housekeeping.
7. D1, D2 — documentation.
