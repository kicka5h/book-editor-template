#!/usr/bin/env python3
"""
Count words in the latest versioned markdown files from a Chapters directory.
Handles directory structure like: Chapters/Chapter 1/v1.0.0/file.md

# Basic usage (assumes ./Chapters directory)
python count_chapter_words.py

# Specify a different directory
python count_chapter_words.py /path/to/Chapters

# Show only the total word count
python count_chapter_words.py --total-only

# Verbose mode (shows individual files)
python count_chapter_words.py --verbose

# CSV output (for spreadsheets)
python count_chapter_words.py --csv > word_counts.csv
```

## Example Output:

**Standard mode:**
```
Chapter Word Counts (Latest Versions)
============================================================

Chapter  1 (v1.2.0):   4,523 words  (1 file)
Chapter  2 (v1.1.0):   3,892 words  (1 file)
Chapter  3 (v2.0.0):   5,234 words  (2 files)

============================================================
Total Chapters: 3
Total Words:    13,649
Average Words:  4,550 per chapter
```

**Verbose mode** shows individual file names and their word counts.

**CSV mode** outputs data that can be imported into spreadsheets:
```
Chapter,Version,Files,Words
1,1.2.0,1,4523
2,1.1.0,1,3892
3,2.0.0,2,5234
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
    """Represents a semantic version number."""
    major: int
    minor: int
    patch: int
    
    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class ChapterVersion:
    """Represents a versioned chapter."""
    chapter_num: int
    version: SemanticVersion
    directory: Path
    md_files: List[Path]
    word_count: int = 0


def parse_semantic_version(version_str: str) -> Optional[SemanticVersion]:
    """
    Parse a semantic version string like 'v1.2.3' or '1.2.3'.
    
    Args:
        version_str: Version string to parse
        
    Returns:
        SemanticVersion object or None if parsing fails
    """
    # Remove 'v' prefix if present
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
    """
    Extract chapter number from directory name.
    Supports formats like:
    - Chapter 1
    - chapter1
    - ch1
    - 01
    
    Args:
        dirname: The directory name to parse
        
    Returns:
        Chapter number or None if not found
    """
    dirname_lower = dirname.lower()
    
    # Try various patterns
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
    """
    Count words in a markdown file.
    
    Args:
        file_path: Path to the markdown file
        
    Returns:
        Word count
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove markdown formatting for more accurate word count
        # Remove code blocks
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        # Remove inline code
        content = re.sub(r'`[^`]+`', '', content)
        # Remove markdown links but keep the text
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        # Remove markdown images
        content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', content)
        # Remove markdown headers
        content = re.sub(r'^#+\s+', '', content, flags=re.MULTILINE)
        # Remove markdown emphasis markers
        content = re.sub(r'[*_]{1,2}', '', content)
        
        # Split on whitespace and count
        words = content.split()
        return len(words)
    
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return 0


def find_latest_versions(chapters_dir: Path) -> Dict[int, ChapterVersion]:
    """
    Find the latest version of each chapter in the Chapters directory.
    
    Expected structure:
        Chapters/
            Chapter 1/
                v1.0.0/
                    file.md
                v1.1.0/
                    file.md
            Chapter 2/
                v1.0.0/
                    file.md
    
    Args:
        chapters_dir: Path to the Chapters directory
        
    Returns:
        Dictionary mapping chapter number to latest ChapterVersion
    """
    if not chapters_dir.exists():
        print(f"Error: Directory not found: {chapters_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not chapters_dir.is_dir():
        print(f"Error: Not a directory: {chapters_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Dictionary to store chapter versions: {chapter_num: [ChapterVersion, ...]}
    chapter_versions = defaultdict(list)
    
    # Iterate through chapter directories
    for chapter_dir in chapters_dir.iterdir():
        if not chapter_dir.is_dir():
            continue
        
        # Extract chapter number
        chapter_num = extract_chapter_number(chapter_dir.name)
        if chapter_num is None:
            print(f"Warning: Could not extract chapter number from '{chapter_dir.name}'", file=sys.stderr)
            continue
        
        # Look for version directories inside
        for version_dir in chapter_dir.iterdir():
            if not version_dir.is_dir():
                continue
            
            # Try to parse version
            version = parse_semantic_version(version_dir.name)
            if version is None:
                print(f"Warning: Could not parse version '{version_dir.name}' in {chapter_dir.name}", file=sys.stderr)
                continue
            
            # Find all markdown files in this version directory
            md_files = list(version_dir.glob("*.md"))
            
            if not md_files:
                print(f"Warning: No markdown files found in {version_dir}", file=sys.stderr)
                continue
            
            # Create ChapterVersion object
            chapter_version = ChapterVersion(
                chapter_num=chapter_num,
                version=version,
                directory=version_dir,
                md_files=md_files
            )
            
            chapter_versions[chapter_num].append(chapter_version)
    
    # Select the latest version for each chapter
    latest_versions = {}
    for chapter_num, versions in chapter_versions.items():
        # Sort by version and take the latest
        latest = max(versions, key=lambda v: v.version)
        latest_versions[chapter_num] = latest
    
    return latest_versions


def count_words_in_chapters(latest_versions: Dict[int, ChapterVersion]) -> None:
    """
    Count words in all markdown files for each chapter version.
    
    Args:
        latest_versions: Dictionary of latest ChapterVersion objects
    """
    for chapter_num in sorted(latest_versions.keys()):
        chapter_version = latest_versions[chapter_num]
        
        # Count words in all markdown files
        total_words = 0
        for md_file in chapter_version.md_files:
            word_count = count_words_in_file(md_file)
            total_words += word_count
        
        chapter_version.word_count = total_words


def main():
    parser = argparse.ArgumentParser(
        description='Count words in the latest versioned markdown files from Chapters directory',
        epilog='''
Examples:
  %(prog)s /path/to/Chapters
  %(prog)s /path/to/Chapters --total-only
  %(prog)s /path/to/Chapters --verbose
        ''',
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
    
    # Find latest versions
    if args.verbose:
        print(f"Scanning directory: {args.chapters_dir}")
        print()
    
    latest_versions = find_latest_versions(args.chapters_dir)
    
    if not latest_versions:
        print("Error: No valid chapter versions found", file=sys.stderr)
        sys.exit(1)
    
    # Count words
    count_words_in_chapters(latest_versions)
    
    # Display results
    if args.csv:
        # CSV output
        print("Chapter,Version,Files,Words")
        for chapter_num in sorted(latest_versions.keys()):
            cv = latest_versions[chapter_num]
            print(f"{chapter_num},{cv.version},{len(cv.md_files)},{cv.word_count}")
    elif args.total_only:
        # Just the total
        total_words = sum(cv.word_count for cv in latest_versions.values())
        print(f"{total_words:,}")
    else:
        # Detailed output
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
        
        # Summary
        print()
        print("=" * 60)
        total_words = sum(cv.word_count for cv in latest_versions.values())
        total_chapters = len(latest_versions)
        avg_words = total_words / total_chapters if total_chapters > 0 else 0
        
        print(f"Total Chapters: {total_chapters}")
        print(f"Total Words:    {total_words:,}")
        print(f"Average Words:  {avg_words:,.0f} per chapter")
        print()
        
        # Breakdown by version
        if args.verbose:
            version_counts = defaultdict(int)
            for cv in latest_versions.values():
                version_counts[str(cv.version)] += 1
            
            print("Version Distribution:")
            for version in sorted(version_counts.keys()):
                print(f"  v{version}: {version_counts[version]} chapter(s)")


if __name__ == '__main__':
    main()