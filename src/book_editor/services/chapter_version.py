#!/usr/bin/env python3
"""
Chapter Version Manager — semantic versioning for book chapters (Chapter X/vX.Y.Z/).
"""

import shutil
import argparse
from pathlib import Path
import re


class ChapterVersionManager:
    def __init__(self, chapters_dir="./Chapters"):
        self.chapters_dir = Path(chapters_dir)

    def parse_version(self, version_str):
        """Parse a version string like 'v0.0.0' into (major, minor, patch)"""
        match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")
        return tuple(map(int, match.groups()))

    def format_version(self, major, minor, patch):
        """Format version tuple as string"""
        return f"v{major}.{minor}.{patch}"

    def get_latest_version(self, chapter_dir):
        """Get the latest version directory for a chapter"""
        version_dirs = []
        for item in chapter_dir.iterdir():
            if item.is_dir() and item.name.startswith('v'):
                try:
                    version = self.parse_version(item.name)
                    version_dirs.append((version, item))
                except ValueError:
                    continue

        if not version_dirs:
            raise ValueError(f"No version directories found in {chapter_dir}")

        version_dirs.sort(key=lambda x: x[0], reverse=True)
        return version_dirs[0][1]

    def increment_version(self, version_tuple, bump_type):
        """Increment version based on bump type"""
        major, minor, patch = version_tuple

        if bump_type == "major":
            return (major + 1, 0, 0)
        elif bump_type == "minor":
            return (major, minor + 1, 0)
        elif bump_type == "patch":
            return (major, minor, patch + 1)
        else:
            raise ValueError(f"Invalid bump type: {bump_type}. Use 'major', 'minor', or 'patch'")

    def get_markdown_file(self, version_dir):
        """Get the markdown file from a version directory"""
        md_files = list(version_dir.glob("*.md"))
        if not md_files:
            raise ValueError(f"No markdown file found in {version_dir}")
        if len(md_files) > 1:
            raise ValueError(f"Multiple markdown files found in {version_dir}: {md_files}")
        return md_files[0]

    def bump_chapter(self, chapter_num, bump_type):
        """Bump version for a specific chapter"""
        chapter_dir = None
        for item in self.chapters_dir.iterdir():
            if item.is_dir() and item.name.lower() == f"chapter {chapter_num}":
                chapter_dir = item
                break
        if chapter_dir is None:
            raise ValueError(f"Chapter directory not found for chapter {chapter_num}")
        if not chapter_dir.exists():
            raise ValueError(f"Chapter directory not found: {chapter_dir}")

        latest_version_dir = self.get_latest_version(chapter_dir)
        current_version = self.parse_version(latest_version_dir.name)
        md_file = self.get_markdown_file(latest_version_dir)
        new_version = self.increment_version(current_version, bump_type)
        new_version_str = self.format_version(*new_version)

        new_version_dir = chapter_dir / new_version_str
        new_version_dir.mkdir(exist_ok=False)
        new_md_file = new_version_dir / md_file.name
        shutil.copy2(md_file, new_md_file)

        print(f"✓ Chapter {chapter_num}: {latest_version_dir.name} → {new_version_str}")
        print(f"  Created: {new_version_dir}")
        print(f"  Copied: {md_file.name}")

        return new_version_dir

    def bump_all_chapters(self, bump_type):
        """Bump version for all chapters"""
        if not self.chapters_dir.exists():
            raise ValueError(f"Chapters directory not found: {self.chapters_dir}")

        chapter_dirs = []
        for item in self.chapters_dir.iterdir():
            if item.is_dir() and item.name.lower().startswith("chapter "):
                chapter_dirs.append(item)

        chapter_dirs.sort(key=lambda x: self._extract_chapter_num(x.name))

        print(f"\nBumping {bump_type} version for {len(chapter_dirs)} chapters...\n")

        results = []
        for chapter_dir in chapter_dirs:
            chapter_num = self._extract_chapter_num(chapter_dir.name)
            try:
                new_dir = self.bump_chapter(chapter_num, bump_type)
                results.append((chapter_num, True, new_dir))
            except Exception as e:
                print(f"✗ Chapter {chapter_num}: Error - {e}")
                results.append((chapter_num, False, str(e)))
            print()

        successful = sum(1 for _, success, _ in results if success)
        print(f"\nSummary: {successful}/{len(results)} chapters updated successfully")

        return results

    def _extract_chapter_num(self, dirname):
        match = re.search(r'chapter\s+(\d+)', dirname.lower())
        if match:
            return int(match.group(1))
        return 0

    def list_chapters(self):
        """List all chapters with their current versions"""
        if not self.chapters_dir.exists():
            raise ValueError(f"Chapters directory not found: {self.chapters_dir}")

        chapter_dirs = []
        for item in self.chapters_dir.iterdir():
            if item.is_dir() and item.name.lower().startswith("chapter "):
                chapter_dirs.append(item)

        chapter_dirs.sort(key=lambda x: self._extract_chapter_num(x.name))

        print(f"\nChapters in {self.chapters_dir}:\n")
        for chapter_dir in chapter_dirs:
            chapter_num = self._extract_chapter_num(chapter_dir.name)
            try:
                latest = self.get_latest_version(chapter_dir)
                md_file = self.get_markdown_file(latest)
                print(f"Chapter {chapter_num:2d}: {latest.name:10s} - {md_file.name}")
            except Exception as e:
                print(f"Chapter {chapter_num:2d}: Error - {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage semantic versioning for book chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chapter-version list
  chapter-version minor -c 5
  chapter-version major --all
  chapter-version patch -c 1 2 3
  chapter-version minor -c 1 -d /path/to/Chapters
        """
    )

    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch", "list"],
        help="Version bump type or 'list' to show current versions"
    )
    parser.add_argument(
        "-c", "--chapters",
        nargs="+",
        type=int,
        metavar="N",
        help="Chapter number(s) to bump (e.g., -c 1 2 3)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Bump all chapters"
    )
    parser.add_argument(
        "-d", "--dir",
        default="Chapters",
        help="Chapters directory (default: Chapters)"
    )

    args = parser.parse_args()
    manager = ChapterVersionManager(args.dir)

    try:
        if args.bump_type == "list":
            manager.list_chapters()
        elif args.all:
            manager.bump_all_chapters(args.bump_type)
        elif args.chapters:
            print(f"\nBumping {args.bump_type} version for specified chapters...\n")
            for chapter_num in args.chapters:
                try:
                    manager.bump_chapter(chapter_num, args.bump_type)
                    print()
                except Exception as e:
                    print(f"✗ Chapter {chapter_num}: Error - {e}\n")
        else:
            parser.error("Must specify either --all or -c with chapter number(s)")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
