## Download and Install the Desktop App

Beckit is distributed as a prebuilt installer — no Python or developer tools required. Download the version for your platform from the [latest release](../../releases/latest). This app was built with the help of Claude.

### macOS

**Requirements:** macOS 11 (Big Sur) or later

1. Go to the [latest release](../../releases/latest) and download `Beckit-macOS-<version>.dmg`
2. Open the downloaded `.dmg` file
3. In the window that appears, drag **Beckit** into your **Applications** folder
4. Eject the disk image (drag it to Trash or right-click → Eject)
5. Open **Launchpad** or your **Applications** folder and launch **Beckit**

> **"App can't be opened because it is from an unidentified developer"**
> This appears because the app is not yet signed with an Apple Developer certificate.
> To open it anyway: right-click (or Control-click) the app icon → click **Open** → click **Open** again in the dialog. You only need to do this once.

---

### Windows

**Requirements:** Windows 10 or later (64-bit)

1. Go to the [latest release](../../releases/latest) and download `Beckit-Windows-<version>.zip`
2. Right-click the zip file and select **Extract All…** — choose a permanent location (e.g. `C:\Program Files\Beckit` or a folder on your Desktop)
3. Open the extracted folder and double-click **Beckit.exe** to launch the app

> **Windows Defender SmartScreen warning ("Windows protected your PC")**
> This appears because the app is not yet code-signed. Click **More info** → **Run anyway** to proceed.

> **Tip:** Right-click `Beckit.exe` → **Send to** → **Desktop (create shortcut)** for easier access.

---

## First Launch

Regardless of platform, the first time you open Beckit you will be asked to connect your GitHub account:

1. [Create a GitHub Personal Access Token](https://github.com/settings/tokens/new) with the **`repo`** scope (classic token)
2. Paste it into the sign-in prompt and press **Connect**
3. Select an existing repository to use as your book, or create a new one — Beckit will clone it locally and set up the `Chapters/` structure automatically

Your token and repository settings are stored in your system's app config directory:

| Platform | Config location |
|---|---|
| macOS | `~/Library/Application Support/beckit/` |
| Windows | `%APPDATA%\beckit\` |

---

## Optional: PDF Generation

The **Generate PDF** button and the release workflow both require **Pandoc** and a LaTeX engine to be installed on your machine separately — they are not bundled with the app.

### macOS

```bash
brew install pandoc mactex-no-gui
```

Or download the installers manually:
- [Pandoc](https://pandoc.org/installing.html)
- [MacTeX](https://tug.org/mactex/) (full) or [BasicTeX](https://tug.org/mactex/morepackages.html) (smaller)

### Windows

```powershell
winget install JohnMacFarlane.Pandoc
winget install MiKTeX.MiKTeX
```

Or download manually:
- [Pandoc for Windows](https://pandoc.org/installing.html)
- [MiKTeX](https://miktex.org/download) (recommended LaTeX distribution for Windows)

After installing, restart Beckit and the PDF button will be fully functional.

---

## Run from Source (Developers)

If you'd prefer to run directly from source, or want to contribute to the project:

```bash
git clone https://github.com/kicka5h/book-editor-template.git
cd book-editor-template

python3 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -e .
python -m book_editor     # or: beckit
```

To install dev dependencies and run tests:

```bash
pip install -e ".[dev]"
pytest
```

---

## Project Layout

```
book-editor-template/
├── .gitignore
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── book_editor/
│       ├── __init__.py
│       ├── __main__.py    # GUI entry (python -m book_editor)
│       ├── app.py         # Flet desktop UI
│       ├── config/        # App config (repo path, token)
│       ├── services/      # Chapter versioning, create, increment, word count, format, git
│       └── utils/         # Paths, chapter number helpers
├── tests/
│   ├── api/
│   ├── services/
│   ├── repositories/
│   └── utils/
└── .github/workflows/     # CI, CD, PDF generation, major release
```

---

## Book Directory Structure

Chapters live under `Chapters/` with semantic versioning per chapter:

```
Chapters/
  Chapter 1/
    v1.0.0/
      v1.0.0.md
    v1.1.0/
      v1.1.0.md
  Chapter 2/
    v1.0.0/
      v1.0.0.md
```

Each chapter can have multiple version folders (`vMAJOR.MINOR.PATCH`). All tools use the **latest** version when reporting word counts, generating PDFs, or listing chapters.

---

## CLI Tools

After `pip install -e .`, these commands are available (run from a directory containing your `Chapters/` folder):

| Command | Description |
|---|---|
| `chapter-version list` | List chapters and their current versions |
| `chapter-version minor -c 5` | Bump minor version for chapter 5 |
| `chapter-version patch -c 1 2 3` | Bump patch version for chapters 1–3 |
| `chapter-version major --all` | Bump major version for all chapters |
| `create-chapter` | Create the next chapter (e.g. Chapter 11) at v1.0.0 |
| `increment-chapters 6` | Renumber: Chapter 7→8, 8→9, … (use `-y` to skip confirm) |
| `count-chapter-words` | Word count for the latest version of each chapter |
| `format-markdown -r -i .` | Format markdown in place |

Use `-d /path/to/Chapters` to point any tool at a specific directory.

---

## License

[MIT](LICENSE)
