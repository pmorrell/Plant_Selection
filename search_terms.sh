#!/bin/zsh

setopt errexit nounset pipefail

# Script to search for terms in markdown files and report counts
# Usage: ./search_terms.sh [--dry-run|-n] <directory_with_markdown_files> <terms_file>

log() {
  local msg="$1"
  echo "$(date +'%Y-%m-%d %H:%M:%S') - ${msg}" >&2
}

# Parse optional --dry-run/-n
DRY_RUN=0
if [[ "${1:-}" == "-n" || "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

# Check if required arguments are provided
if [ $# -ne 2 ]; then
  echo "Usage: $0 [--dry-run|-n] <directory_with_markdown_files> <terms_file>" >&2
  echo "" >&2
  echo "Arguments:" >&2
  echo "  directory_with_markdown_files - Directory containing .md files to search" >&2
  echo "  terms_file                    - File containing search terms (one per line)" >&2
  exit 1
fi

MARKDOWN_DIR="$1"
TERMS_FILE="$2"

# Check if directory exists
if [ ! -d "$MARKDOWN_DIR" ]; then
  log "Error: Directory not found: $MARKDOWN_DIR"
  exit 1
fi

# Check if terms file exists
if [ ! -f "$TERMS_FILE" ]; then
  log "Error: Terms file not found: $TERMS_FILE"
  exit 1
fi

# Read search terms from file (one per line) into an array, trimming blanks
log "Reading search terms from: $TERMS_FILE"
SEARCH_TERMS=()
while IFS= read -r line || [[ -n $line ]]; do
  # Trim leading/trailing whitespace
  term="${line##+([[:space:]])}"
  term="${term%%+([[:space:]])}"
  if [[ -n "$term" ]]; then
    SEARCH_TERMS+=("$term")
  fi
done < "$TERMS_FILE"

if [ ${#SEARCH_TERMS[@]} -eq 0 ]; then
  log "Error: No search terms found in $TERMS_FILE"
  exit 1
fi

# Check if directory exists
if [ ! -d "$MARKDOWN_DIR" ]; then
  log "Error: Directory not found: $MARKDOWN_DIR"
  exit 1
fi

# Count total markdown files
TOTAL_FILES=$(find "$MARKDOWN_DIR" -type f -name "*.md" | wc -l | tr -d ' ')

if [ "$TOTAL_FILES" -eq 0 ]; then
  log "Error: No markdown files found in $MARKDOWN_DIR"
  exit 1
fi

log "Searching $TOTAL_FILES markdown files in: $MARKDOWN_DIR"
log "Searching for ${#SEARCH_TERMS[@]} terms"

# Create associative array to store counts (zsh syntax)
typeset -A term_counts

# Search for each term
for term in "${SEARCH_TERMS[@]}"; do
  if (( DRY_RUN )); then
    log "Files matching term: '$term'"
    # Print matching files (unique)
    grep -ril --include="*.md" -F -e "$term" "$MARKDOWN_DIR" 2>/dev/null | sort -u || true
  else
    # Use grep to find files containing the term (case-insensitive, fixed string)
    # Make grep failure non-fatal (no matches -> exit code 1), so append '|| true'
    count=$(grep -ril --include="*.md" -F -e "$term" "$MARKDOWN_DIR" 2>/dev/null | sort -u | wc -l | tr -d ' ' || true)
    if [[ -z "$count" ]]; then
      count=0
    fi
    term_counts[$term]=$count
  fi
done

# Output results in table format
echo ""
echo "Search Results"
echo "============================================"
echo "Total Markdown files searched: $TOTAL_FILES"
echo "============================================"
echo ""
printf "%-40s | %s\n" "Search Term" "Papers Found"
printf "%-40s-+-%s\n" "----------------------------------------" "------------"

# Sort terms by count (descending) and then alphabetically
for term in "${(k)term_counts[@]}"; do
  printf "%s\t%d\n" "$term" "${term_counts[$term]}"
done | sort -t$'\t' -k2,2nr -k1,1 | while IFS=$'\t' read -r term count; do
  printf "%-40s | %12d\n" "$term" "$count"
done

echo ""
log "Search completed"
