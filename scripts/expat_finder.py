#!/usr/bin/env python3
"""
Expat & professional network finder.
Uses Google X-Ray searches to find LinkedIn profiles of employees
at Japanese/US-headquartered companies who are based in Bangalore.
Targets expats on assignment and professionals at MNC offices.
"""
import hashlib
import json
import logging
import random
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List

import requests
from bs4 import BeautifulSoup

from config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

RESULTS_DIR = Path(__file__).parent.parent / "results"

EXPAT_SIGNALS = [
    "expat", "expatriate", "assignment", "relocated", "relocation",
    "moved to", "based in", "secondment", "on deputation",
    "global mobility", "international assignment",
]

SENIORITY_KEYWORDS = [
    "director", "vp", "vice president", "head of", "chief",
    "senior manager", "general manager", "principal",
    "senior director", "managing director", "partner",
    "program manager", "delivery manager", "engagement manager",
]


def build_xray_query(company: str, origin: str, location: str = "Bangalore") -> List[str]:
    queries = []
    queries.append(
        f'site:linkedin.com/in/ "{company}" "{location}" "{origin}"'
    )
    queries.append(
        f'site:linkedin.com/in/ "{company}" "{location}"'
    )
    if origin.lower() == "japan":
        queries.append(
            f'site:linkedin.com/in/ "{company}" "{location}" ("Japanese" OR "Japan" OR "Tokyo" OR "expat")'
        )
    elif origin.lower() in ("us", "usa"):
        queries.append(
            f'site:linkedin.com/in/ "{company}" "{location}" ("American" OR "USA" OR "expat" OR "relocated")'
        )
    return queries


