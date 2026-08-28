"""
Naukri.com job search scraper.
Primary job board for India-based positions.
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

NAUKRI_BASE = "https://www.naukri.com"


def build_naukri_url(query: str, page: int = 1) -> str:
    slug = query.lower().replace(" ", "-")
    if page > 1:
        return f"{NAUKRI_BASE}/{slug}-jobs-{page}"
    return f"{NAUKRI_BASE}/{slug}-jobs"


def scrape_naukri(query: str, max_pages: int = 3) -> List[JobListing]:
    jobs = []

    for page in range(1, max_pages + 1):
        url = build_naukri_url(query, page)
        logger.info(f"Naukri search page {page}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            job_cards = soup.find_all("article", class_=re.compile(r"jobTuple"))
            if not job_cards:
                job_cards = soup.find_all("div", class_=re.compile(r"srp-jobtuple|cust-job-tuple"))

            for card in job_cards:
                title_el = card.find("a", class_=re.compile(r"title|designation"))
                company_el = card.find("a", class_=re.compile(r"subTitle|comp-name"))
                if not company_el:
                    company_el = card.find("span", class_=re.compile(r"comp-name"))

                location_el = card.find("span", class_=re.compile(r"locWdth|loc-wrap|location"))
                salary_el = card.find("span", class_=re.compile(r"sal|salary"))
                exp_el = card.find("span", class_=re.compile(r"exp|experience"))
                desc_el = card.find("span", class_=re.compile(r"job-desc|ellipsis"))

                if not title_el:
                    continue

                href = title_el.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{NAUKRI_BASE}{href}"

                job = JobListing(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "Unknown",
                    location=location_el.get_text(strip=True) if location_el else "India",
                    url=href,
                    source="naukri",
                    salary_text=salary_el.get_text(strip=True) if salary_el else "",
                    experience_level=exp_el.get_text(strip=True) if exp_el else "",
                    description=desc_el.get_text(strip=True) if desc_el else "",
                )
                jobs.append(job)

            if not job_cards:
                break
            time.sleep(3)

        except requests.RequestException as e:
            logger.warning(f"Naukri request failed (page {page}): {e}")

    logger.info(f"Found {len(jobs)} jobs from Naukri for query: {query}")
    return jobs


def run_naukri_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    queries = get_search_queries(config, "naukri")
    all_jobs = []

    for query in queries:
        jobs = scrape_naukri(query)
        all_jobs.extend(jobs)
        time.sleep(5)

    logger.info(f"Total Naukri jobs found: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_naukri_search()
    for job in results:
        print(job.to_json())
