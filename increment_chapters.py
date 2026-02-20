#!/usr/bin/env python3
"""
Script to increment chapter folder numbers after a specified chapter.
Example: If you're adding a new Chapter 6, run with parameter 6 to increment
next chapter: Chapter 7 → 8, etc.

python increment_chapters.py 6
"""

import os
import sys
import re
from pathlib import Path


def get_chapter_number(folder_name):
    """Extract chapter number from folder name like 'Chapter 7'."""
    match = re.match(r'Chapter\s+(\d+)', folder_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def increment_chapters(chapters_dir, after_chapter):
    """
    Increment all chapter folders with numbers greater than after_chapter.
    
    Args:
        chapters_dir: Path to the Chapters directory
        after_chapter: Chapter number after which to start incrementing
    """
    chapters_path = Path(chapters_dir)
    
    if not chapters_path.exists():
        print(f"Error: Directory '{chapters_dir}' does not exist.")
        return False
    
    # Get all chapter folders
    chapter_folders = []
    for item in chapters_path.iterdir():
        if item.is_dir():
            chapter_num = get_chapter_number(item.name)
            if chapter_num is not None:
                chapter_folders.append((chapter_num, item))
    
    # Sort by chapter number in descending order (to avoid conflicts)
    chapter_folders.sort(key=lambda x: x[0], reverse=True)
    
    # Filter to only chapters after the specified number
    chapters_to_increment = [(num, path) for num, path in chapter_folders if num > after_chapter]
    
    if not chapters_to_increment:
        print(f"No chapters found after Chapter {after_chapter}")
        return True
    
    print(f"Found {len(chapters_to_increment)} chapter(s) to increment:")
    for num, path in chapters_to_increment:
        print(f"  Chapter {num} → Chapter {num + 1}")
    
    # Ask for confirmation
    response = input("\nProceed with renaming? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return False
    
    # Perform the renaming (in reverse order to avoid conflicts)
    for chapter_num, old_path in chapters_to_increment:
        new_num = chapter_num + 1
        new_name = f"Chapter {new_num}"
        new_path = old_path.parent / new_name
        
        try:
            old_path.rename(new_path)
            print(f"✓ Renamed: {old_path.name} → {new_path.name}")
        except Exception as e:
            print(f"✗ Error renaming {old_path.name}: {e}")
            return False
    
    print(f"\n✓ Successfully incremented {len(chapters_to_increment)} chapter(s)")
    print(f"You can now create your new 'Chapter {after_chapter + 1}' folder")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python increment_chapters.py <after_chapter_number> [chapters_directory]")
        print("\nExample: python increment_chapters.py 6")
        print("         This will increment Chapter 6 → 7, Chapter 7 → 8, etc.")
        print("\nOptional: Specify chapters directory as second argument")
        print("         python increment_chapters.py 6 /path/to/Chapters")
        sys.exit(1)
    
    try:
        after_chapter = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid chapter number")
        sys.exit(1)
    
    # Default to "Chapters" directory in current working directory
    chapters_dir = sys.argv[2] if len(sys.argv) > 2 else "Chapters"
    
    print(f"Incrementing chapters after Chapter {after_chapter}")
    print(f"Looking in directory: {chapters_dir}")
    print()
    
    success = increment_chapters(chapters_dir, after_chapter)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()