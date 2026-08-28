import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    salary_text: str = ""
    posted_date: str = ""
    company_origin: str = ""
    experience_level: str = ""
    is_expat_role: bool = False
    match_score: float = 0.0
    tags: list = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def id(self):
        raw = f"{self.company}|{self.title}|{self.url}".lower()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self):
        d = asdict(self)
        d["id"] = self.id
        return d

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def compute_match_score(job, config):
    score = 0.0
    title_lower = job.title.lower()
    desc_lower = job.description.lower()
    company_lower = job.company.lower()

    title_keywords = [k.lower() for k in config.get("search_profiles", {}).get("primary", {}).get("title_keywords", [])]
    for kw in title_keywords:
        if kw in title_lower:
            score += 20
            break

    location_keywords = [k.lower() for k in config.get("search_profiles", {}).get("primary", {}).get("location_keywords", [])]
    for kw in location_keywords:
        if kw in job.location.lower():
            score += 15
            break

    tier_scores = {
        "tier1_japanese_priority": 30,
        "tier2_us_global_tech": 20,
        "tier3_european": 18,
        "tier4_korean_asian": 15,
    }
    target_companies = []
    for tier, companies in config.get("target_companies", {}).items():
        for c in companies:
            name = c["name"].lower() if isinstance(c, dict) else c.lower()
            origin = c.get("origin", "").lower() if isinstance(c, dict) else ""
            target_companies.append((name, tier, origin))

    for name, tier, origin in target_companies:
        if name in company_lower:
            score += tier_scores.get(tier, 10)
            if origin == "japan":
                job.company_origin = "Japan"
            break

    expat_signals = ["expat", "relocation", "japan to india", "cross-border",
                     "international assignment", "overseas posting", "global mobility"]
    for signal in expat_signals:
        if signal in desc_lower or signal in title_lower:
            job.is_expat_role = True
            score += 20
            break

    seniority_signals = ["senior", "director", "lead", "principal", "vp",
                         "head of", "chief", "executive"]
    for signal in seniority_signals:
        if signal in title_lower:
            score += 10
            break

    salary_signals = ["1 crore", "1cr", "10000000", "100 lpa", "1,00,00,000",
                      "competitive", "best in industry"]
    for signal in salary_signals:
        if signal in job.salary_text.lower() or signal in desc_lower:
            score += 10
            break

    culture_signals = ["work-life balance", "flexible", "remote", "hybrid",
                       "inclusive", "diversity", "employee-first", "great place to work"]
    for signal in culture_signals:
        if signal in desc_lower:
            score += 5

    job.match_score = min(score, 100)
    return job
