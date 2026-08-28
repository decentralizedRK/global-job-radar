"""
Indeed job search scraper.
Uses Indeed's public search pages.
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
}

INDEED_BASE = "https://www.indeed.com/jobs"


def build_indeed_url(query: str, location: str = "India", page: int = 0) -> str:
    params = {
        "q": query,
        "l": location,
        "fromage": 7,  # last 7 days
        "start": page * 10,
        "sort": "date",
    }
    return f"{INDEED_BASE}?{urllib.parse.urlencode(params)}"


def scrape_indeed(query: str, location: str = "India", max_pages: int = 3) -> List[JobListing]:
    jobs = []

    for page in range(max_pages):
        url = build_indeed_url(query, location, page)
        logger.info(f"Indeed search page {page + 1}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|cardOutline"))
            if not job_cards:
                job_cards = soup.find_all("td", id=re.compile(r"resultsCol"))

            for card in job_cards:
                title_el = card.find("h2", class_=re.compile(r"jobTitle"))
                if not title_el:
                    title_el = card.find("a", class_=re.compile(r"jcs-JobTitle"))

                company_el = card.find("span", attrs={"data-testid": "company-name"})
                if not company_el:
                    company_el = card.find("span", class_=re.compile(r"companyName"))

                location_el = card.find("div", attrs={"data-testid": "text-location"})
                if not location_el:
                    location_el = card.find("div", class_=re.compile(r"companyLocation"))

                salary_el = card.find("div", class_=re.compile(r"salary-snippet|metadata"))
                snippet_el = card.find("div", class_=re.compile(r"job-snippet"))

                link_el = card.find("a", href=True)
                href = ""
                if link_el:
                    raw_href = link_el.get("href", "")
                    href = f"https://www.indeed.com{raw_href}" if raw_href.startswith("/") else raw_href

                if not title_el:
                    continue

                job = JobListing(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "Unknown",
                    location=location_el.get_text(strip=True) if location_el else location,
                    url=href,
                    source="indeed",
                    salary_text=salary_el.get_text(strip=True) if salary_el else "",
                    description=snippet_el.get_text(strip=True) if snippet_el else "",
                )
                jobs.append(job)

            if not job_cards:
                break
            time.sleep(3)

        except requests.RequestException as e:
            logger.warning(f"Indeed request failed (page {page + 1}): {e}")

    logger.info(f"Found {len(jobs)} jobs from Indeed for query: {query}")
    return jobs


def run_indeed_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    queries = get_search_queries(config, "indeed")
    all_jobs = []

    for query in queries:
        jobs = scrape_indeed(query)
        all_jobs.extend(jobs)
        time.sleep(5)

    logger.info(f"Total Indeed jobs found: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_indeed_search()
    for job in results:
        print(job.to_json())
