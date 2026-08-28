"""
Google Jobs meta-aggregator scraper.
Searches Google's job listing cards which aggregate from multiple boards.
Also covers SimplyHired, ZipRecruiter, and other boards indexed by Google.
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

AGGREGATOR_SITES = [
    "simplyhired.com",
    "ziprecruiter.com",
    "monster.com",
    "shine.com",
    "foundit.in",
    "instahyre.com",
    "hirist.tech",
    "cutshort.io",
    "toptal.com/talent",
    "turing.com/jobs",
    "remoteok.com",
    "weworkremotely.com",
    "flexjobs.com",
    "ai-jobs.net",
]


def scrape_google_jobs(query: str, location: str = "India") -> List[JobListing]:
    jobs = []
    search_query = f"{query} jobs {location}"
    url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}&ibp=htl;jobs&num=20"
    logger.info(f"Google Jobs search: {query} ({location})")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.find_all("div", class_=re.compile(r"BjJfJf|PwjeAc|gws-plugins")):
            title_el = card.find("div", class_=re.compile(r"BjJfJf|vNEEBe"))
            company_el = card.find("div", class_=re.compile(r"vNEEBe|nJlDiv"))
            location_el = card.find("div", class_=re.compile(r"Qk80Jf|nJlDiv"))

            if not title_el:
                continue

            job = JobListing(
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else location,
                url=url,
                source="google_jobs",
            )
            jobs.append(job)

    except requests.RequestException as e:
        logger.warning(f"Google Jobs search failed: {e}")

    return jobs


def scrape_aggregator_xray(query: str, site: str) -> List[JobListing]:
    jobs = []
    xray_query = f'site:{site} "{query}" India'
    url = f"https://www.google.com/search?q={urllib.parse.quote(xray_query)}&num=10"
    logger.info(f"Aggregator X-Ray ({site}): {query}")

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
            if site not in href:
                continue

            raw_title = title_el.get_text(strip=True)
            parts = raw_title.split(" - ")
            title = parts[0] if parts else raw_title
            company = parts[1] if len(parts) > 1 else "Unknown"

            source_name = site.split(".")[0]

            job = JobListing(
                title=title,
                company=company,
                location="India",
                url=href.split("?")[0],
                source=source_name,
                description=snippet_el.get_text(strip=True) if snippet_el else "",
            )
            jobs.append(job)

    except requests.RequestException as e:
        logger.warning(f"Aggregator X-Ray ({site}) failed: {e}")

    return jobs


def run_google_jobs_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    queries = get_search_queries(config, "google_jobs")
    all_jobs = []

    for query in queries:
        jobs = scrape_google_jobs(query)
        all_jobs.extend(jobs)
        time.sleep(3)

    ai_queries = [q for q in queries if any(kw in q.lower() for kw in ["ai", "ml", "genai", "remote"])]
    if not ai_queries:
        ai_queries = queries[:3]

    for query in ai_queries:
        for site in AGGREGATOR_SITES:
            jobs = scrape_aggregator_xray(query, site)
            all_jobs.extend(jobs)
            time.sleep(3)

    logger.info(f"Total Google Jobs + aggregator results: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_google_jobs_search()
    for job in results:
        print(job.to_json())
