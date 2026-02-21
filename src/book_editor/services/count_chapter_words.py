#!/usr/bin/env python3
"""
Count words in the latest versioned markdown files from a Chapters directory.
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class SemanticVersion:
    major: int
    minor: int
    patch: int

    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class ChapterVersion:
    chapter_num: int
    version: SemanticVersion
    directory: Path
    md_files: List[Path]
    word_count: int = 0


def parse_semantic_version(version_str: str) -> Optional[SemanticVersion]:
    version_str = version_str.lstrip('v')
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if match:
        return SemanticVersion(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3))
        )
    return None


def extract_chapter_number(dirname: str) -> Optional[int]:
    dirname_lower = dirname.lower()
    patterns = [
        r'chapter[_\s-]*(\d+)',
        r'ch[_\s-]*(\d+)',
        r'^(\d+)$',
    ]
    for pattern in patterns:
        match = re.search(pattern, dirname_lower)
        if match:
            return int(match.group(1))
    return None


def count_words_in_file(file_path: Path) -> int:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        content = re.sub(r'`[^`]+`', '', content)
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', content)
        content = re.sub(r'^#+\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'[*_]{1,2}', '', content)
        words = content.split()
        return len(words)
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return 0


def find_latest_versions(chapters_dir: Path) -> Dict[int, ChapterVersion]:
    if not chapters_dir.exists():
        print(f"Error: Directory not found: {chapters_dir}", file=sys.stderr)
        sys.exit(1)

    if not chapters_dir.is_dir():
        print(f"Error: Not a directory: {chapters_dir}", file=sys.stderr)
        sys.exit(1)

    chapter_versions = defaultdict(list)

    for chapter_dir in chapters_dir.iterdir():
        if not chapter_dir.is_dir():
            continue

        chapter_num = extract_chapter_number(chapter_dir.name)
        if chapter_num is None:
            print(f"Warning: Could not extract chapter number from '{chapter_dir.name}'", file=sys.stderr)
            continue

        for version_dir in chapter_dir.iterdir():
            if not version_dir.is_dir():
                continue

            version = parse_semantic_version(version_dir.name)
            if version is None:
                continue

            md_files = list(version_dir.glob("*.md"))
            if not md_files:
                continue

            chapter_version = ChapterVersion(
                chapter_num=chapter_num,
                version=version,
                directory=version_dir,
                md_files=md_files
            )
            chapter_versions[chapter_num].append(chapter_version)

    latest_versions = {}
    for chapter_num, versions in chapter_versions.items():
        latest = max(versions, key=lambda v: v.version)
        latest_versions[chapter_num] = latest

    return latest_versions


def count_words_in_chapters(latest_versions: Dict[int, ChapterVersion]) -> None:
    for chapter_num in sorted(latest_versions.keys()):
        chapter_version = latest_versions[chapter_num]
        total_words = 0
        for md_file in chapter_version.md_files:
            word_count = count_words_in_file(md_file)
            total_words += word_count
        chapter_version.word_count = total_words


def main():
    parser = argparse.ArgumentParser(
        description='Count words in the latest versioned markdown files from Chapters directory',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'chapters_dir',
        type=Path,
        nargs='?',
        default=Path.cwd() / 'Chapters',
        help='Path to the Chapters directory (default: ./Chapters)'
    )
    parser.add_argument(
        '--total-only',
        action='store_true',
        help='Only show total word count'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed information including file names'
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Output in CSV format'
    )

    args = parser.parse_args()

    if args.verbose:
        print(f"Scanning directory: {args.chapters_dir}")
        print()

    latest_versions = find_latest_versions(args.chapters_dir)

    if not latest_versions:
        print("Error: No valid chapter versions found", file=sys.stderr)
        sys.exit(1)

    count_words_in_chapters(latest_versions)

    if args.csv:
        print("Chapter,Version,Files,Words")
        for chapter_num in sorted(latest_versions.keys()):
            cv = latest_versions[chapter_num]
            print(f"{chapter_num},{cv.version},{len(cv.md_files)},{cv.word_count}")
    elif args.total_only:
        total_words = sum(cv.word_count for cv in latest_versions.values())
        print(f"{total_words:,}")
    else:
        print("Chapter Word Counts (Latest Versions)")
        print("=" * 60)
        print()

        for chapter_num in sorted(latest_versions.keys()):
            cv = latest_versions[chapter_num]

            if args.verbose:
                print(f"Chapter {chapter_num} (v{cv.version}):")
                print(f"  Directory: {cv.directory}")
                print(f"  Files:")
                for md_file in cv.md_files:
                    file_words = count_words_in_file(md_file)
                    print(f"    - {md_file.name}: {file_words:,} words")
                print(f"  Total: {cv.word_count:,} words")
                print()
            else:
                files_str = f"{len(cv.md_files)} file" + ("s" if len(cv.md_files) > 1 else "")
                print(f"Chapter {chapter_num:2d} (v{cv.version}): {cv.word_count:7,} words  ({files_str})")

        print()
        print("=" * 60)
        total_words = sum(cv.word_count for cv in latest_versions.values())
        total_chapters = len(latest_versions)
        avg_words = total_words / total_chapters if total_chapters > 0 else 0

        print(f"Total Chapters: {total_chapters}")
        print(f"Total Words:    {total_words:,}")
        print(f"Average Words:  {avg_words:,.0f} per chapter")
        print()

        if args.verbose:
            version_counts = defaultdict(int)
            for cv in latest_versions.values():
                version_counts[str(cv.version)] += 1
            print("Version Distribution:")
            for version in sorted(version_counts.keys()):
                print(f"  v{version}: {version_counts[version]} chapter(s)")


if __name__ == '__main__':
    main()
