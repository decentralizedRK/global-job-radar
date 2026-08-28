# Global Job Radar

Automated job search pipeline targeting **Tech Program Manager / Delivery Manager roles at global MNCs with India operations** — with **priority scoring for Japanese companies** and expat/cross-border roles offering 1 Cr+ INR compensation.

Runs on **GitHub Actions** on a schedule, scrapes multiple job boards, scores matches by company tier, deduplicates, and notifies via GitHub Issues / Slack / Telegram.

## What It Searches For

- **Roles:** Tech Program Manager, Engineering Program Manager, AI/ML Program Manager, GenAI Program Manager, Delivery Manager, Program Director, Engagement Manager, Expat Manager, Client Partner
- **Companies:** 80+ global companies across 4 priority tiers
- **Location:** Bangalore, Mumbai, Hyderabad, Pune, Delhi NCR, Chennai, Remote/WFH
- **Signals:** Expat assignments, cross-border roles, global mobility, relocation packages, seniority, compensation, AI/ML focus

## Company Tiers

| Tier | Origin | Priority Score | Examples |
|------|--------|---------------|----------|
| **Tier 1** | Japanese (Priority) | +30 | Rakuten, Sony, NTT Data, Fujitsu, Hitachi, Nomura, Toyota, SoftBank, Mercari |
| **Tier 2** | US / Global Tech | +20 | Google, Microsoft, Amazon, Meta, Apple, Netflix, Goldman Sachs, Stripe |
| **Tier 3** | European | +18 | SAP, Siemens, Mercedes-Benz, Bosch, HSBC, Deutsche Bank, Ericsson |
| **Tier 4** | Korean / Asian | +15 | Samsung, LG, Hyundai, Grab, ByteDance |

## Architecture

```
┌─────────────────────────────────────────────────┐
│              GitHub Actions (cron)               │
│  job_search.yml   │   company_monitor.yml        │
└────────┬──────────┴──────────┬───────────────────┘
         │                     │
         ▼                     ▼
┌────────────────┐  ┌──────────────────────┐
│   main.py      │  │  Direct Careers      │
│  orchestrator  │  │  Page Monitor        │
└───┬──┬──┬──┬───┘  └──────────────────────┘
    │  │  │  │
    ▼  ▼  ▼  ▼
┌──────┐┌──────┐┌──────┐┌─────────┐
│Linked││Indeed││Naukri││Careers  │
│  In  ││      ││      ││ Pages   │
└──┬───┘└──┬───┘└──┬───┘└────┬────┘
   │       │       │         │
┌──┴───┐┌──┴───┐┌──┴──────┐┌─┴──────┐
│Glass ││Well- ││BuiltIn  ││Google  │
│door  ││found ││         ││Jobs +  │
│      ││      ││         ││Aggr.   │
└──┬───┘└──┬───┘└────┬────┘└───┬────┘
   │       │         │         │
   └───────┴─────────┴─────────┘
           │
           ▼
   ┌───────────────┐
   │ Deduplication  │
   │ + Tier Scoring │
   │ + Filtering    │
   └───────┬───────┘
           │
           ▼
   ┌───────────────┐
   │  Notify:        │
   │  - GH Issues    │
   │  - Telegram     │
   │  - Slack         │
   │  - MD Report     │
   └────────────────┘
```

## Setup

### 1. Clone and Install

```bash
git clone <this-repo>
cd global-job-radar
pip install -r requirements.txt
```

### 2. Configure Search Criteria

Edit [config/search_config.yaml](config/search_config.yaml) to customize:
- Title keywords and role types
- Target companies and tiers
- Location preferences
- Salary filters
- Notification channels

### 3. GitHub Secrets (Optional)

| Secret | Purpose |
|--------|---------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for notifications |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Telegram chat/group ID for notifications |

### 4. Enable GitHub Actions

The workflows run automatically:
- **Job Search:** Twice daily (6 AM / 6 PM IST)
- **Company Monitor:** Monday & Thursday (8 AM IST)

Trigger manually from the Actions tab anytime.

## Local Run

```bash
cd scripts && python main.py                              # all 8 sources
python main.py --sources linkedin naukri glassdoor         # specific sources
python main.py --sources builtin wellfound google_jobs     # AI/startup focused
python main.py --no-notify                                 # skip notifications
```

### Sources

| Source | Type | Coverage |
|--------|------|----------|
| **LinkedIn** | Traditional | Public listings + Google X-Ray |
| **Indeed** | Traditional | India job listings |
| **Naukri** | India-focused | Primary India board |
| **Glassdoor** | Traditional | Listings via Google X-Ray |
| **Wellfound** | Startup/Tech | AngelList Talent, startup roles |
| **BuiltIn** | Tech/AI | Tech & AI-focused listings |
| **Google Jobs** | Meta-aggregator | Aggregates SimplyHired, ZipRecruiter, Monster, Shine, Foundit, Instahyre, Hirist, CutShort, RemoteOK, WeWorkRemotely, FlexJobs, AI-Jobs.net, Toptal, Turing |
| **Careers** | Direct | 80+ company career pages |

## Match Scoring (0–100)

| Signal | Points |
|--------|--------|
| Title keyword match | +20 |
| India location match | +15 |
| Tier 1 Japanese company | **+30** |
| Tier 2 US/Global company | +20 |
| Tier 3 European company | +18 |
| Tier 4 Korean/Asian company | +15 |
| Expat/cross-border signal | +20 |
| Seniority signal | +10 |
| Salary signal | +10 |
| Culture signal | +5 each |

## Results

- `results/latest_matches.json` — Top scored matches from latest run
- `results/all_results.json` — Full historical database
- `results/REPORT.md` — Human-readable markdown report
- GitHub Issues — Auto-created for new high-score matches

## Limitations

- Public scraping only — no LinkedIn login/API (avoids ToS issues)
- Rate-limited to avoid blocks (3-5s delays between requests)
- Google X-Ray searches may hit CAPTCHAs at high volume
- Salary data is often not disclosed on listings
- Results depend on job board HTML structure (may need selector updates)

## License

MIT
