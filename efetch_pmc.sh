#!/bin/bash
# pmc_download.sh — download PMC XML for a list of PMIDs by resolving to PMCIDs first

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [ID_FILE] [OUTPUT_DIR]

Download PMC XML files for a list of PMIDs or PMCIDs.

Options:
  --pmcid          Treat ID_FILE as PMCIDs (skip PMID resolution)
  -h, --help       Show this help message

Arguments:
  ID_FILE      Input file with IDs (default: ./candidates_ranked.txt)
               Format: one ID per line, or tab-separated with ID first
  OUTPUT_DIR   Directory for downloaded XML files (default: ./pmc_html)

Environment Variables:
  RATE_DELAY      Seconds between requests (default: 0.34 ~3 req/sec)
  SKIP_HEADER     Skip first N lines of input (default: 1)
  FETCH_TIMEOUT   Timeout per fetch in seconds (default: 30)

Examples:
  $(basename "$0") ./candidates_min4_seeds.txt ./pmc_results
  $(basename "$0") --pmcid ./pmcid_list.txt ./pmc_results
  RATE_DELAY=0.5 $(basename "$0")

EOF
    exit "${1:-0}"
}

[[ "$*" == *"-h"* ]] || [[ "$*" == *"--help"* ]] && usage

set -euo pipefail

# Parse options
USE_PMCID=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pmcid)
            USE_PMCID=1
            shift
            ;;
        *)
            break
            ;;
    esac
done

PMID_FILE="${1:-./candidates_ranked.txt}"  # Input: IDs (PMIDs or PMCIDs)
OUTPUT_DIR="${2:-./pmc_html}"              # Output: directory for XML files
RATE_DELAY="${RATE_DELAY:-0.34}"           # ~3 req/sec without API key
SKIP_HEADER="${SKIP_HEADER:-1}"            # Skip first line of input (default: 1)
FETCH_TIMEOUT="${FETCH_TIMEOUT:-90}"       # Seconds to wait per XML fetch

mkdir -p "$OUTPUT_DIR"

# Function: Sleep that tolerates fractional delays across environments
rate_sleep() {
    local delay="$1"
    # Try native sleep first; if it fails (e.g., fractional unsupported), fallback to integer seconds
    if ! sleep "$delay" 2>/dev/null; then
        local int_delay="${delay%%.*}"
        sleep "${int_delay:-0}" || true
    fi
}

# Function: Resolve PMID to PMCID (writes pipeline output into a variable and echoes it)
resolve_pmid_to_pmcid() {
    local pmid="$1"
    local pmcid_out
    pmcid_out=$(
        elink -db pubmed -id "$pmid" -target pmc 2>/dev/null | \
        efetch -format uid 2>/dev/null || true
    )
    # Take only the first line (if multiple), strip CRs
    pmcid_out="${pmcid_out%%$'\n'*}"
    pmcid_out="${pmcid_out//$'\r'/}"
    printf "%s" "$pmcid_out"
}

# Function: Phase 1 - Map all PMIDs to PMCIDs
phase1_resolve_pmids() {
    local pmid_file="$1"
    local mapping_file="$2"
    local rate_delay="$3"

    echo "[Phase 1] Resolving PMIDs to PMCIDs..." >&2
    : > "$mapping_file"

    # Read PMIDs into an array (portable on macOS Bash 3.2), then iterate.
    local -a pmids
    local line_no=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line_no=$((line_no+1))
        if (( line_no <= SKIP_HEADER )); then
            continue
        fi
        line="${line//$'\r'/}"
        local pmid
        pmid="${line%%$'\t'*}"
        [[ -n "$pmid" ]] && pmids+=("$pmid")
    done < "$pmid_file"

    local processed=0
    for pmid in "${pmids[@]}"; do
        processed=$((processed+1))
        local pmcid
        pmcid=$(resolve_pmid_to_pmcid "$pmid")
        if [[ -n "$pmcid" ]]; then
            printf "%s\t%s\n" "$pmid" "$pmcid" >> "$mapping_file"
            echo "[map] PMID $pmid -> $pmcid" >&2
        else
            echo "[skip] PMID $pmid has no PMC link" >&2
        fi
        rate_sleep "$rate_delay"
    done

    local mapped
    mapped=$(wc -l < "$mapping_file" | tr -d ' ')
    echo "[Phase 1] Processed $processed PMIDs; mapped $mapped" >&2
}

