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


def run_search(sources=None, notify=True):
    config = load_config()
    all_sources = sources or ["linkedin", "indeed", "naukri", "careers"]
    all_jobs = []

    logger.info(f"Starting job search across: {', '.join(all_sources)}")

    if "linkedin" in all_sources:
        logger.info("--- Searching LinkedIn ---")
        try:
            jobs = run_linkedin_search(config)
            all_jobs.extend(jobs)
            logger.info(f"LinkedIn: {len(jobs)} results")
        except Exception as e:
            logger.error(f"LinkedIn search failed: {e}")

    if "indeed" in all_sources:
        logger.info("--- Searching Indeed ---")
        try:
            jobs = run_indeed_search(config)
            all_jobs.extend(jobs)
            logger.info(f"Indeed: {len(jobs)} results")
        except Exception as e:
            logger.error(f"Indeed search failed: {e}")

    if "naukri" in all_sources:
        logger.info("--- Searching Naukri ---")
        try:
            jobs = run_naukri_search(config)
            all_jobs.extend(jobs)
            logger.info(f"Naukri: {len(jobs)} results")
        except Exception as e:
            logger.error(f"Naukri search failed: {e}")

    if "careers" in all_sources:
        logger.info("--- Searching Company Career Pages ---")
        try:
            jobs = run_careers_search(config)
            all_jobs.extend(jobs)
            logger.info(f"Careers: {len(jobs)} results")
        except Exception as e:
            logger.error(f"Careers search failed: {e}")

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
    parser = argparse.ArgumentParser(description="Automated Job Search for Japanese Company Roles in India")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["linkedin", "indeed", "naukri", "careers"],
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
