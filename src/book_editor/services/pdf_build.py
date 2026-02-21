"""Build a single PDF from the latest version of each chapter (same logic as generate_book_pdf workflow)."""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def get_latest_chapter_files(chapters_dir: Path) -> List[Path]:
    """
    Collect the latest version of each chapter's markdown file, in chapter order.
    Returns list of Paths to .md files.
    """
    def parse_version(version_str: str) -> Optional[tuple]:
        match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version_str)
        if not match:
            return None
        return tuple(map(int, match.groups()))

    if not chapters_dir.exists() or not chapters_dir.is_dir():
        return []

    chapter_dirs = sorted(
        [
            d
            for d in chapters_dir.iterdir()
            if d.is_dir() and d.name.lower().startswith("chapter")
        ],
        key=lambda x: int(re.search(r"\d+", x.name).group()) if re.search(r"\d+", x.name) else 0,
    )

    latest_chapters = []
    for chapter_dir in chapter_dirs:
        version_dirs = []
        for version_dir in chapter_dir.iterdir():
            if version_dir.is_dir() and version_dir.name.startswith("v"):
                version = parse_version(version_dir.name)
                if version:
                    version_dirs.append((version, version_dir))
        if not version_dirs:
            continue
        version_dirs.sort(key=lambda x: x[0], reverse=True)
        latest_version_dir = version_dirs[0][1]
        md_files = list(latest_version_dir.glob("*.md"))
        if md_files:
            latest_chapters.append(md_files[0])
    return latest_chapters


def build_pdf(
    repo_path: str,
    output_path: Optional[Path] = None,
    title: str = "Book",
    author: str = "",
) -> Path:
    """
    Generate a single PDF from the latest version of each chapter using pandoc.
    Requires pandoc and a LaTeX engine (e.g. pdflatex) to be installed.
    Returns the path to the generated PDF.
    """
    chapters_dir = Path(repo_path) / "Chapters"
    files = get_latest_chapter_files(chapters_dir)
    if not files:
        raise ValueError("No chapters found in Chapters/")

    if output_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_") or "Book"
        output_path = Path(repo_path) / f"{safe_title}_{date_str}.pdf"
    output_path = Path(output_path)

    date_str = datetime.now().strftime("%Y-%m-%d")
    cmd = [
        "pandoc",
        *[str(f) for f in files],
        "-o",
        str(output_path),
        "--pdf-engine=pdflatex",
        "-V", "geometry:margin=1in",
        "-V", "fontsize=12pt",
        "-V", "documentclass=book",
        "-V", "papersize=letter",
        "--toc",
        "--toc-depth=2",
        "-V", f"title={title}",
        "-V", f"author={author}",
        "-V", f"date={date_str}",
        "--highlight-style=tango",
        "--number-sections",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
    if result.returncode != 0:
        raise RuntimeError(
            f"Pandoc failed: {result.stderr or result.stdout or 'unknown error'}"
        )
    return output_path


def check_pandoc_available() -> bool:
    """Return True if pandoc is on PATH."""
    result = subprocess.run(
        ["pandoc", "--version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
