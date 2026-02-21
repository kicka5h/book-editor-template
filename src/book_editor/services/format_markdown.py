#!/usr/bin/env python3
"""
Format Markdown files (blank lines between paragraphs, optional indentation).
"""

import sys
import argparse
from pathlib import Path
from typing import List


def format_markdown(content: str, indent_paragraphs: bool = False, indent_string: str = "    ") -> str:
    lines = content.split('\n')
    formatted_lines = []
    prev_line_empty = True

    for line in lines:
        current_line_empty = line.strip() == ''
        formatted_lines.append(line)
        prev_line_empty = current_line_empty

    result = []
    i = 0
    is_first_paragraph = True
    in_code_block = False

    while i < len(formatted_lines):
        line = formatted_lines[i]
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue

        if in_code_block:
            result.append(line)
            i += 1
            continue

        is_special_line = (
            stripped.startswith('#') or
            stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('+ ') or
            (len(stripped) > 0 and stripped[0].isdigit() and '. ' in stripped) or
            stripped.startswith('>') or stripped.startswith('|') or
            stripped.startswith('---') or stripped.startswith('***') or stripped.startswith('===')
        )

        if stripped != '':
            if indent_paragraphs and not is_first_paragraph and not is_special_line:
                result.append(indent_string + line)
            else:
                result.append(line)
            if not is_special_line:
                is_first_paragraph = False
            if i + 1 < len(formatted_lines):
                next_line = formatted_lines[i + 1]
                if next_line.strip() != '':
                    result.append('')
        else:
            result.append(line)

        i += 1

    return '\n'.join(result)


def find_markdown_files(directory: Path, exclude_patterns: List[str] = None) -> List[Path]:
    if exclude_patterns is None:
        exclude_patterns = ['.git', 'node_modules', '__pycache__', '.venv', 'venv']

    markdown_files = []
    for path in directory.rglob('*'):
        if any(excluded in path.parts for excluded in exclude_patterns):
            continue
        if path.is_file() and path.suffix.lower() in ['.md', '.markdown']:
            markdown_files.append(path)
    return sorted(markdown_files)


def process_file(input_path: Path, output_path: Path = None, in_place: bool = False,
                dry_run: bool = False, indent_paragraphs: bool = False, indent_string: str = "    "):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    formatted_content = format_markdown(content, indent_paragraphs, indent_string)

    if content == formatted_content:
        if not dry_run:
            print(f"No changes needed: {input_path}")
        return False

    if in_place:
        output = input_path
    elif output_path:
        output = output_path
    else:
        output = input_path.parent / f"{input_path.stem}{input_path.suffix}"

    if dry_run:
        print(f"Would format: {input_path} -> {output}")
    else:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        print(f"Formatted: {input_path} -> {output}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Format Markdown files by adding blank lines between paragraphs',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'paths',
        nargs='+',
        type=Path,
        help='Markdown file(s) or directory/directories to format'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Recursively process directories'
    )
    parser.add_argument(
        '-i', '--in-place',
        action='store_true',
        help='Modify files in place'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file (only valid with single input file)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--exclude',
        nargs='*',
        default=['.git', 'node_modules', '__pycache__', '.venv', 'venv'],
        help='Directory names to exclude'
    )
    parser.add_argument(
        '--indent',
        action='store_true',
        help='Indent new paragraphs (first paragraph not indented)'
    )
    parser.add_argument(
        '--indent-string',
        default='    ',
        help='String to use for indentation (default: 4 spaces)'
    )

    args = parser.parse_args()

    if args.output and (len(args.paths) > 1 or args.recursive):
        print("Error: --output can only be used with a single input file", file=sys.stderr)
        sys.exit(1)

    files_to_process = []

    for path in args.paths:
        if not path.exists():
            print(f"Error: Path not found: {path}", file=sys.stderr)
            continue

        if path.is_file():
            files_to_process.append(path)
        elif path.is_dir():
            if not args.recursive:
                print(f"Error: {path} is a directory. Use -r/--recursive to process directories", file=sys.stderr)
                continue
            found_files = find_markdown_files(path, args.exclude)
            if found_files:
                print(f"Found {len(found_files)} markdown file(s) in {path}")
                files_to_process.extend(found_files)

    if not files_to_process:
        print("No files to process", file=sys.stderr)
        sys.exit(1)

    processed = 0
    changed = 0
    errors = 0

    for file_path in files_to_process:
        try:
            file_changed = process_file(
                file_path,
                args.output,
                args.in_place,
                args.dry_run,
                args.indent,
                args.indent_string
            )
            processed += 1
            if file_changed:
                changed += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            errors += 1

    print(f"\n{'Dry run summary' if args.dry_run else 'Summary'}:")
    print(f"  Files processed: {processed}")
    print(f"  Files {'that would be ' if args.dry_run else ''}changed: {changed}")
    print(f"  Files unchanged: {processed - changed}")
    if errors:
        print(f"  Errors: {errors}")


if __name__ == '__main__':
    main()