def google_xray_search(query: str, num: int = 15, max_retries: int = 3) -> List[dict]:
    profiles = []
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={num}"
    logger.info(f"X-Ray: {query[:80]}...")

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = 30 * (2 ** attempt) + random.uniform(5, 15)
                logger.warning(f"Rate limited (429), waiting {wait:.0f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for result in soup.find_all("div", class_="g"):
                link_el = result.find("a")
                title_el = result.find("h3")
                snippet_el = result.find("div", class_=re.compile(r"VwiC3b|IsZvec"))
                if not snippet_el:
                    snippet_el = result.find("span")

                if not link_el or not title_el:
                    continue

                href = link_el.get("href", "")
                if "linkedin.com/in/" not in href:
                    continue

                raw_title = title_el.get_text(strip=True)
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                name, headline = parse_linkedin_title(raw_title)
                if not name:
                    continue

                profile_url = href.split("?")[0]
                pid = hashlib.sha256(profile_url.encode()).hexdigest()[:12]

                profiles.append({
                    "id": pid,
                    "name": name,
                    "headline": headline,
                    "snippet": snippet,
                    "linkedin_url": profile_url,
                })
            break

        except requests.RequestException as e:
            logger.warning(f"Google X-Ray failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(15 * (attempt + 1))

    return profiles


def parse_linkedin_title(raw: str) -> tuple:
    raw = raw.replace(" - LinkedIn", "").replace("| LinkedIn", "").strip()
    separators = [" - ", " – ", " — ", " | "]
    for sep in separators:
        if sep in raw:
            parts = raw.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return raw.strip(), ""


def classify_profile(profile: dict, company: str, origin: str) -> dict:
    combined = f"{profile['headline']} {profile['snippet']}".lower()
    name_lower = profile["name"].lower()

    is_expat = any(sig in combined for sig in EXPAT_SIGNALS)

    if origin.lower() == "japan":
        japanese_name_patterns = bool(re.search(
            r'\b(san|kun|sama)\b|[ぁ-ん]|[ァ-ヴ]|[一-龥]', combined
        ))
        japanese_signals = any(
            kw in combined for kw in ["japanese", "japan", "tokyo", "osaka", "jlpt"]
        )
        is_expat = is_expat or japanese_name_patterns or japanese_signals

    is_senior = any(kw in combined for kw in SENIORITY_KEYWORDS)

    relevance = 0
    if company.lower() in combined or company.lower() in name_lower:
        relevance += 30
    if is_expat:
        relevance += 30
    if is_senior:
        relevance += 20
    if any(loc in combined for loc in ["bangalore", "bengaluru", "india"]):
        relevance += 20

    profile["company"] = company
    profile["company_origin"] = origin
    profile["is_expat"] = is_expat
    profile["is_senior"] = is_senior
    profile["relevance_score"] = min(relevance, 100)

    tags = []
    if is_expat:
        tags.append("expat")
    if is_senior:
        tags.append("senior")
    if origin.lower() == "japan":
        tags.append("japanese-company")
    elif origin.lower() in ("us", "usa"):
        tags.append("us-company")
    profile["tags"] = tags

    return profile


def find_expat_profiles(config: dict) -> List[dict]:
    companies = []
    target_tiers = config.get("expat_network", {}).get(
        "target_tiers", ["tier1_japanese_priority", "tier2_us_global_tech"]
    )
    for tier in target_tiers:
        tier_companies = config.get("target_companies", {}).get(tier, [])
        for c in tier_companies:
            if isinstance(c, dict) and c.get("name"):
                companies.append({
                    "name": c["name"],
                    "origin": c.get("origin", ""),
                    "tier": tier,
                })

    max_companies = config.get("expat_network", {}).get("max_companies", 30)
    companies = companies[:max_companies]

    location = config.get("expat_network", {}).get("location", "Bangalore")
    all_profiles = {}

    logger.info(f"Searching for profiles at {len(companies)} companies in {location}")

    for company in companies:
        queries = build_xray_query(company["name"], company["origin"], location)

        for query in queries[:2]:
            results = google_xray_search(query)
            for profile in results:
                profile = classify_profile(profile, company["name"], company["origin"])
                if profile["id"] not in all_profiles:
                    all_profiles[profile["id"]] = profile
                elif profile["relevance_score"] > all_profiles[profile["id"]]["relevance_score"]:
                    all_profiles[profile["id"]] = profile
            time.sleep(random.uniform(12, 20))

        time.sleep(random.uniform(8, 15))

    profiles = list(all_profiles.values())
    profiles.sort(key=lambda p: p["relevance_score"], reverse=True)

    logger.info(f"Found {len(profiles)} unique profiles ({sum(1 for p in profiles if p['is_expat'])} expats)")
    return profiles


def save_profiles(profiles: List[dict], config: dict):
    existing = load_existing_profiles()

    for p in profiles:
        pid = p["id"]
        if pid in existing["profiles"]:
            old = existing["profiles"][pid]
            p["first_seen"] = old.get("first_seen", datetime.utcnow().isoformat())
            p["seen_count"] = old.get("seen_count", 0) + 1
        else:
            p["first_seen"] = datetime.utcnow().isoformat()
            p["seen_count"] = 1
        p["last_seen"] = datetime.utcnow().isoformat()
        existing["profiles"][pid] = p

    existing["metadata"]["last_run"] = datetime.utcnow().isoformat()
    existing["metadata"]["total_runs"] = existing["metadata"].get("total_runs", 0) + 1
    existing["metadata"]["total_profiles"] = len(existing["profiles"])

    all_path = RESULTS_DIR / "all_profiles.json"
    all_path.parent.mkdir(parents=True, exist_ok=True)
    with open(all_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    top = sorted(
        existing["profiles"].values(),
        key=lambda p: p.get("relevance_score", 0),
        reverse=True,
    )[:100]

    expats = [p for p in top if p.get("is_expat")]
    non_expats = [p for p in top if not p.get("is_expat")]
    ordered = expats + non_expats

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_profiles": len(existing["profiles"]),
        "expat_count": sum(1 for p in existing["profiles"].values() if p.get("is_expat")),
        "companies_covered": len(set(
            p.get("company", "") for p in existing["profiles"].values()
        )),
        "profiles": ordered,
    }

    out_path = RESULTS_DIR / "expat_profiles.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(ordered)} top profiles to {out_path}")
    return output


def load_existing_profiles() -> dict:
    path = RESULTS_DIR / "all_profiles.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"profiles": {}, "metadata": {"total_runs": 0}}


def send_telegram_summary(profiles: List[dict]):
    import os
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    from html import escape

    expats = [p for p in profiles if p.get("is_expat")]
    seniors = [p for p in profiles if p.get("is_senior")]

    lines = [
        f"<b>Expat Network Finder</b>",
        f"Found <b>{len(profiles)}</b> profiles ({len(expats)} expats, {len(seniors)} senior)",
        "",
    ]

    for p in profiles[:8]:
        name = escape(p["name"])
        company = escape(p.get("company", ""))
        headline = escape(p.get("headline", ""))[:80]
        tags = " ".join(f"[{t.upper()}]" for t in p.get("tags", []))
        url = p.get("linkedin_url", "")
        lines.append(f'<a href="{escape(url)}">{name}</a>')
        lines.append(f"   {company} | {headline}")
        if tags:
            lines.append(f"   {tags}")
        lines.append("")

    if len(profiles) > 8:
        lines.append(f"<i>...and {len(profiles) - 8} more</i>")

    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "..."

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Telegram summary sent")
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Find expat profiles at target companies")
    parser.add_argument("--no-notify", action="store_true", help="Skip Telegram notification")
    args = parser.parse_args()

    config = load_config()
    profiles = find_expat_profiles(config)
    result = save_profiles(profiles, config)

    if not args.no_notify and profiles:
        send_telegram_summary(profiles)

    logger.info(f"Done — {result['total_profiles']} total profiles tracked")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    main()
