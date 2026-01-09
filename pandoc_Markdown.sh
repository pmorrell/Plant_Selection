#!/usr/bin/env zsh -l

# Small zsh script to convert HTML/HTM files to Markdown using pandoc.
# Usage: pandoc_Markdown.sh [WORK_DIR] [OUTPUT_DIR] [HTML_FILES...]
#   WORK_DIR   - directory to search for HTML files (default: current directory)
#   OUTPUT_DIR - directory to write Markdown files (default: $WORK_DIR/output)
# If no HTML_FILES are provided, the script will recursively find all .html/.htm files
# under WORK_DIR and convert them while preserving relative paths.

set -e
set -u
set -o pipefail 2>/dev/null || true

log() {
  local msg="$1"
  echo "$(date +'%Y-%m-%d %H:%M:%S') - ${msg}"
}

usage() {
  cat <<EOF
Usage: $0 [WORK_DIR] [OUTPUT_DIR] [HTML_FILES...]

Converts HTML/HTM files to Markdown using pandoc. If no HTML files are provided,
the script will recursively convert all .html and .htm files under WORK_DIR.

Positional arguments:
  WORK_DIR    Directory to search for HTML files (default: current directory)
  OUTPUT_DIR  Directory to place Markdown output (default: WORK_DIR/output)
  HTML_FILES  Optional list of HTML files (paths or globs). If provided, only
              those files are converted.

Examples:
  $0                    # convert all HTML under current dir -> ./output
  $0 /path/to/dir       # convert all HTML under /path/to/dir -> /path/to/dir/output
  $0 /in /out a.html b.html
  $0 /in /out "**/*.html"   # (shell must expand the glob or pass expanded names)
EOF
}

# Quick help
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

DEFAULT_WORK_DIR="$(pwd)"
WORK_DIR="${1:-${WORK_DIR:-${DEFAULT_WORK_DIR}}}"
shift || true
OUTPUT_DIR="${1:-${OUTPUT_DIR:-${WORK_DIR}/output}}"
shift || true

# Check pandoc
if ! command -v pandoc >/dev/null 2>&1; then
  log "Error: pandoc is not available. Please install pandoc or load the module."
  exit 1
fi

if [[ -z "${WORK_DIR}" ]]; then
  log "Error: WORK_DIR is empty"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Collect files to convert into an array 'files'
typeset -a files
if (( $# > 0 )); then
  # Remaining args are treated as files (shell usually expands globs before calling)
  for arg in "$@"; do
    if [[ -e "$arg" ]]; then
      files+=("$arg")
    else
      log "Warning: specified file not found: $arg"
    fi
  done
else
  # Find all .html/.htm files recursively under WORK_DIR (preserve relative paths)
  while IFS= read -r -d $'\0' f; do
    files+=("$f")
  done < <(find "$WORK_DIR" -type f \( -iname '*.html' -o -iname '*.htm' \) -print0)
fi

if (( ${#files[@]} == 0 )); then
  log "No HTML/HTM files found to convert. Exiting."
  exit 0
fi

log "Found ${#files[@]} files to convert. Starting conversion..."

for src in "${files[@]}"; do
  if [[ ! -f "$src" ]]; then
    log "Skipping non-file: $src"
    continue
  fi

  # Compute relative path to WORK_DIR to preserve directory structure
  relpath="${src#${WORK_DIR}/}"
  if [[ "$relpath" == "$src" ]]; then
    # src is not under WORK_DIR (user passed absolute path outside workdir)
    rel_dir="."
  else
    rel_dir="$(dirname "$relpath")"
  fi

  mkdir -p "$OUTPUT_DIR/$rel_dir"

  base="$(basename "$src")"
  name="${base%.*}"
  out="${OUTPUT_DIR}/${rel_dir}/${name}.md"

  log "Converting: $src -> $out"
  
  # Get input file size for validation
  src_size=$(stat -f%z "$src" 2>/dev/null || stat -c%s "$src" 2>/dev/null || echo "0")
  
  # Detect if this is a JATS/PMC XML file (common for PubMed Central articles)
  input_format="html"
  if head -5 "$src" | grep -q "pmc-articleset\|jats\|article xmlns"; then
    input_format="jats"
    log "Detected JATS/PMC XML format for $src"
  fi
  
  # Run pandoc with fail-if-warnings for stricter error handling
  if ! pandoc -f "$input_format" -t gfm --fail-if-warnings -o "$out" "$src" 2>/dev/null; then
    # Try again without --fail-if-warnings in case warnings are acceptable
    log "Warning: pandoc reported warnings for $src, attempting without strict mode..."
    if ! pandoc -f "$input_format" -t gfm -o "$out" "$src"; then
      log "Error: pandoc failed for $src"
      continue
    fi
  fi
  
  # Validate output file exists and has content
  if [[ ! -f "$out" ]]; then
    log "Error: output file not created for $src"
    continue
  fi
  
  out_size=$(stat -f%z "$out" 2>/dev/null || stat -c%s "$out" 2>/dev/null || echo "0")
  
  if (( out_size == 0 )); then
    log "Error: output file is empty for $src"
    continue
  fi
  
  # Check if output is suspiciously small (less than 10% of input size)
  # This often indicates conversion issues with complex HTML
  if (( src_size > 0 )); then
    ratio=$((out_size * 100 / src_size))
    if (( ratio < 10 )); then
      log "Warning: output file ($out_size bytes) is suspiciously small compared to input ($src_size bytes) for $src"
      log "Warning: conversion may be incomplete - please verify $out manually"
    fi
  fi
  
  # Count lines to ensure we have substantial content
  line_count=$(wc -l < "$out" | tr -d ' ')
  if (( line_count < 50 )); then
    log "Warning: output file has very few lines ($line_count) for $src - conversion may be incomplete"
  elif (( line_count < 100 )); then
    log "Info: output file has $line_count lines for $src (typical files have 400+)"
  fi

  # Remove bibliography / references section: find first line that begins with
  # References, Reference, Bibliography, or Literature Cited (case-insensitive),
  # possibly preceded by heading marks (e.g. '## References') and truncate the
  # file at that point so citations are not printed in the Markdown output.
  match=$(grep -niE '^[[:space:]]*(#+[[:space:]]*)?(References|Reference|Bibliography|Literature Cited)\b' "$out" | head -n1 | cut -d: -f1 || true)
  if [[ -n "$match" ]]; then
    log "Truncating bibliography from $out at line $match"
    tmp=$(mktemp "${TMPDIR:-/tmp}/pandoc_md.XXXXXX")
    if (( match > 1 )); then
      head -n $((match - 1)) "$out" > "$tmp"
    else
      : > "$tmp"
    fi
    mv "$tmp" "$out"
  fi
done

log "Conversion complete. Markdown files written to: $OUTPUT_DIR"
