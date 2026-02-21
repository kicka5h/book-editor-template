#!/usr/bin/env python3
"""
Increment chapter folder numbers after a specified chapter (e.g. after 6: 7→8, 8→9).
"""

import sys
import re
from pathlib import Path


def get_chapter_number(folder_name):
    """Extract chapter number from folder name like 'Chapter 7'."""
    match = re.match(r'Chapter\s+(\d+)', folder_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def increment_chapters(chapters_dir, after_chapter, confirm=True):
    """
    Increment all chapter folders with numbers greater than after_chapter.
    confirm: If True, prompt for confirmation; if False, proceed without prompting.
    """
    chapters_path = Path(chapters_dir)

    if not chapters_path.exists():
        print(f"Error: Directory '{chapters_dir}' does not exist.")
        return False

    chapter_folders = []
    for item in chapters_path.iterdir():
        if item.is_dir():
            chapter_num = get_chapter_number(item.name)
            if chapter_num is not None:
                chapter_folders.append((chapter_num, item))

    chapter_folders.sort(key=lambda x: x[0], reverse=True)
    chapters_to_increment = [(num, path) for num, path in chapter_folders if num > after_chapter]

    if not chapters_to_increment:
        print(f"No chapters found after Chapter {after_chapter}")
        return True

    print(f"Found {len(chapters_to_increment)} chapter(s) to increment:")
    for num, path in chapters_to_increment:
        print(f"  Chapter {num} → Chapter {num + 1}")

    if confirm:
        response = input("\nProceed with renaming? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return False

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
        print("Usage: increment-chapters <after_chapter_number> [chapters_directory]")
        print("\nExample: increment-chapters 6")
        print("Optional: increment-chapters 6 /path/to/Chapters")
        print("Use -y or --yes to skip confirmation.")
        sys.exit(1)

    try:
        after_chapter = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid chapter number")
        sys.exit(1)

    args_list = [a for a in sys.argv[2:] if a not in ("-y", "--yes")]
    confirm = "-y" not in sys.argv and "--yes" not in sys.argv
    chapters_dir_arg = args_list[0] if args_list else "Chapters"

    print(f"Incrementing chapters after Chapter {after_chapter}")
    print(f"Looking in directory: {chapters_dir_arg}")
    print()

    success = increment_chapters(chapters_dir_arg, after_chapter, confirm=confirm)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
