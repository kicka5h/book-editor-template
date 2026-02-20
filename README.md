# book-editor-template

A template project for writing a book using GitHub as source control. This repository includes tools to manage chapter versions, count words, format markdown, and add or renumber chapters.

## Directory structure

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

## Tools

All tools are Python 3 scripts. Run them from the repository root (or pass the correct paths).

### 1. Chapter versioning — `chapter_version.py`

Manages semantic versioning for chapters so older versions stay in the repo and remain documented in source.

**List all chapters and their current versions:**

```bash
python chapter_version.py list
```

**Bump versions:**

- **`minor`** — typical bump when revising a chapter (e.g. `v1.0.0` → `v1.1.0`).
- **`patch`** — small fixes (e.g. `v1.1.0` → `v1.1.1`).
- **`major`** — large changes (e.g. `v1.1.0` → `v2.0.0`).

Bumping creates a new version folder and **copies** the markdown file from the current latest version. You then edit the new file.

**Examples:**

```bash
# Bump minor version for chapter 5
python chapter_version.py minor -c 5

# Bump patch for chapters 1, 2, and 3
python chapter_version.py patch -c 1 2 3

# Bump major version for all chapters
python chapter_version.py major --all

# Use a custom chapters directory
python chapter_version.py minor -c 1 -d /path/to/Chapters
```

**Options:**

| Option | Description |
| ------ | ----------- |
| `-c N` / `--chapters N [N ...]` | Chapter number(s) to bump |
| `--all` | Bump all chapters |
| `-d DIR` / `--dir DIR` | Chapters directory (default: `chapters`) |

---

### 2. Word count — `count_chapter_words.py`

Counts words in the **latest** version of each chapter (or the whole project). Strips code blocks, links, and markdown formatting for a prose-only count.

**Basic usage (uses `./Chapters` by default):**

```bash
python count_chapter_words.py
```

**Examples:**

```bash
# Custom chapters directory
python count_chapter_words.py /path/to/Chapters

# Only print total word count (e.g. for scripts)
python count_chapter_words.py --total-only

# Show per-file details
python count_chapter_words.py --verbose

# CSV for spreadsheets
python count_chapter_words.py --csv > word_counts.csv
```

**Options:**

| Option | Description |
| ------ | ----------- |
| `chapters_dir` | Path to `Chapters` (optional; default: `./Chapters`) |
| `--total-only` | Print only the total word count |
| `-v` / `--verbose` | Show files and paths per chapter |
| `--csv` | Output CSV: Chapter, Version, Files, Words |

---

### 3. Markdown formatting — `format_markdown.py`

Formats markdown files to a consistent style: blank lines between paragraphs and optional paragraph indentation. Skips code blocks, lists, headers, blockquotes, and tables when applying indentation.

**Examples:**

```bash
# Preview what would change (dry run) for the whole repo
python format_markdown.py -r --dry-run .

# Format all markdown files in the repo in place
python format_markdown.py -r -i .

# Format a single file in place
python format_markdown.py -i path/to/file.md

# Format with custom exclusions
python format_markdown.py -r -i . --exclude .git node_modules build dist

# Add paragraph indentation (first paragraph not indented)
python format_markdown.py -r -i --indent .
```

**Options:**

| Option | Description |
| ------ | ----------- |
| `paths` | File(s) or directory/directories to format |
| `-r` / `--recursive` | Process directories recursively (required for dirs) |
| `-i` / `--in-place` | Overwrite files (required to save changes) |
| `--dry-run` | Show what would be done without changing files |
| `--exclude NAME [NAME ...]` | Directory names to skip (default includes `.git`, `node_modules`, etc.) |
| `--indent` | Indent new paragraphs (4 spaces by default) |
| `--indent-string STR` | Custom indentation string |
| `-o FILE` / `--output FILE` | Output file (single file only) |

---

### 4. Add a new chapter — `increment_chapters.py`

When you insert a new chapter in the middle of the book, this script renumbers existing chapters so the new one can take the correct number. It renames folders only (e.g. `Chapter 7` → `Chapter 8`); it does not create the new chapter folder or version subfolders.

**Usage:**

```bash
python increment_chapters.py <after_chapter_number> [chapters_directory]
```

**Examples:**

```bash
# Insert a new Chapter 6: current 6→7, 7→8, etc. (default dir: ./Chapters)
python increment_chapters.py 6

# Then create the new folder and content, e.g. Chapters/Chapter 6/v1.0.0/v1.0.0.md
```

```bash
# Use a custom Chapters path
python increment_chapters.py 6 /path/to/Chapters
```

The script lists the renames, asks for confirmation (`y/n`), then renames. After it runs, create your new chapter folder (e.g. `Chapter 6`) and add your first version (e.g. `v1.0.0/` and a markdown file) using your usual workflow.

---

### 5. Create a new chapter at the end — `create_chapter.py`

Creates a new chapter folder at the **end** of the book (e.g. if the highest is Chapter 10, creates Chapter 11). Also creates a `v1.0.0` version folder and an initial `v1.0.0.md` file inside it, so the chapter is ready to edit and works with the other tools.

**Usage:**

```bash
python create_chapter.py
```

**Examples:**

```bash
# Create next chapter (default: ./Chapters)
python create_chapter.py

# Custom chapters directory
python create_chapter.py -d /path/to/Chapters

# Preview what would be created
python create_chapter.py --dry-run
```

**Options:**

| Option | Description |
| ------ | ----------- |
| `-d DIR` / `--dir DIR` | Chapters directory (default: `Chapters`) |
| `--dry-run` | Show paths that would be created without creating anything |

---

## GitHub Actions workflows

Two workflows automate releases and PDF generation. Both build the book from the **latest** version of each chapter using **Pandoc** and LaTeX.

### Create major release (`create_major_release.yaml`)

Creates a **GitHub Release** for the current version of the book when a **major** chapter version is merged to `main`.

#### When it runs

- **Trigger:** Push to `main` that changes any file under a major-version path: `Chapters/**/v*.0.0/*.md` (e.g. new or updated content in `Chapters/Chapter 3/v2.0.0/`).
- So: after a pull request is merged that adds or edits a `vX.0.0` chapter directory, the workflow runs.

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