# Function: Phase 2 - Download HTML for mapped PMCIDs
phase2_download_html() {
    local mapping_file="$1"
    local output_dir="$2"
    local rate_delay="$3"

    echo "[Phase 2] Downloading HTML files..." >&2
    local fail_count=0
    local ok_count=0
    local skip_count=0
    local total=0

    while IFS=$'\t' read -r pmid pmcid; do
        [[ -z "$pmcid" ]] && continue
        total=$((total+1))
        local out
        out="$output_dir/${pmcid}.xml"
        
        # Skip if already exists and has content
        if [[ -s "$out" ]]; then
            skip_count=$((skip_count+1))
            if (( skip_count % 50 == 1 )); then
                echo "[skip] $pmcid (already exists) [Progress: $total processed, $ok_count OK, $fail_count failed, $skip_count skipped]" >&2
            fi
            continue
        fi
        
        echo "[$total] Downloading $pmcid (PMID $pmid)..." >&2
        
        # Fetch full format to get complete article content
        # Note: efetch needs "PMC" prefix for pmc database IDs
        efetch -db pmc -id "PMC${pmcid}" -format full > "$out" 2>/dev/null
        
        # Check if file has publisher restriction
        if grep -q "publisher of this article does not allow" "$out" 2>/dev/null; then
            mkdir -p "$output_dir/restricted"
            mv "$out" "$output_dir/restricted/${pmcid}.xml"
            echo "  ⚠ Publisher restriction (moved to restricted/)" >&2
            fail_count=$((fail_count+1))
            rate_sleep "$rate_delay"
            continue
        fi
        
        if [[ -s "$out" ]]; then
            ok_count=$((ok_count+1))
            echo "  ✓ Success" >&2
        else
            echo "  ✗ Failed (empty or timeout)" >&2
            fail_count=$((fail_count+1))
            rm -f "$out"
        fi
        rate_sleep "$rate_delay"
    done < "$mapping_file"

    echo "" >&2
    echo "Done. Success: $ok_count; Failed: $fail_count; Skipped: $skip_count; Total: $total" >&2
}

# Main
mapping_file="$OUTPUT_DIR/.pmid_to_pmcid.txt"

# Phase 1: Skip if using PMCIDs directly or if mapping file already exists with content
if (( USE_PMCID )); then
    echo "[Phase 1] Skipping - using PMCIDs directly" >&2
    # Create a simple mapping file: PMCID -> PMCID (no PMID)
    : > "$mapping_file"
    line_no=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line_no=$((line_no+1))
        if (( line_no <= SKIP_HEADER )); then
            continue
        fi
        line="${line//$'\r'/}"
        pmcid="${line%%$'\t'*}"
        [[ -n "$pmcid" ]] && printf "%s\t%s\n" "$pmcid" "$pmcid" >> "$mapping_file"
    done < "$PMID_FILE"
    mapped=$(wc -l < "$mapping_file" | tr -d ' ')
    echo "[Phase 1] Loaded $mapped PMCIDs" >&2
elif [[ -s "$mapping_file" ]]; then
    mapped=$(wc -l < "$mapping_file" | tr -d ' ')
    echo "[Phase 1] Skipping - using existing mapping file with $mapped entries" >&2
    echo "           (Delete $mapping_file to regenerate)" >&2
else
    phase1_resolve_pmids "$PMID_FILE" "$mapping_file" "$RATE_DELAY"
fi

# Phase 2: Download HTML files
phase2_download_html "$mapping_file" "$OUTPUT_DIR" "$RATE_DELAY"
echo "Mapping file: $mapping_file" >&2
