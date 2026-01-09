#!/usr/bin/env python3
"""
PubMed Iterative Expansion - Python Version

Find new papers similar to a curated set using PubMed elink/efetch.
Ranks candidates by how many seed papers link to them.

Peter L. Morrell - January 2026 - St. Paul, MN
Adapted from Shell script for better data structure handling and maintainability.
"""

import sys
import os
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse
from typing import Dict, List, Set, Tuple, Optional


# ============================================================================
# SEED LISTS AND CONFIGURATION (Lines 94-101 from shell version)
# ============================================================================

INCLUDE_PMIDS = [
    32514106, 38068624, 40399895, 27085183, 29025393, 34240169, 39611775, 27357660,
    31862875, 25641359, 39149812, 27294617, 37019898, 36467269, 25901015, 30044522,
    24967630, 39316046, 30861529, 30950186, 33931610, 31570895, 36266506, 38012346,
    35883045, 33073445, 40186008, 31300020, 22660545, 34497122, 37770615, 34289200,
    39107305, 29983312, 38689695, 35060228, 30318590, 33477542, 35787713, 36862793,
    28473417, 35337259, 31462776, 31366935, 32941604, 36864629, 40269167, 37797086,
    34797710, 35513577, 28256021, 34294107, 33247723, 30384830, 34172741, 30411828,
    39472552, 39325737, 31676863, 36932922, 21980108, 38221758, 26549859, 38414075,
    31298732, 34498072, 38606833, 34980919, 35484301, 38978318, 38809753, 34473873,
    22660546, 34706738, 32422187, 33100219, 40307323, 34493868, 33397978, 30806624,
    40097782, 27301592, 31653677, 32681796, 31570613, 36480621, 35037853, 34806764,
    38150485, 40587577, 29301967, 38991084, 37210585, 31394003, 34106529, 36071507,
    34502156, 38988615, 23984715, 30791928, 33687945, 34786880, 36946261, 30867414,
    35012630, 33878927, 37335936, 36578210, 28087781, 37173729, 40148071, 39496880,
    23793030, 40415256, 30523281, 30858362, 36477175, 39006000, 29736016, 34934047,
    33020633, 27500524, 38504651, 39510980, 34479604, 37253933, 26569124, 32503111,
    37647532, 35154199, 34191029, 28416819, 34272249, 34329481, 39279509, 40651977,
    32973000, 37883717, 35298255, 39906956, 38263403, 31114806, 38069099, 31002209,
    36477810, 33950177, 41206694, 25817433, 38232726, 30217779, 26825293, 29575353,
    40770574, 33139952, 34971791, 39719589, 39945053, 32641831, 38990113, 32794321,
    35527235, 32514036, 27029319, 28530677, 31036963, 34759320, 27707802, 37079743,
    40435003, 36684744, 32341525, 36426120, 29866176, 36435453, 28263319, 38898961,
    36260744, 36415319, 37339133, 38396942, 38755313, 37524773, 36419182, 33846635,
    39187610, 31624088, 36018239, 30472326, 34999019, 38720463, 32377351, 40708030,
    38768215, 27595476, 38033071, 38883333, 31570620, 40098183, 24443444, 33539781,
    34240238, 30573726, 35551309, 35361112, 33430931, 35654976, 38578160, 38479835,
    31676864, 36928772, 31519986, 33144942, 35366022, 39349447, 33106631, 25643055,
    29284515
]

EXCLUDE_PMIDS = [
    29476024, 34828432, 35075727, 29409859, 24760390, 34165082, 23990800, 36546413,
    22231484, 30051843, 37043536, 34354260, 32913300, 32821413, 39634061, 35710823,
    31549477, 33439857, 23267105, 28992310, 35138897, 31048485, 39056474, 27258693,
    33512726, 32969558, 37974527, 36109148, 39582196, 33166746, 30710646, 35152499,
    35676481, 26865341, 38166629, 33973633, 33837962, 16649157, 20345635, 35180846,
    29183772, 35031793, 29018458, 4383925, 4822723, 4978888, 5015928, 5026255,
    5569476, 5646786, 5811809, 5831853, 5853444, 5873934, 6046548, 6162604,
    6169392, 6304691, 6431195, 6523605, 6553533, 6895062, 7247153, 7721174,
    7947771, 7959735, 8428838, 8550333, 9226155, 9541791, 9590452, 9590488,
    9680854, 9821504, 9905331, 9943071, 9979274, 10091845, 11628880
]

