"""
Wellfound (formerly AngelList Talent) job search scraper.
Targets startup and tech company roles via Google X-Ray.
"""
import re
import time
import logging
import urllib.parse
from typing import List

import requests
from bs4 import BeautifulSoup

from job_model import JobListing
from config_loader import load_config, get_search_queries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_wellfound_via_google(query: str) -> List[JobListing]:
    jobs = []
    xray_query = f'site:wellfound.com/jobs "{query}"'
    url = f"https://www.google.com/search?q={urllib.parse.quote(xray_query)}&num=20"
    logger.info(f"Wellfound X-Ray search: {query}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for result in soup.find_all("div", class_="g"):
            link_el = result.find("a")
            title_el = result.find("h3")
            snippet_el = result.find("span")

            if not link_el or not title_el:
                continue

            href = link_el.get("href", "")
            if "wellfound.com" not in href:
                continue

            raw_title = title_el.get_text(strip=True)
            parts = raw_title.split(" - ")
            title = parts[0] if parts else raw_title
            company = parts[1] if len(parts) > 1 else "Unknown"

            job = JobListing(
                title=title,
                company=company,
                location="India",
                url=href.split("?")[0],
                source="wellfound",
                description=snippet_el.get_text(strip=True) if snippet_el else "",
            )
            jobs.append(job)

    except requests.RequestException as e:
        logger.warning(f"Wellfound X-Ray search failed: {e}")

    return jobs


def run_wellfound_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    queries = get_search_queries(config, "wellfound")
    all_jobs = []

    for query in queries:
        jobs = scrape_wellfound_via_google(query)
        all_jobs.extend(jobs)
        time.sleep(5)

    logger.info(f"Total Wellfound jobs found: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_wellfound_search()
    for job in results:
        print(job.to_json())
