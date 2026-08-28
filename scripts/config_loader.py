import os
import yaml
from pathlib import Path


def load_config(config_path=None):
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "search_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_search_queries(config, platform):
    return config.get("search_queries", {}).get(platform, [])


def get_target_companies(config):
    companies = []
    for tier, company_list in config.get("target_companies", {}).items():
        for company in company_list:
            if isinstance(company, dict):
                company["tier"] = tier
                companies.append(company)
            else:
                companies.append({"name": company, "tier": tier})
    return companies


def get_title_keywords(config):
    return config.get("search_profiles", {}).get("primary", {}).get("title_keywords", [])


def get_location_keywords(config):
    return config.get("search_profiles", {}).get("primary", {}).get("location_keywords", [])


def get_filters(config):
    return config.get("filters", {})


def get_env_var(name, required=False):
    value = os.environ.get(name)
    if required and not value:
        raise EnvironmentError(f"Required environment variable {name} is not set")
    return value
