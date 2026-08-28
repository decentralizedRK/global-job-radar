"""
Results tracking, deduplication, and persistence.
Stores results as JSON with deduplication by job ID.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from job_model import JobListing, compute_match_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent.parent / "results"


def load_existing_results(filepath=None) -> dict:
    if filepath is None:
        filepath = RESULTS_DIR / "all_results.json"
    if not filepath.exists():
        return {"jobs": {}, "metadata": {"total_runs": 0, "last_run": None}}
    with open(filepath, "r") as f:
        return json.load(f)


def save_results(data: dict, filepath=None):
    if filepath is None:
        filepath = RESULTS_DIR / "all_results.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved results to {filepath}")


def deduplicate_jobs(jobs: List[JobListing]) -> List[JobListing]:
    seen = {}
    for job in jobs:
        job_id = job.id
        if job_id not in seen:
            seen[job_id] = job
        else:
            existing = seen[job_id]
            if len(job.description) > len(existing.description):
                seen[job_id] = job
    return list(seen.values())


def filter_jobs(jobs: List[JobListing], config: dict) -> List[JobListing]:
    filters = config.get("filters", {})
    exclude_keywords = [kw.lower() for kw in filters.get("exclude_keywords", [])]
    require_any = [kw.lower() for kw in filters.get("require_any_keyword", [])]

    filtered = []
    for job in jobs:
        title_lower = job.title.lower()
        desc_lower = job.description.lower()
        combined = f"{title_lower} {desc_lower} {job.company.lower()}"

        if any(kw in title_lower for kw in exclude_keywords):
            continue

        if require_any and not any(kw in combined for kw in require_any):
            continue

        filtered.append(job)

    logger.info(f"Filtered {len(jobs)} -> {len(filtered)} jobs")
    return filtered


def merge_and_track(new_jobs: List[JobListing], config: dict) -> dict:
    existing = load_existing_results()
    new_count = 0

    for job in new_jobs:
        job = compute_match_score(job, config)
        job_dict = job.to_dict()

        if job.id not in existing["jobs"]:
            new_count += 1
            job_dict["first_seen"] = datetime.utcnow().isoformat()
            job_dict["seen_count"] = 1
        else:
            job_dict["first_seen"] = existing["jobs"][job.id].get(
                "first_seen", datetime.utcnow().isoformat()
            )
            job_dict["seen_count"] = existing["jobs"][job.id].get("seen_count", 0) + 1

        job_dict["last_seen"] = datetime.utcnow().isoformat()
        existing["jobs"][job.id] = job_dict

    existing["metadata"]["total_runs"] = existing["metadata"].get("total_runs", 0) + 1
    existing["metadata"]["last_run"] = datetime.utcnow().isoformat()
    existing["metadata"]["total_jobs"] = len(existing["jobs"])
    existing["metadata"]["new_this_run"] = new_count

    save_results(existing)
    return existing


def get_top_matches(data: dict, min_score: float = 30, limit: int = 20) -> List[dict]:
    jobs = list(data["jobs"].values())
    scored = [j for j in jobs if j.get("match_score", 0) >= min_score]
    scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return scored[:limit]


def generate_latest_matches(data: dict, config: dict):
    top = get_top_matches(data, min_score=25, limit=50)
    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_tracked": len(data["jobs"]),
        "top_matches_count": len(top),
        "matches": top,
    }
    filepath = RESULTS_DIR / "latest_matches.json"
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"Generated latest matches report: {filepath}")
    return output
