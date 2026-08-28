"""
Direct careers page scraper for target Japanese companies.
Checks each company's careers URL for matching positions.
"""
import re
import time
import logging
import urllib.parse
from typing import List

import requests
from bs4 import BeautifulSoup

from job_model import JobListing
from config_loader import load_config, get_target_companies, get_title_keywords

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def search_company_careers(company: dict, title_keywords: List[str]) -> List[JobListing]:
    jobs = []
    careers_url = company.get("careers_url")
    if not careers_url:
        return jobs

    company_name = company["name"]
    logger.info(f"Checking careers page for {company_name}: {careers_url}")

    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("a", href=True)
        for link in links:
            text = link.get_text(strip=True).lower()
            href = link["href"]

            is_match = any(kw.lower() in text for kw in title_keywords)
            india_match = any(loc in text for loc in ["india", "bangalore", "mumbai", "hyderabad", "pune"])

            if is_match or india_match:
                if not href.startswith("http"):
                    href = urllib.parse.urljoin(careers_url, href)

                job = JobListing(
                    title=link.get_text(strip=True),
                    company=company_name,
                    location="India",
                    url=href,
                    source="careers_page",
                    company_origin="Japan",
                    tags=[company.get("tier", "unknown")],
                )
                jobs.append(job)

    except requests.RequestException as e:
        logger.warning(f"Failed to check {company_name} careers page: {e}")

    return jobs


def search_google_for_company(company_name: str, title_keywords: List[str]) -> List[JobListing]:
    jobs = []
    for keyword in title_keywords[:3]:
        query = f'"{company_name}" "{keyword}" India job'
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=10"
        logger.info(f"Google search for {company_name}: {keyword}")

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
                if any(domain in href for domain in ["linkedin.com/jobs", "indeed.com", "naukri.com", "glassdoor.com"]):
                    job = JobListing(
                        title=title_el.get_text(strip=True),
                        company=company_name,
                        location="India",
                        url=href,
                        source="google_company_search",
                        description=snippet_el.get_text(strip=True) if snippet_el else "",
                        company_origin="Japan",
                    )
                    jobs.append(job)

            time.sleep(5)

        except requests.RequestException as e:
            logger.warning(f"Google search failed for {company_name}: {e}")

    return jobs


def run_careers_search(config=None) -> List[JobListing]:
    if config is None:
        config = load_config()

    companies = get_target_companies(config)
    title_keywords = get_title_keywords(config)
    all_jobs = []

    for company in companies:
        jobs = search_company_careers(company, title_keywords)
        all_jobs.extend(jobs)

        google_jobs = search_google_for_company(company["name"], title_keywords)
        all_jobs.extend(google_jobs)

        time.sleep(3)

    logger.info(f"Total careers page jobs found: {len(all_jobs)}")
    return all_jobs


if __name__ == "__main__":
    results = run_careers_search()
    for job in results:
        print(job.to_json())