MIN_PMID = 21980108  # Exclude older papers


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log(message: str):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def run_command(cmd: List[str], input_text: Optional[str] = None) -> Tuple[str, int]:
    """Run shell command and return stdout and exit code."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=30
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        log(f"Warning: Command timeout: {' '.join(cmd)}")
        return "", 1
    except Exception as e:
        log(f"Error running command: {e}")
        return "", 1


def get_related_pmids(seed_pmid: int) -> List[int]:
    """Get PMIDs of papers related to seed_pmid using elink."""
    try:
        # Use elink to get related articles, then efetch to get UIDs
        elink_cmd = ["elink", "-db", "pubmed", "-id", str(seed_pmid), "-related"]
        stdout, code = run_command(elink_cmd)
        if code != 0 or not stdout:
            return []
        
        efetch_cmd = ["efetch", "-format", "uid"]
        stdout, code = run_command(efetch_cmd, input_text=stdout)
        if code != 0 or not stdout:
            return []
        
        # Parse UIDs from output
        pmids = []
        for line in stdout.strip().split("\n"):
            line = line.strip().strip('"')
            if line and line.isdigit():
                pmids.append(int(line))
        return pmids
    except Exception as e:
        log(f"Warning: Failed to get related PMIDs for {seed_pmid}: {e}")
        return []


def fetch_article_metadata(pmids: List[int]) -> Dict[int, Dict[str, str]]:
    """Fetch article metadata (title, abstract, publication types) for PMIDs."""
    results = {}
    
    if not pmids:
        return results
    
    try:
        # Convert to comma-separated string
        ids = ",".join(str(p) for p in pmids)
        
        # Use efetch with XML format to get detailed metadata
        cmd = [
            "efetch", "-db", "pubmed", "-id", ids, "-format", "xml"
        ]
        stdout, code = run_command(cmd)
        
        if code != 0 or not stdout:
            return results
        
        # Parse XML to extract PMID, Title, Abstract, PublicationTypes
        current_pmid = None
        current_title = ""
        current_abstract = ""
        current_pubtypes = ""
        
        for line in stdout.split("\n"):
            # Extract PMID
            pmid_match = re.search(r"<PMID[^>]*>(\d+)</PMID>", line)
            if pmid_match:
                # Save previous record if exists
                if current_pmid and current_pmid in pmids:
                    results[current_pmid] = {
                        "title": current_title,
                        "abstract": current_abstract,
                        "pubtypes": current_pubtypes
                    }
                current_pmid = int(pmid_match.group(1))
                current_title = ""
                current_abstract = ""
                current_pubtypes = ""
            
            # Extract Title
            title_match = re.search(r"<ArticleTitle>([^<]*)</ArticleTitle>", line)
            if title_match:
                current_title = title_match.group(1)
            
            # Extract Abstract text
            abstract_match = re.search(r"<AbstractText[^>]*>([^<]*)</AbstractText>", line)
            if abstract_match:
                current_abstract += abstract_match.group(1) + " "
            
            # Extract Publication Types
            pubtype_match = re.search(r"<PublicationType[^>]*>([^<]*)</PublicationType>", line)
            if pubtype_match:
                if current_pubtypes:
                    current_pubtypes += ";"
                current_pubtypes += pubtype_match.group(1)
        
        # Save last record
        if current_pmid and current_pmid in pmids:
            results[current_pmid] = {
                "title": current_title,
                "abstract": current_abstract,
                "pubtypes": current_pubtypes
            }
        
        return results
    except Exception as e:
        log(f"Warning: Failed to fetch metadata: {e}")
        return results


def filter_candidates(
    candidates: Dict[int, List[int]],
    require_pos: bool = True,
    assembly_only_exclude: bool = True,
    comparative_boost: float = 1.15
) -> Tuple[Dict[int, List[int]], Dict[int, bool]]:
    """
    Filter candidates based on content criteria.
    
    Returns:
        (filtered_candidates, comparative_hits)
    """
    
    # Regex patterns
    pos_patterns = r"whole[\s\-]?genome|WGS|resequenc"
    neg_patterns = r"0K-exome|targeted|amplicon|panel|GBS|genotyping(\s+by\s+sequencing)?|GenomeStudio|SNP([\s\-]?array)?|microarray|Infinium|Axiom|expression|transcriptome|RNA[\s\-]?seq|mRNA|SSR(s)?|microsatellite|RAD[\s\-]?seq|ddRAD|SLAF|reduced\s+representation|capture|hybrid[\s\-]?capture|chloroplast|mitochondri|mitochondrial\s+genome|plastid|plastome|mitogenome"
    excl_pt = r"Review|Editorial|Letter|Meta-Analysis|News|Comment"
    comparative_patterns = r"variant|polymorphism|SNP|indel|SV|structural\s+variant|copy\s+number|CNV|haplotype|diversity|population|comparative|resequenc|association|GWAS|selection|adaptation|introgression|domestication|pangenome|pan[\s\-]?genome|phylogeny|evolution"
    
    comparative_hits = {}
    pmids_to_process = list(candidates.keys())
    
    # Fetch metadata in batches
    batch_size = 200
    metadata = {}
    for i in range(0, len(pmids_to_process), batch_size):
        batch = pmids_to_process[i:i+batch_size]
        batch_metadata = fetch_article_metadata(batch)
        metadata.update(batch_metadata)
    
    # Filter
    filtered = {}
    removed_count = 0
    
    for pmid, seeds in candidates.items():
        if pmid not in metadata:
            # If we couldn't fetch metadata, keep it anyway
            filtered[pmid] = seeds
            continue
        
        meta = metadata[pmid]
        content = f"{meta['title']} {meta['abstract']}".lower()
        pubtypes = meta['pubtypes'].lower()
        
        # Check comparative patterns
        if re.search(comparative_patterns, content, re.IGNORECASE):
            comparative_hits[pmid] = True
        
        # Exclude assembly-only papers if enabled
        if assembly_only_exclude:
            if re.search(r"(de[\s\-]?novo\s+)?assembly|genome\s+assembly", content, re.IGNORECASE):
                if pmid not in comparative_hits:
                    removed_count += 1
                    continue
        
        # Exclude unwanted publication types
        if pubtypes and re.search(excl_pt, pubtypes, re.IGNORECASE):
            removed_count += 1
            continue
        
        # Exclude if negative patterns present
        if re.search(neg_patterns, content, re.IGNORECASE):
            removed_count += 1
            continue
        
        # Optionally require positive WGS terms
        if require_pos:
            if not re.search(pos_patterns, content, re.IGNORECASE):
                removed_count += 1
                continue
        
        # Passed all filters
        filtered[pmid] = seeds
    
    log(f"Content filter removed {removed_count} candidates not matching WGS criteria")
    return filtered, comparative_hits


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Find new papers similar to a curated set using PubMed elink/efetch"
    )
    parser.add_argument(
        "--output-dir",
        default="pubmed_results",
        help="Output directory for results (default: pubmed_results)"
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Limit number of seed papers to process (for testing)"
    )
    parser.add_argument(
        "--age-beta",
        type=float,
        default=0.3,
        help="Max age penalty: 0-1 (default: 0.3)"
    )
    parser.add_argument(
        "--age-gamma",
        type=float,
        default=0.7,
        help="Age curve exponent (default: 0.7)"
    )
    parser.add_argument(
        "--comparative-boost",
        type=float,
        default=1.15,
        help="Score multiplier for comparative studies (default: 1.15)"
    )
    
    args = parser.parse_args()
    
    # Setup
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    include_set = set(INCLUDE_PMIDS)
    exclude_set = set(EXCLUDE_PMIDS)
    seeds_to_process = INCLUDE_PMIDS[:args.max_seeds] if args.max_seeds else INCLUDE_PMIDS
    
    log("=== PubMed Iterative Expansion ===")
    log(f"Using {len(seeds_to_process)} papers as seeds")
    log(f"Output directory: {output_dir}")
    
    # ========================================================================
    # PHASE 1: Query similar articles for each seed
    # ========================================================================
    log("Querying PubMed (this will take a while)...")
    log("Progress will be shown every 10 papers")
    
    candidate_seeds: Dict[int, List[int]] = defaultdict(list)  # PMID -> [seed_pmids]
    
    for idx, seed in enumerate(seeds_to_process, 1):
        if idx % 10 == 0:
            pct = (idx * 100) // len(seeds_to_process)
            log(f"  Progress: {idx}/{len(seeds_to_process)} ({pct}%)")
        
        related = get_related_pmids(seed)
        
        for pmid in related:
            # Skip if in include or exclude sets
            if pmid in include_set or pmid in exclude_set:
                continue
            # Skip if older than cutoff
            if pmid < MIN_PMID:
                continue
            # Add to candidates
            candidate_seeds[pmid].append(seed)
        
        # Rate limiting
        import time
        time.sleep(0.5)
    
    log(f"Complete: {len(seeds_to_process)}/{len(seeds_to_process)} (100%)")
    
    if not candidate_seeds:
        log("Error: No similar articles found. Check your network connection.")
        sys.exit(1)
    
    log("Processing results...")
    
    # ========================================================================
    # PHASE 2: Calculate raw scores (number of seeds per candidate)
    # ========================================================================
    candidate_scores: Dict[int, int] = {}
    for pmid, seeds in candidate_seeds.items():
        candidate_scores[pmid] = len(seeds)
    
    # ========================================================================
    # PHASE 3: Content filtering
    # ========================================================================
    log("Filtering by content...")
    candidate_seeds, comparative_hits = filter_candidates(
        dict(candidate_seeds)
    )
    candidate_scores = {
        pmid: candidate_scores[pmid]
        for pmid in candidate_seeds.keys()
        if pmid in candidate_scores
    }
    
    # ========================================================================
    # PHASE 4: Apply age weighting and comparative boost
    # ========================================================================
    if not candidate_scores:
        log("Error: No candidates after filtering")
        sys.exit(1)
    
    # Compute min/max PMIDs for age normalization
    max_pmid = max(candidate_scores.keys())
    min_pmid = min(candidate_scores.keys())
    
    weighted_scores: Dict[int, float] = {}
    for pmid, score in candidate_scores.items():
        if max_pmid == min_pmid:
            weighted = float(score)
        else:
            age_norm = (max_pmid - pmid) / (max_pmid - min_pmid)
            weighted = score * (1 - args.age_beta * (age_norm ** args.age_gamma))
        
        # Apply comparative boost if applicable
        if pmid in comparative_hits:
            weighted *= args.comparative_boost
        
        weighted_scores[pmid] = weighted
    
    log(f"Age weighting parameters: AGE_BETA={args.age_beta}, AGE_GAMMA={args.age_gamma}")
    log(f"Comparative boost factor: {args.comparative_boost}")
    
    # ========================================================================
    # PHASE 5: Generate output files and statistics
    # ========================================================================
    max_score = max(candidate_scores.values())
    recommended_threshold = max(2, max_score // 10)
    
    log("")
    log("=== RESULTS ===")
    log(f"Total unique candidate papers found: {len(candidate_seeds)}")
    log("")
    
    # Score distribution
    log("Score Distribution (how many seeds found each candidate):")
    score_counts = defaultdict(int)
    for score in candidate_scores.values():
        score_counts[score] += 1
    
    for score in sorted(score_counts.keys(), reverse=True):
        count = score_counts[score]
        log(f"  {score:3d} seeds: {count:4d} candidates")
    
    log("")
    log(f"Maximum score: {max_score}")
    log(f"Recommended threshold: >={recommended_threshold} (captures high-confidence matches)")
    log("")
    log("=== OUTPUT FILES ===")
    
    # Create threshold files
    for threshold in [2, 3, 5, 10, recommended_threshold]:
        if threshold <= max_score:
            outfile = output_dir / f"candidates_min{threshold}_seeds.txt"
            with open(outfile, "w") as f:
                pmids = [
                    pmid for pmid, score in candidate_scores.items()
                    if score >= threshold
                ]
                for pmid in sorted(pmids):
                    f.write(f"{pmid}\n")
            
            count = len(pmids)
            log(f"  candidates_min{threshold}_seeds.txt: {count} candidates (≥{threshold} seeds)")
    
    # Create ranked list with full details
    ranked_file = output_dir / "candidates_ranked.txt"
    with open(ranked_file, "w") as f:
        f.write("PMID\tScore\tWeightedScore\tSeeds\n")
        
        # Sort by weighted score (desc), then raw score (desc), then PMID (asc)
        sorted_pmids = sorted(
            candidate_scores.keys(),
            key=lambda p: (-weighted_scores[p], -candidate_scores[p], p)
        )
        
        for pmid in sorted_pmids:
            score = candidate_scores[pmid]
            weighted = weighted_scores[pmid]
            seeds = ",".join(str(s) for s in candidate_seeds[pmid])
            f.write(f"{pmid}\t{score}\t{weighted:.6f}\t{seeds}\n")
    
    log(f"  candidates_ranked.txt: All {len(candidate_seeds)} candidates with weighted and raw scores")
    log("")
    
    # Calculate confidence recommendations
    high_conf = sum(1 for s in candidate_scores.values() if s >= recommended_threshold)
    med_conf = sum(1 for s in candidate_scores.values() if 3 <= s < recommended_threshold)
    low_conf = sum(1 for s in candidate_scores.values() if s < 3)
    
    log("=== RECOMMENDATIONS ===")
    log(f"High confidence (≥{recommended_threshold} seeds): {high_conf} papers")
    log("  → START HERE - these are most likely true positives")
    log("")
    log(f"Medium confidence (3-{recommended_threshold-1} seeds): {med_conf} papers")
    log("  → Review these after high confidence papers")
    log("")
    log(f"Low confidence (1-2 seeds): {low_conf} papers")
    log("  → Likely many false positives")
    log("")
    log("Next steps:")
    log(f"  1. Review {output_dir}/candidates_min{recommended_threshold}_seeds.txt")
    log("  2. If you need more papers, lower the threshold")
    log("  3. If you find false positives, raise the threshold")
    log("")
    log(f"Done! Output files are in: {output_dir}")


if __name__ == "__main__":
    main()
