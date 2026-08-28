"""
LinkedIn job search via public search URLs (no login required).
Uses the Google X-Ray search method to find LinkedIn job postings.
Falls back to LinkedIn's public job search API-like endpoints.
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

LINKEDIN_JOB_SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def build_linkedin_url(query: str, location: str = "India", page: int = 0) -> str:
    params = {
        "keywords": query,
        "location": location,
        "f_TPR": "r604800",  # past week
        "position": 1,
        "pageNum": page,
        "start": page * 25,
    }
    return f"{LINKEDIN_JOB_SEARCH_URL}?{urllib.parse.urlencode(params)}"


def build_google_xray_url(query: str) -> str:
    xray_query = f'site:linkedin.com/jobs/view "{query}" India'
    return f"https://www.google.com/search?q={urllib.parse.quote(xray_query)}&num=20"


def scrape_linkedin_public(query: str, location: str = "India") -> List[JobListing]:
    jobs = []
    url = build_linkedin_url(query, location)
    logger.info(f"Searching LinkedIn: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        job_cards = soup.find_all("div", class_=re.compile(r"base-card|job-search-card"))
        for card in job_cards:
            title_el = card.find("h3", class_=re.compile(r"base-search-card__title"))
            company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
            location_el = card.find("span", class_=re.compile(r"job-search-card__location"))
            link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
            date_el = card.find("time")

            if not title_el or not company_el:
                continue

            job = JobListing(
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True),
                location=location_el.get_text(strip=True) if location_el else location,
                url=link_el["href"].split("?")[0] if link_el else "",
                source="linkedin",
                posted_date=date_el.get("datetime", "") if date_el else "",
            )
            jobs.append(job)

        logger.info(f"Found {len(jobs)} jobs from LinkedIn for query: {query}")
    except requests.RequestException as e:
        logger.warning(f"LinkedIn request failed: {e}")

    return jobs


def scrape_google_xray(query: str) -> List[JobListing]:
    jobs = []
    url = build_google_xray_url(query)
    logger.info(f"Google X-Ray search: {query}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for result in soup.find_all("div", class_="g"):
            link_el = result.find("a")
            title_el = result.find("h3")
            snippet_el = result.find("span", class_=re.compile(r"aCOpRe|st"))

            if not link_el or not title_el:
                continue

            href = link_el.get("href", "")
            if "linkedin.com/jobs/view" not in href:
                continue

            raw_title = title_el.get_text(strip=True)
            parts = raw_title.split(" - ")
            title = parts[0] if parts else raw_title
            company = parts[1] if len(parts) > 1 else "Unknown"
            location_text = parts[2] if len(parts) > 2 else "India"

            job = JobListing(
                title=title,
                company=company,
                location=location_text,
                url=href.split("?")[0],
                source="linkedin_xray",
                description=snippet_el.get_text(strip=True) if snippet_el else "",
            )
            jobs.append(job)

    except requests.RequestException as e:
        logger.warning(f"Google X-Ray search failed: {e}")

    return jobs


def run_linkedin_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    queries = get_search_queries(config, "linkedin")
    all_jobs = []

    for query in queries:
        jobs = scrape_linkedin_public(query)
        all_jobs.extend(jobs)
        time.sleep(3)

        xray_jobs = scrape_google_xray(query)
        all_jobs.extend(xray_jobs)
        time.sleep(5)

    logger.info(f"Total LinkedIn jobs found: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_linkedin_search()
    for job in results:
        print(job.to_json())
