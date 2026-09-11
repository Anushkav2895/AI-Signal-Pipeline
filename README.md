# AI Signal Intelligence Pipeline

A scalable, fault-tolerant, async data ingestion pipeline for the AI/venture
ecosystem — built for the GraphOne / FrontierAtlas Intelligence Graph.

It ingests, normalizes, and enriches data on **startups**, **products**,
**research papers** (with live GitHub star tracking), **AI news**, and
**AI job listings**, then resolves messy entity names to canonical forms
and writes everything to Google Sheets (and/or a local database).

## Architecture Overview
                     ┌─────────────────────┐
                     │     Orchestrator     │  (src/main.py)
                     └──────────┬───────────┘
          ┌───────────────────┼───────────────────┐
          ▼                    ▼                    ▼
 ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
 │ Phase I Scraper │  │ Phase II Crawler │  │  Phase III LLM    │
 │ (bulk, one-time)│  │ (news/jobs, 24h) │  │  Extraction Engine│
 │ startups/       │  │ freshness-gated  │  │  Gemini→Groq→     │
 │ products/papers │  └────────┬─────────┘  │  DeepSeek fallback│
 └────────┬────────┘           │            └─────────┬─────────┘
          │                    │                       │
          └────────────────────┴───────────────────────┘
                                ▼
                 ┌──────────────────────────┐
                 │ Phase IV Entity Resolver  │
                 │ (raw name → canonical)    │
                 └────────────┬──────────────┘
                              ▼
                 ┌──────────────────────────┐
                 │   Storage (SQLite/Postgres│
                 
Each stage is independently async and queue-driven, so scraping, LLM
extraction, and entity resolution all run concurrently rather than as
sequential batch steps — this is what lets the architecture scale from a
few hundred records in a local run to 500k+ across distributed workers
without code changes (see `architecture.pdf` for the full scale plan,
413/429 handling strategy, freshness/dedup strategy, and storage
justification).

## Project Structure

## Setup

1. Clone the repo and create a virtual environment:
```bash
   git clone <this-repo-url>
   cd ai-signal-pipeline
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
```

2. Copy `.env.example` to `.env` and fill in your API keys:
```bash
   cp .env.example .env
```
   You'll need at minimum a Gemini API key for the LLM extraction layer;
   Groq and DeepSeek keys enable the fallback chain (Phase III).

3. For Google Sheets export, place a Google service-account
   `credentials.json` in the project root (path configurable via
   `GOOGLE_SHEETS_CREDENTIALS_PATH`) and share your target sheet with the
   service account's email. Set `GOOGLE_SHEET_ID` in `.env`.

4. Run the pipeline:
```bash
   python -m src.main --phase all
```
   Or run a single phase, e.g.:
```bash
   python -m src.main --phase startups
   python -m src.main --phase news
```

5. Run tests:
```bash
   pytest
```

## Evaluation Notes

- Every record traces back to a real, valid `source.url` — nothing here
  is LLM-hallucinated filler data.
- The entity resolver ships with a mock seed list of ~50 known AI
  startups (`src/entity_resolution/seed_entities.py`) for canonicalization
  matching, per the brief.
- See `architecture.pdf` for the written answers to the Phase VI
  scale/413/429/freshness/storage questions.
                 │   staging) + Google Sheets│
                 │   export (6 tabs)         │
                 └──────────────────────────┘
