#!/usr/bin/env python3
"""
Format Markdown files.
Can process individual files or recursively process entire directories.

Usage examples:
# Preview changes in entire repo (dry run)
python format_markdown.py -r --dry-run /path/to/your/repo

# Format all markdown files in repo (in-place)
python format_markdown.py -r -i /path/to/your/repo

# Format with custom exclusions
python format_markdown.py -r -i /path/to/repo --exclude .git node_modules build dist

# Format current directory
python format_markdown.py -r -i ./
"""

import sys
import argparse
from pathlib import Path
from typing import List


def format_markdown(content: str, indent_paragraphs: bool = False, indent_string: str = "    ") -> str:
    """
    Add blank lines between paragraphs in markdown content, optionally with indentation.
    
    Args:
        content: The markdown file content as a string
        indent_paragraphs: If True, indent new paragraphs (not the first one)
        indent_string: The string to use for indentation (default: 4 spaces)
        
    Returns:
        Formatted content with blank lines between paragraphs
    """
    lines = content.split('\n')
    formatted_lines = []
    prev_line_empty = True  # Start as True to avoid leading blank line
    
    for line in lines:
        current_line_empty = line.strip() == ''
        
        # Add the current line
        formatted_lines.append(line)
        
        # If current line has content and next line will have content,
        # we need to ensure there's a blank line after this one
        if not current_line_empty and not prev_line_empty:
            # Check if we need to add a blank line
            # (we'll handle this when we see the next non-empty line)
            pass
        
        prev_line_empty = current_line_empty
    
    # Second pass: ensure blank lines between paragraphs and add indentation
    result = []
    i = 0
    is_first_paragraph = True
    in_code_block = False
    
    while i < len(formatted_lines):
        line = formatted_lines[i]
        stripped = line.strip()
        
        # Track code blocks (don't indent inside them)
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue
        
        # Don't process lines inside code blocks
        if in_code_block:
            result.append(line)
            i += 1
            continue
        
        # Check for special markdown lines that shouldn't be indented
        is_special_line = (
            stripped.startswith('#') or      # Headers
            stripped.startswith('- ') or     # Unordered lists
            stripped.startswith('* ') or     # Unordered lists
            stripped.startswith('+ ') or     # Unordered lists
            (len(stripped) > 0 and stripped[0].isdigit() and '. ' in stripped) or  # Numbered lists
            stripped.startswith('>') or      # Blockquotes
            stripped.startswith('|') or      # Tables
            stripped.startswith('---') or    # Horizontal rules
            stripped.startswith('***') or    # Horizontal rules
            stripped.startswith('===')       # Horizontal rules
        )
        
        if stripped != '':  # Current line has content
            # Apply indentation if requested and appropriate
            if indent_paragraphs and not is_first_paragraph and not is_special_line:
                result.append(indent_string + line)
            else:
                result.append(line)
            
            # Mark that we've seen the first paragraph
            if not is_special_line:
                is_first_paragraph = False
            
            # Look ahead to see if we need a blank line
            if i + 1 < len(formatted_lines):
                next_line = formatted_lines[i + 1]
                if next_line.strip() != '':  # Next line also has content
                    # Add a blank line between them
                    result.append('')
        else:
            # Empty line - just add it
            result.append(line)
        
        i += 1
    
    return '\n'.join(result)


def find_markdown_files(directory: Path, exclude_patterns: List[str] = None) -> List[Path]:
    """
    Recursively find all markdown files in a directory.
    
    Args:
        directory: Root directory to search
        exclude_patterns: List of directory names to exclude (e.g., ['node_modules', '.git'])
        
    Returns:
        List of Path objects for all markdown files found
    """
    if exclude_patterns is None:
        exclude_patterns = ['.git', 'node_modules', '__pycache__', '.venv', 'venv']
    
    markdown_files = []
    
    for path in directory.rglob('*'):
        # Skip if path contains any excluded directory
        if any(excluded in path.parts for excluded in exclude_patterns):
            continue
        
        # Check if it's a markdown file
        if path.is_file() and path.suffix.lower() in ['.md', '.markdown']:
            markdown_files.append(path)
    
    return sorted(markdown_files)


def process_file(input_path: Path, output_path: Path = None, in_place: bool = False, 
                dry_run: bool = False, indent_paragraphs: bool = False, indent_string: str = "    "):
    """
    Process a single markdown file.
    
    Args:
        input_path: Path to input markdown file
        output_path: Path to output file (if not in-place)
        in_place: If True, modify the file in place
        dry_run: If True, only show what would be done without making changes
        indent_paragraphs: If True, indent new paragraphs
        indent_string: String to use for indentation
    """
    # Read the file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Format the content
    formatted_content = format_markdown(content, indent_paragraphs, indent_string)
    
    # Check if changes are needed
    if content == formatted_content:
        if not dry_run:
            print(f"No changes needed: {input_path}")
        return False
    
    # Determine output location
    if in_place:
        output = input_path
    elif output_path:
        output = output_path
    else:
        output = input_path.parent / f"{input_path.stem}{input_path.suffix}"
    
    if dry_run:
        print(f"Would format: {input_path} -> {output}")
    else:
        # Write the formatted content
        with open(output, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        print(f"Formatted: {input_path} -> {output}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Format Markdown files by adding blank lines between paragraphs',
        epilog='Examples:\n'
               '  %(prog)s -i file.md                         # Format single file in place\n'
               '  %(prog)s -r -i /path/to/repo                # Format all .md files in repo\n'
               '  %(prog)s -r -i --indent /path/to/repo       # Format with paragraph indentation\n'
               '  %(prog)s -r --dry-run /path/to/repo         # Preview changes without modifying\n',
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
        help='Directory names to exclude (default: .git node_modules __pycache__ .venv venv)'
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
    
    # Validate arguments
    if args.output and (len(args.paths) > 1 or args.recursive):
        print("Error: --output can only be used with a single input file", file=sys.stderr)
        sys.exit(1)
    
    # Collect all files to process
    files_to_process = []
    
    for path in args.paths:
        if not path.exists():
            print(f"Error: Path not found: {path}", file=sys.stderr)
            continue
        
        if path.is_file():
            if not path.suffix.lower() in ['.md', '.markdown']:
                print(f"Warning: {path} doesn't appear to be a Markdown file", file=sys.stderr)
            files_to_process.append(path)
        elif path.is_dir():
            if not args.recursive:
                print(f"Error: {path} is a directory. Use -r/--recursive to process directories", file=sys.stderr)
                continue
            
            found_files = find_markdown_files(path, args.exclude)
            if not found_files:
                print(f"No markdown files found in {path}", file=sys.stderr)
            else:
                print(f"Found {len(found_files)} markdown file(s) in {path}")
                files_to_process.extend(found_files)
    
    if not files_to_process:
        print("No files to process", file=sys.stderr)
        sys.exit(1)
    
    # Process each file
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
    
    # Summary
    print(f"\n{'Dry run summary' if args.dry_run else 'Summary'}:")
    print(f"  Files processed: {processed}")
    print(f"  Files {'that would be ' if args.dry_run else ''}changed: {changed}")
    print(f"  Files unchanged: {processed - changed}")
    if errors:
        print(f"  Errors: {errors}")



if __name__ == '__main__':
    main()