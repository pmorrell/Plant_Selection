#!/usr/bin/env python3
"""
Search for terms in markdown files and report counts.
Usage: ./search_terms.py <directory_with_markdown_files> <terms_file>
"""

import sys
import argparse
import re
from pathlib import Path
from datetime import datetime


def log(msg):
    """Print log message with timestamp."""
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}", file=sys.stderr)


def read_search_terms(terms_file):
    """
    Read search terms from file.
    Format: "Display Name: pattern1|pattern2|pattern3"
    Returns list of (display_name, [patterns]) tuples.
    """
    term_groups = []
    
    with open(terms_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse "Display Name: pattern1|pattern2"
            if ':' not in line:
                log(f"Warning: Skipping line {line_num} without 'Name: pattern' format: {line}")
                continue
            
            display_name, patterns_str = line.split(':', 1)
            display_name = display_name.strip()
            patterns_str = patterns_str.strip()
            
            if not display_name or not patterns_str:
                log(f"Warning: Skipping line {line_num} with empty name or patterns: {line}")
                continue
            
            # Split patterns by |
            patterns = [p.strip() for p in patterns_str.split('|')]
            patterns = [p for p in patterns if p]  # Remove empty patterns
            
            if patterns:
                term_groups.append((display_name, patterns))
    
    return term_groups


def search_files(directory, pattern, case_insensitive=True, whole_word=True):
    """
    Search for pattern in all markdown files.
    Returns set of matching file paths.
    """
    markdown_dir = Path(directory)
    if not markdown_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Build regex pattern with word boundaries
    if whole_word:
        regex_pattern = r'\b' + re.escape(pattern) + r'\b'
    else:
        regex_pattern = re.escape(pattern)
    
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled_pattern = re.compile(regex_pattern, flags)
    except re.error as e:
        log(f"Error compiling regex pattern '{pattern}': {e}")
        return set()
    
    matching_files = set()
    
    for md_file in markdown_dir.glob('**/*.md'):
        try:
            with open(md_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if compiled_pattern.search(content):
                    matching_files.add(md_file)
        except (OSError, IOError) as e:
            log(f"Warning: Skipping file {md_file}: {e}")
        except Exception as e:
            log(f"Warning: Error reading file {md_file}: {e}")
    
    return matching_files


def main():
    parser = argparse.ArgumentParser(
        description='Search for terms in markdown files and report counts'
    )
    parser.add_argument('directory', help='Directory containing .md files to search')
    parser.add_argument('terms_file', help='File containing search terms (one per line)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Show what would be searched without running searches')
    
    args = parser.parse_args()
    
    markdown_dir = Path(args.directory)
    terms_file = Path(args.terms_file)
    
    # Validate inputs
    if not markdown_dir.is_dir():
        log(f"Error: Directory not found: {args.directory}")
        sys.exit(1)
    
    if not terms_file.is_file():
        log(f"Error: Terms file not found: {args.terms_file}")
        sys.exit(1)
    
    # Read search terms
    log(f"Reading search terms from: {args.terms_file}")
    term_groups = read_search_terms(terms_file)
    
    if not term_groups:
        log(f"Error: No search terms found in {args.terms_file}")
        log("Expected format: 'Display Name: pattern1|pattern2|pattern3'")
        sys.exit(1)
    
    # Count total markdown files
    total_files = len(list(markdown_dir.glob('**/*.md')))
    if total_files == 0:
        log(f"Error: No markdown files found in {args.directory}")
        sys.exit(1)
    
    log(f"Searching {total_files} markdown files in: {args.directory}")
    log(f"Searching for {len(term_groups)} term groups")
    
    # Search for each term group
    term_counts = {}
    
    for display_name, patterns in term_groups:
        matching_files = set()
        
        for pattern in patterns:
            if args.dry_run:
                log(f"Files matching pattern: '{pattern}' (group: '{display_name}')")
                files = search_files(args.directory, pattern)
                for f in sorted(files):
                    print(f)
            else:
                files = search_files(args.directory, pattern)
                matching_files.update(files)
        
        if not args.dry_run:
            term_counts[display_name] = len(matching_files)
    
    # Output results
    if not args.dry_run:
        print()
        print("Search Results")
        print("=" * 59)
        print(f"Total Markdown files searched: {total_files}")
        print("=" * 59)
        print()
        print(f"{'Search Term':<40} | {'Papers Found':>12}")
        print("-" * 59)
        
        # Sort by count (descending) then by name (ascending)
        sorted_terms = sorted(term_counts.items(), 
                             key=lambda x: (-x[1], x[0]))
        
        for term, count in sorted_terms:
            print(f"{term:<40} | {count:>12}")
        
        print()
    
    log("Search completed")


if __name__ == '__main__':
    main()
