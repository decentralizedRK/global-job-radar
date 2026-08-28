#!/usr/bin/env python3
"""
Main orchestrator for the job search automation.
Runs all scrapers, deduplicates, scores, filters, and notifies.
"""
import sys
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config_loader import load_config
from scraper_linkedin import run_linkedin_search
from scraper_indeed import run_indeed_search
from scraper_naukri import run_naukri_search
from scraper_careers import run_careers_search
from scraper_glassdoor import run_glassdoor_search
from scraper_wellfound import run_wellfound_search
from scraper_builtin import run_builtin_search
from scraper_google_jobs import run_google_jobs_search
from results_tracker import (
    deduplicate_jobs,
    filter_jobs,
    merge_and_track,
    get_top_matches,
    generate_latest_matches,
)
from notifier import notify_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


SCRAPERS = {
    "linkedin": ("LinkedIn", run_linkedin_search),
    "indeed": ("Indeed", run_indeed_search),
    "naukri": ("Naukri", run_naukri_search),
    "careers": ("Company Career Pages", run_careers_search),
    "glassdoor": ("Glassdoor", run_glassdoor_search),
    "wellfound": ("Wellfound", run_wellfound_search),
    "builtin": ("BuiltIn", run_builtin_search),
    "google_jobs": ("Google Jobs + Aggregators", run_google_jobs_search),
}

ALL_SOURCES = list(SCRAPERS.keys())


def run_search(sources=None, notify=True):
    config = load_config()
    active_sources = sources or ALL_SOURCES
    all_jobs = []

    logger.info(f"Starting job search across: {', '.join(active_sources)}")

    for source_key in active_sources:
        if source_key not in SCRAPERS:
            logger.warning(f"Unknown source: {source_key}, skipping")
            continue
        label, search_fn = SCRAPERS[source_key]
        logger.info(f"--- Searching {label} ---")
        try:
            jobs = search_fn(config)
            all_jobs.extend(jobs)
            logger.info(f"{label}: {len(jobs)} results")
        except Exception as e:
            logger.error(f"{label} search failed: {e}")

    logger.info(f"Total raw results: {len(all_jobs)}")

    unique_jobs = deduplicate_jobs(all_jobs)
    logger.info(f"After deduplication: {len(unique_jobs)}")

    filtered_jobs = filter_jobs(unique_jobs, config)
    logger.info(f"After filtering: {len(filtered_jobs)}")

    data = merge_and_track(filtered_jobs, config)

    top_matches = get_top_matches(data, min_score=25, limit=50)
    logger.info(f"Top matches (score >= 25): {len(top_matches)}")

    generate_latest_matches(data, config)

    if notify:
        new_matches = [j for j in top_matches if j.get("seen_count", 0) <= 1]
        if new_matches:
            notify_all(new_matches, data["metadata"], config)
        else:
            logger.info("No new matches to notify about")

    logger.info("Search run complete!")
    return data


def main():
    parser = argparse.ArgumentParser(description="Automated Job Search for TPM/AI PM Roles at Global MNCs")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=ALL_SOURCES,
        default=None,
        help="Which sources to search (default: all)",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Skip notifications",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config file",
    )

    args = parser.parse_args()
    run_search(sources=args.sources, notify=not args.no_notify)


if __name__ == "__main__":
    main()
