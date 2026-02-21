# book-editor-template

A template project for writing a book using GitHub as source control. This repository includes tools to manage chapter versions, count words, format markdown, and add or renumber chapters, plus an optional desktop app.

## Project layout

```text
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
└── .github/workflows/     # e.g. generate PDF, create release
```

## Install and run

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .          # editable install
.venv/bin/python -m book_editor     # or: book-editor
```

On Windows: `.venv\Scripts\pip install -e .` then `.venv\Scripts\python -m book_editor` or `book-editor`.

Optional dev deps (tests): `pip install -e ".[dev]"` then `pytest`.

## Book Editor desktop app

A lightweight, cross-platform Python desktop app: sign in to GitHub, select or create a repository for your book, then write in the editor. All configuration (GitHub connection, selected repo, local clone path) is stored in **app config on your machine** (e.g. `~/Library/Application Support/book-editor` on macOS, `~/.config/book-editor` on Linux).

- **Launch**: If no GitHub account is connected, you’re prompted to sign in (Personal Access Token with `repo` scope). Then you choose an existing repository or create a new one; the app clones it locally and ensures a `Chapters/` structure (with a starter chapter if the repo is empty).
- **Editor**: Chapter list (latest version per chapter), markdown editor, and toolbar: **New chapter**, **Bump version** (minor/patch/major), **Increment chapters**, **Word count**, **Format**, **Generate PDF**, **Save**.
- **Save**: Writes the current chapter, then `git add` / `git commit` / `git push` so your GitHub Actions workflows (e.g. generate PDF, create release) can run.
- **Generate PDF**: Builds a single PDF from the latest version of each chapter (same logic as the `generate_book_pdf` workflow), using **pandoc** and a LaTeX engine (e.g. pdflatex). Install pandoc and LaTeX on your system to use this.

Use the **Settings** (gear) button to switch repository or sign in again.

## CLI tools

When the package is installed, these commands are available (run from a directory that contains or is your book repo with `Chapters/`):

| Command | Description |
|--------|-------------|
| `chapter-version list` | List chapters and current versions |
| `chapter-version minor -c 5` | Bump minor for chapter 5 |
| `chapter-version patch -c 1 2 3` | Bump patch for chapters 1–3 |
| `chapter-version major --all` | Bump major for all chapters |
| `create-chapter` | Create next chapter (e.g. Chapter 11) with v1.0.0 |
| `increment-chapters 6` | Renumber: Chapter 7→8, 8→9, … (use `-y` to skip confirm) |
| `count-chapter-words` | Word count for latest version of each chapter |
| `format-markdown -r -i .` | Format markdown in place (e.g. blank lines between paragraphs) |

Use `-d /path/to/Chapters` (or the appropriate flag per tool) to point at a specific book directory.

---

## Directory structure (book content)

Chapters live under `Chapters/` with semantic versioning per chapter:

```text
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

Each chapter can have multiple version folders (`vMAJOR.MINOR.PATCH`). The tools use the **latest** version when reporting word counts or listing chapters.

---

## Tools (CLI)

After `pip install -e .`, the tools are available as commands (see table above). Details:

### 1. Chapter versioning — `chapter-version`

Manages semantic versioning for chapters so older versions stay in the repo.

- **`minor`** — typical bump when revising (e.g. `v1.0.0` → `v1.1.0`).
- **`patch`** — small fixes (e.g. `v1.1.0` → `v1.1.1`).
- **`major`** — large changes (e.g. `v1.1.0` → `v2.0.0`).

Bumping creates a new version folder and **copies** the markdown file from the current latest version.

**Options:** `-c N` (chapter number(s)), `--all`, `-d DIR` (Chapters directory, default: `Chapters`).

---

### 2. Word count — `count-chapter-words`

Counts words in the **latest** version of each chapter. Strips code blocks, links, and markdown for prose-only count. Options: `chapters_dir` (default `./Chapters`), `--total-only`, `-v` / `--verbose`, `--csv`.

### 3. Markdown formatting — `format-markdown`

Blank lines between paragraphs, optional indentation. Options: `paths`, `-r` (recursive), `-i` (in-place), `--dry-run`, `--exclude`, `--indent`, `-o` (output file).

### 4. Renumber chapters — `increment-chapters`

When you insert a new chapter in the middle, renumbers existing folders (e.g. Chapter 7→8, 8→9). Usage: `increment-chapters <after_N> [chapters_dir]`. Use `-y` to skip confirmation.

### 5. Create a new chapter at the end — `create-chapter`

Creates the next chapter folder at the **end** (e.g. Chapter 11 after Chapter 10) with `v1.0.0/` and an initial markdown file. Options: `-d DIR` (Chapters directory), `--dry-run`.

---

## GitHub Actions workflows

Two workflows automate releases and PDF generation. Both build the book from the **latest** version of each chapter using **Pandoc** and LaTeX.

### Create major release (`create_major_release.yaml`)

Creates a **GitHub Release** for the current version of the book when a **major** chapter version is merged to `main`.

#### When it runs

- **Trigger:** Push to `main` that changes any file under a major-version path: `Chapters/**/v*.0.0/*.md` (e.g. new or updated content in `Chapters/Chapter 3/v2.0.0/`).
- **Manual:** Can be run from the **Actions** tab via **workflow_dispatch** (e.g. to retry or after pushing a major-version change). It still only creates a release if the last commit on the branch contains major-version path changes.
- So: after a pull request is merged that adds or edits a `vX.0.0` chapter directory, the workflow runs (or you can trigger it manually).

#### What it does

1. Detects which chapters had major-version changes in the last commit.
2. Builds a single PDF of the entire book from the latest version of every chapter (Pandoc + LaTeX).
3. Creates a GitHub Release with:
   - Tag like `chapter-N-vN.0.0` (based on the updated chapter/version).
   - Release name and body listing the chapters that had major version updates.
   - The generated PDF attached to the release.

**Use case:** Mark a milestone (e.g. “Chapter 5 v2.0”) and publish a downloadable book PDF with that version.

---

### Generate book PDF (`generate_book_pdf.yaml`)

Builds the book as a single PDF from the latest version of each chapter and saves it as a **workflow artifact** (no release is created).

#### Run conditions

- **Trigger:** Any push to `main` or pull request targeting `main` that touches `Chapters/**/*.md`.
- **Manual:** Can be run from the **Actions** tab via **workflow_dispatch**.

#### Steps

1. Collects the latest version of each chapter under `Chapters/`.
2. Combines them with Pandoc into one PDF (letter size, book class, TOC, numbered sections).
3. Uploads the PDF as an artifact named `book-pdf-<sha>` with 90-day retention.

**Use case:** Get a current full-draft PDF on every significant change or on demand, without creating a release. Download the PDF from the run’s **Artifacts** in the Actions tab.

#### Note

The workflow uses **Pandoc** (and a LaTeX engine) to generate the PDF. Title, author, and other PDF metadata are set in the workflow file; edit the workflow if you need to change them.

---

## Quick reference

| Task | Command |
| ---- | ------- |
| See all chapter versions | `python chapter_version.py list` |
| New draft of one chapter | `python chapter_version.py minor -c N` |
| New draft of all chapters | `python chapter_version.py minor --all` |
| Word count (full report) | `python count_chapter_words.py` |
| Word count (total only) | `python count_chapter_words.py --total-only` |
| Format all markdown (preview) | `python format_markdown.py -r --dry-run .` |
| Format all markdown (apply) | `python format_markdown.py -r -i .` |
| Make room for new Chapter N | `python increment_chapters.py N` |
| Create new chapter at end | `python create_chapter.py` |
