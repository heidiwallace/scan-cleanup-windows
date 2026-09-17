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
scanned page. Download the installer from its developer's official GitHub
page:

- 64-bit (use this on a normal modern PC):
  <https://github.com/4lex4/scantailor-advanced/releases/download/v1.0.16/scantailor-advanced-1.0.16-win64.exe>
- 32-bit (only if you know you're on a 32-bit Windows install):
  <https://github.com/4lex4/scantailor-advanced/releases/download/v1.0.16/scantailor-advanced-1.0.16-win32.exe>

Run the downloaded installer once it finishes downloading.

> **A security warning is normal.** The first time you launch a freshly
> downloaded ScanTailor Advanced, Windows may show a blue "Windows protected
> your PC" box (SmartScreen), or your antivirus may flag it. This happens
> because the program isn't digitally signed by a large company, not because
> anything is wrong. If you trust where you got it from, click **More info**,
> then **Run anyway**.

### Step 3: Install the other required programs

`scan-cleanup` also needs two more small programs: one that reads text out of
scanned pages (Tesseract), and one that helps assemble the final PDF
(Ghostscript).

Install Tesseract with:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Install Ghostscript by hand:

1. Go to <https://ghostscript.com/releases/gsdnld.html> and download the
   64-bit Windows release (look for a filename like
   `gs10.xx.x-x64-installer.exe`).
2. Run the downloaded installer, accepting the defaults. In particular, the installed program location should be in `C:\Program Files\`.


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

If you see a warning like `... is not on your PATH`, run this once (it's a
one-time fix — you won't need to repeat it after future installs):

```powershell
uv tool update-shell
```

That's it — `scan-cleanup` is now installed.



**Close this PowerShell window and open a new one** afterward, so the
`scan-cleanup` command is recognized. To check that it worked, run:

```powershell
scan-cleanup --help
```

It should print usage instructions. If it returns a message like "not recognized," please contact me for troubleshooting.

## Using scan-cleanup

In the commands below, replace anything in ALL CAPS with your own file or
folder path — for example, `INPUT.pdf` becomes the actual path to your PDF,
and `OUTPUT_DIRECTORY` becomes the folder you want the result saved in. The
easiest way to get a path right is to type the command (i.e., `scan-cleanup process`), then
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
> cause confusing errors, and the more nested or synced your folders are,
> the more likely you are to hit it. If you run into strange
> file-not-found errors partway through, this is the first thing to check:
> add `--workspace-root C:\sc` to your command to use a short, local folder
> instead of the default location.

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
