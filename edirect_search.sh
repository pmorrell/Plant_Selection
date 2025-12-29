#!/bin/bash

# Parse command line arguments
LIST_IDS_ONLY=false
DOWNLOAD_LIMIT=""
OUTPUT_FORMAT="xml"

while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--list-ids)
            LIST_IDS_ONLY=true
            shift
            ;;
        -n|--num)
            DOWNLOAD_LIMIT="$2"
            shift 2
            ;;
        --format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -l, --list-ids    List PubMed IDs only (don't download articles)"
            echo "  -n, --num N       Download only the first N PMC articles"
            echo "      --format F    Output format: xml (default), html, pdf"
            echo "  -h, --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Define the search queries
# PubMed supports field tags like [Publication Type]
SEARCH_QUERY="plant genome resequencing AND whole genome NOT review[Publication Type]"
# PMC is stricter; avoid field tags in PMC query
PMC_QUERY="plant genome resequencing AND whole genome NOT review"

# Optional: Set your NCBI API key for higher rate limits (10 req/sec vs 3 req/sec)
# export NCBI_API_KEY="your_api_key_here"

# If only listing IDs, do that and exit
if [ "$LIST_IDS_ONLY" = true ]; then
    echo "Searching PubMed for articles..." >&2
    esearch -db pubmed -query "$SEARCH_QUERY" | efetch -format uid
    exit 0
fi

# Otherwise, proceed with full download
# Create output directory
mkdir -p html_files

echo "Searching for articles..." >&2

# Get the count first (PMC-safe query)
COUNT=$(esearch -db pmc -query "$PMC_QUERY" | xtract -pattern ENTREZ_DIRECT -element Count)
echo "Found $COUNT articles to download" >&2

# Download PMCIDs using PMC-safe query
echo "Fetching PMC IDs..." >&2
esearch -db pmc -query "$PMC_QUERY" | efetch -format uid > pmcids.txt

# If a download limit is set, truncate the list to the first N IDs
if [[ -n "$DOWNLOAD_LIMIT" ]]; then
    if ! [[ "$DOWNLOAD_LIMIT" =~ ^[0-9]+$ ]]; then
        echo "Error: N must be a positive integer" >&2
        rm -f pmcids.txt
        exit 1
    fi
    echo "Limiting downloads to first $DOWNLOAD_LIMIT articles..." >&2
    head -n "$DOWNLOAD_LIMIT" pmcids.txt > pmcids.firstn.tmp && mv pmcids.firstn.tmp pmcids.txt
    # Update COUNT to reflect limited set
    COUNT=$(wc -l < pmcids.txt | tr -d ' ')
fi

# Counter for progress
CURRENT=0

# Download each article as HTML with rate limiting
while read pmcid; do
    if [ -n "$pmcid" ]; then
        CURRENT=$((CURRENT + 1))
        echo "[$CURRENT/$COUNT] Downloading PMC${pmcid}..." >&2
        
        # Choose output format and fetch accordingly
        case "$OUTPUT_FORMAT" in
            xml)
                # JATS XML full text
                efetch -db pmc -id "PMC${pmcid}" -format xml > "html_files/PMC${pmcid}.xml" 2>/dev/null
                OUTFILE="html_files/PMC${pmcid}.xml"
                ;;
            html)
                # Try full HTML; if empty, fallback to standard html
                efetch -db pmc -id "PMC${pmcid}" -format full -retmode html > "html_files/PMC${pmcid}.html" 2>/dev/null
                if [ ! -s "html_files/PMC${pmcid}.html" ]; then
                    efetch -db pmc -id "PMC${pmcid}" -format html > "html_files/PMC${pmcid}.html" 2>/dev/null
                fi
                OUTFILE="html_files/PMC${pmcid}.html"
                ;;
            pdf)
                # Not all PMCs have PDFs via efetch; attempt fetch
                efetch -db pmc -id "PMC${pmcid}" -format pdf > "html_files/PMC${pmcid}.pdf" 2>/dev/null
                OUTFILE="html_files/PMC${pmcid}.pdf"
                ;;
            *)
                echo "Unknown format: $OUTPUT_FORMAT" >&2
                continue
                ;;
        esac
        
        # Check if download was successful
        if [ $? -eq 0 ] && [ -s "$OUTFILE" ]; then
            echo "  ✓ Success" >&2
        else
            echo "  ✗ Failed" >&2
        fi
        
        # Rate limiting: 3 requests per second without API key
        # Change to 0.1 if you have an API key
        sleep 0.34
    fi
done < pmcids.txt

# Clean up
rm pmcids.txt

echo ""
echo "Download complete! Files saved in html_files/"
echo "Total files: $(ls html_files/*.html 2>/dev/null | wc -l)"