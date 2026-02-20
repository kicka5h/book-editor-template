#!/usr/bin/env python3
"""
Create a new chapter at the end of the Chapters folder.

Finds the highest chapter number (e.g. Chapter 10), creates the next chapter folder
(Chapter 11), adds a v1.0.0 version folder, and creates an initial markdown file
(v1.0.0.md) inside it.

Usage:
  python create_chapter.py
  python create_chapter.py -d /path/to/Chapters
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional


def get_chapter_number(folder_name: str) -> Optional[int]:
    """Extract chapter number from folder name like 'Chapter 7'."""
    match = re.match(r"Chapter\s+(\d+)", folder_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def get_max_chapter_number(chapters_dir: Path) -> int:
    """Return the highest chapter number in the Chapters directory. Returns 0 if empty."""
    max_num = 0
    for item in chapters_dir.iterdir():
        if item.is_dir():
            n = get_chapter_number(item.name)
            if n is not None:
                max_num = max(max_num, n)
    return max_num


def create_new_chapter(chapters_dir: Path, dry_run: bool = False) -> Optional[Path]:
    """
    Create a new chapter folder with v1.0.0 and an initial markdown file.

    Returns the path to the new chapter directory, or None on failure.
    """
    if not chapters_dir.exists():
        print(f"Error: Directory '{chapters_dir}' does not exist.", file=sys.stderr)
        return None

    if not chapters_dir.is_dir():
        print(f"Error: '{chapters_dir}' is not a directory.", file=sys.stderr)
        return None

    next_num = get_max_chapter_number(chapters_dir) + 1
    chapter_name = f"Chapter {next_num}"
    chapter_path = chapters_dir / chapter_name
    version_dir = chapter_path / "v1.0.0"
    md_file = version_dir / "v1.0.0.md"

    if chapter_path.exists():
        print(f"Error: '{chapter_path}' already exists.", file=sys.stderr)
        return None

    if dry_run:
        print(f"Would create: {chapter_path}/")
        print(f"Would create: {version_dir}/")
        print(f"Would create: {md_file}")
        return chapter_path

    chapter_path.mkdir(parents=False)
    version_dir.mkdir(parents=False)
    md_file.write_text(
        f"# {chapter_name}\n\n",
        encoding="utf-8",
    )

    print(f"Created: {chapter_path}/")
    print(f"Created: {version_dir}/")
    print(f"Created: {md_file}")
    return chapter_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new chapter at the end of the Chapters folder (e.g. Chapter 11 after Chapter 10)",
        epilog="Example: python create_chapter.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--dir",
        type=Path,
        default=Path("Chapters"),
        help="Chapters directory (default: Chapters)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without creating anything",
    )
    args = parser.parse_args()

    result = create_new_chapter(args.dir, dry_run=args.dry_run)
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
