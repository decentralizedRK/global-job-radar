"""
Notification system for new job matches.
Supports GitHub Issues, Slack webhooks, email, and markdown reports.
"""
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from config_loader import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent.parent / "results"


def create_github_issue(matches: List[dict], config: dict):
    if not config.get("notifications", {}).get("github_issues", {}).get("enabled", False):
        return

    if not matches:
        logger.info("No new matches to create issues for")
        return

    labels = config["notifications"]["github_issues"].get("labels", ["job-match"])
    label_args = " ".join(f'--label "{l}"' for l in labels)

    title = f"Job Matches - {datetime.utcnow().strftime('%Y-%m-%d')}"
    body_lines = [
        f"# New Job Matches Found - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**Total matches:** {len(matches)}",
        "",
    ]

    for i, job in enumerate(matches[:15], 1):
        score = job.get("match_score", 0)
        expat = " [EXPAT]" if job.get("is_expat_role") else ""
        body_lines.extend([
            f"## {i}. {job['title']}{expat}",
            f"- **Company:** {job['company']}",
            f"- **Location:** {job['location']}",
            f"- **Source:** {job['source']}",
            f"- **Match Score:** {score}/100",
            f"- **Salary:** {job.get('salary_text', 'Not disclosed')}",
            f"- **Link:** {job.get('url', 'N/A')}",
            "",
        ])

    if len(matches) > 15:
        body_lines.append(f"\n*...and {len(matches) - 15} more matches. See full report in results/latest_matches.json*")

    body = "\n".join(body_lines)
    body_escaped = body.replace('"', '\\"')

    try:
        cmd = f'gh issue create --title "{title}" {label_args} --body "{body_escaped}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info(f"Created GitHub issue: {result.stdout.strip()}")
        else:
            logger.warning(f"Failed to create GitHub issue: {result.stderr}")
    except Exception as e:
        logger.warning(f"GitHub issue creation failed: {e}")


def send_slack_notification(matches: List[dict], config: dict):
    if not config.get("notifications", {}).get("slack", {}).get("enabled", False):
        return

    webhook_url = config["notifications"]["slack"].get("webhook_url")
    if not webhook_url:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("Slack webhook URL not configured")
        return

    import requests

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"New Job Matches - {datetime.utcnow().strftime('%Y-%m-%d')}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Found *{len(matches)}* matching positions"}
        },
    ]

    for job in matches[:5]:
        score = job.get("match_score", 0)
        expat = " :jp: EXPAT" if job.get("is_expat_role") else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{job.get('url', '#')}|{job['title']}>*{expat}\n"
                    f":office: {job['company']} | :round_pushpin: {job['location']} | "
                    f"Score: {score}/100"
                ),
            },
        })

    payload = {"blocks": blocks}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Slack notification sent")
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")


def generate_markdown_report(matches: List[dict], metadata: dict) -> str:
    lines = [
        f"# Job Search Report - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        f"- **Total tracked jobs:** {metadata.get('total_jobs', 0)}",
        f"- **New this run:** {metadata.get('new_this_run', 0)}",
        f"- **Top matches shown:** {len(matches)}",
        f"- **Total search runs:** {metadata.get('total_runs', 0)}",
        "",
        "## Top Matches",
        "",
    ]

    high_score = [j for j in matches if j.get("match_score", 0) >= 60]
    medium_score = [j for j in matches if 30 <= j.get("match_score", 0) < 60]
    low_score = [j for j in matches if j.get("match_score", 0) < 30]

    if high_score:
        lines.append("### High Confidence Matches (60+)")
        lines.append("")
        lines.append("| # | Title | Company | Location | Score | Source | Link |")
        lines.append("|---|-------|---------|----------|-------|--------|------|")
        for i, job in enumerate(high_score, 1):
            expat = " [EXPAT]" if job.get("is_expat_role") else ""
            lines.append(
                f"| {i} | {job['title']}{expat} | {job['company']} | "
                f"{job['location']} | {job.get('match_score', 0)} | "
                f"{job['source']} | [Apply]({job.get('url', '#')}) |"
            )
        lines.append("")

    if medium_score:
        lines.append("### Medium Confidence Matches (30-59)")
        lines.append("")
        lines.append("| # | Title | Company | Location | Score | Source | Link |")
        lines.append("|---|-------|---------|----------|-------|--------|------|")
        for i, job in enumerate(medium_score, 1):
            lines.append(
                f"| {i} | {job['title']} | {job['company']} | "
                f"{job['location']} | {job.get('match_score', 0)} | "
                f"{job['source']} | [Apply]({job.get('url', '#')}) |"
            )
        lines.append("")

    lines.extend([
        "",
        "---",
        f"*Generated by [job-search-automation](https://github.com/) at {datetime.utcnow().isoformat()}*",
    ])

    report = "\n".join(lines)
    report_path = RESULTS_DIR / "REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Report generated: {report_path}")
    return report


def notify_all(matches: List[dict], metadata: dict, config: dict):
    generate_markdown_report(matches, metadata)
    create_github_issue(matches, config)
    send_slack_notification(matches, config)
    logger.info("All notifications sent")
