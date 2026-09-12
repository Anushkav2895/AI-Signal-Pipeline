# AI-Signal-Pipeline

A data ingestion pipeline for an AI/venture ecosystem intelligence graph — scrapes startups, products, research papers, news, and jobs; runs extracted content through a multi-tier LLM fallback chain; resolves entities to canonical names; and writes everything to Google Sheets.

Built as a 3-day trial task. See `architecture.pdf` for the full production-scale design discussion (Scale Strategy, 413/429 handling, Freshness Tracking, Storage Strategy).

## What's Implemented

| Component | Source | Status |
|---|---|---|
| Startups | Y Combinator public companies feed | 1,000 AI-tagged records |
| Products | Product Hunt GraphQL API | 1,000 records |
| Research Papers | HuggingFace Daily Papers (+ GitHub star correlation) | 1,000 records |
| News | RSS feeds across 5 AI news sources | 24h-freshness filtered |
| Jobs | RemoteOK API + WeWorkRemotely RSS | 24h-freshness filtered |
| Entity Resolution | rapidfuzz against a 50-company canonical seed list | Full mapping log |
| LLM Extraction | Gemini Flash → Groq (OSS 120B) → DeepSeek fallback chain | Proven working end-to-end |
| Output | Google Sheets (service account, 6 tabs) | Live |

## Project Structure
src/
├── scrapers/
│ ├── startups.py # YC companies feed
│ ├── products.py # Product Hunt API
│ └── papers.py # HuggingFace Daily Papers + GitHub stars
├── news.py # RSS-based news crawler, 24h freshness
├── jobs.py # RemoteOK + WeWorkRemotely, 24h freshness
├── llm_orchestrator.py # 3-tier LLM fallback + chunking + backoff
├── entity_resolution.py # rapidfuzz canonicalization
├── sheets_writer.py # Writes entity records to Google Sheets
├── schemas.py # Shared pydantic schemas
├── config.py # Environment/config loading
└── utils/ # Shared HTTP client helpers

run_*.py # Individual test runners for each component (project root)
architecture.pdf # Production-scale architecture writeup

## Setup

### 1. Clone and create a virtual environment

```powershell
git clone <repo-url>
cd AI-Signal-Pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in:PH_DEVELOPER_TOKEN= # Product Hunt developer token (api.producthunt.com/v2/oauth/applications)
GEMINI_API_KEY= # aistudio.google.com/apikey
GROQ_API_KEY= # console.groq.com/keys
DEEPSEEK_API_KEY= # platform.deepseek.com/api_keys (requires small prepaid balance)

### 3. Set up the Google Sheets service account

1. Create a Google Cloud project, enable the **Sheets API** and **Drive API**
2. Create a Service Account, generate a JSON key, save it as `service_account.json` in the project root (already gitignored)
3. Create a Google Sheet, share it with the service account's email (`...@<project>.iam.gserviceaccount.com`) as **Editor**
4. Copy the Sheet ID from its URL into `.env`

### 4. Run individual components

```powershell
python run_startups_test.py       # scrape + print startups
python run_products_test.py       # scrape + print products
python run_papers_test.py         # scrape + print papers
python run_llm_test.py            # test the LLM fallback chain
python run_entity_test.py         # run entity resolution + write mapping log
python run_sheets_test.py         # write startups to Google Sheets
python run_sheets_products.py     # write products to Google Sheets
python run_sheets_papers.py       # write papers to Google Sheets
python run_sheets_news.py         # crawl news + write to Google Sheets
python run_sheets_jobs.py         # crawl jobs + write to Google Sheets
```

## Known Limitations & Notes

- **Product pricing model**: Product Hunt's API doesn't expose pricing data directly. `products.py` applies a documented heuristic (topic-tag signals for FREE/open-source, defaulting to FREEMIUM) rather than guessing per-product — see the comment in `_infer_pricing_model()`.
- **Jobs freshness**: job boards post far less frequently than news sources, so a single point-in-time run can legitimately return 0 results if nothing was posted in the last 24 hours. Re-running closer to a high-activity window (or on a recurring schedule in production, per `architecture.pdf`) resolves this.
- **DeepSeek tier**: implemented and wired into the fallback chain, but requires a funded account to test live (free tier returns 402). Gemini and Groq are both confirmed working.
- **Entity resolution seed list**: uses a representative 50-company canonical list per the brief's "mock a small database" allowance, not an exhaustive database.

## Architecture

See `architecture.pdf` for the full writeup covering:
1. Scale strategy for 500,000+ records without code changes
2. 413/429 handling across concurrent LLM extractions
3. Freshness tracking across distributed crawler nodes
4. Storage strategy (PostgreSQL + Neo4j + vector store) at production scale
GOOGLE_SHEET_ID= # the ID from your target Sheet's URL
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
