"""
Phase I: Research paper ingestion via Hugging Face Daily Papers.

Sourced from https://huggingface.co/api/daily_papers?date=YYYY-MM-DD.
Confirmed data floor as of 2026-09-11: papers exist from 2026-08-17
onward; dates before that return an empty list. This floor likely
slides forward as HF's window rolls -- re-verify if paper counts
come up short on a later run.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import AsyncIterator

from src.schemas import ResearchPaperContent, ResearchPaperEntity, Source
from src.utils.http_client import AsyncHttpClient, HttpError

HF_DAILY_PAPERS_API = "https://huggingface.co/api/daily_papers"
CONFIRMED_DATA_FLOOR = date(2026, 8, 17)


def _entity_from_hf_record(record: dict) -> ResearchPaperEntity:
    paper = record["paper"]
    arxiv_id = paper["id"]
    return ResearchPaperEntity(
        source=Source(name="Hugging Face Daily Papers", url=f"https://huggingface.co/papers/{arxiv_id}"),
        content=ResearchPaperContent(
            title=paper.get("title", record.get("title", "")),
            authors=[a.get("name", "") for a in paper.get("authors", []) if a.get("name")],
            paper_url=f"https://arxiv.org/abs/{arxiv_id}",
            github_url=paper.get("githubRepo"),
            github_stars=paper.get("githubStars"),
            published_date=paper.get("publishedAt", record.get("publishedAt", "")),
        ),
    )


async def fetch_daily_papers(client: AsyncHttpClient, *, for_date: date) -> list[dict]:
    params = {"date": for_date.isoformat()}
    try:
        resp = await client.get(HF_DAILY_PAPERS_API, params=params)
    except HttpError:
        return []
    data = resp.json()
    return data if isinstance(data, list) else []


async def iter_hf_papers(client: AsyncHttpClient, *, target_count: int) -> AsyncIterator[dict]:
    """Walks backward day by day from today to CONFIRMED_DATA_FLOOR."""
    yielded = 0
    cursor = date.today()

    while yielded < target_count and cursor >= CONFIRMED_DATA_FLOOR:
        records = await fetch_daily_papers(client, for_date=cursor)
        for record in records:
            yield record
            yielded += 1
            if yielded >= target_count:
                return
        cursor -= timedelta(days=1)
        await asyncio.sleep(0.5)


async def scrape_papers(target_count: int = 1000) -> list[ResearchPaperEntity]:
    """Entry point for Phase I paper ingestion, sourced from HF Daily Papers."""
    results: dict[str, ResearchPaperEntity] = {}

    async with AsyncHttpClient() as client:
        async for record in iter_hf_papers(client, target_count=target_count * 2):
            try:
                entity = _entity_from_hf_record(record)
            except (KeyError, TypeError):
                continue
            results[entity.content.paper_url] = entity
            if len(results) >= target_count:
                break

    collected = len(results)
    window_days = (date.today() - CONFIRMED_DATA_FLOOR).days
    print(f"[papers] collected {collected}/{target_count} unique papers across a {window_days}-day window")
    if collected < target_count:
        print(f"[papers] WARNING: fell short of target by {target_count - collected} -- window may not be deep enough")

    return list(results.values())
