import asyncio
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import aiohttp
import feedparser
from pydantic import BaseModel

FRESHNESS_WINDOW = timedelta(hours=24)

AI_KEYWORDS_PATTERN = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|llm|nlp|data scientist)\b",
    re.IGNORECASE,
)

REMOTEOK_API = "https://remoteok.com/api"

WWR_FEEDS = [
    ("We Work Remotely - Programming", "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
    ("We Work Remotely - Data", "https://weworkremotely.com/categories/remote-data-jobs.rss"),
    ("We Work Remotely - DevOps & Sysadmin", "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"),
    ("We Work Remotely - Full-Stack", "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"),
]


class SourceInfo(BaseModel):
    name: str
    url: str


class JobContent(BaseModel):
    company: str
    date: str
    is_remote: bool
    role_family: str


class JobEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "JOB"
    source: SourceInfo
    content: JobContent
    collectedAt: str


def _is_ai_related(text: str) -> bool:
    return bool(AI_KEYWORDS_PATTERN.search(text))


def _infer_role_family(title: str) -> str:
    lowered = title.lower()
    if any(k in lowered for k in ("data scientist", "ml engineer", "machine learning", "ai engineer")):
        return "AI/ML Engineering"
    if any(k in lowered for k in ("backend", "frontend", "full-stack", "full stack", "software engineer")):
        return "Engineering"
    if any(k in lowered for k in ("devops", "sre", "infrastructure")):
        return "DevOps"
    if any(k in lowered for k in ("data engineer", "analytics")):
        return "Data Engineering"
    return "Other"


async def _fetch_remoteok(session: aiohttp.ClientSession) -> list[JobEntity]:
    entities = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Signal-Pipeline/1.0)"}
    try:
        async with session.get(REMOTEOK_API, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json(content_type=None)
    except Exception as e:
        print(f"[jobs] failed to fetch RemoteOK: {e}")
        return entities

    now = datetime.now(timezone.utc)

    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue

        title = item.get("position", "") or item.get("title", "")
        description = item.get("description", "")
        combined = f"{title} {description}"
        if not _is_ai_related(combined):
            continue

        date_str = item.get("date")
        if not date_str:
            continue
        try:
            pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if now - pub_date > FRESHNESS_WINDOW:
            continue

        entities.append(
            JobEntity(
                source=SourceInfo(name="RemoteOK", url=item.get("url", "https://remoteok.com")),
                content=JobContent(
                    company=item.get("company", "").strip(),
                    date=pub_date.isoformat(),
                    is_remote=True,
                    role_family=_infer_role_family(title),
                ),
                collectedAt=now.isoformat(),
            )
        )

    return entities


async def _fetch_wwr_feed(session: aiohttp.ClientSession, source_name: str, feed_url: str) -> list[JobEntity]:
    entities = []
    try:
        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            raw = await resp.text()
    except Exception as e:
        print(f"[jobs] failed to fetch {source_name}: {e}")
        return entities

    parsed = feedparser.parse(raw)
    now = datetime.now(timezone.utc)

    for entry in parsed.entries:
        title = entry.get("title", "")
        description = entry.get("summary", "")
        combined = f"{title} {description}"
        if not _is_ai_related(combined):
            continue

        raw_date = entry.get("published")
        if not raw_date:
            continue
        try:
            pub_date = parsedate_to_datetime(raw_date)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            pub_date = pub_date.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue

        if now - pub_date > FRESHNESS_WINDOW:
            continue

        company = title.split(":")[0].strip() if ":" in title else "Unknown"

        entities.append(
            JobEntity(
                source=SourceInfo(name=source_name, url=entry.get("link", feed_url)),
                content=JobContent(
                    company=company,
                    date=pub_date.isoformat(),
                    is_remote=True,
                    role_family=_infer_role_family(title),
                ),
                collectedAt=now.isoformat(),
            )
        )

    return entities


async def fetch_jobs(session: aiohttp.ClientSession) -> list[JobEntity]:
    tasks = [_fetch_remoteok(session)]
    tasks += [_fetch_wwr_feed(session, name, url) for name, url in WWR_FEEDS]
    results = await asyncio.gather(*tasks)
    all_entities = [entity for batch in results for entity in batch]
    print(f"[jobs] collected {len(all_entities)} AI-related jobs posted within last 24h")
    return all_entities


async def main():
    async with aiohttp.ClientSession() as session:
        jobs = await fetch_jobs(session)
        for j in jobs[:5]:
            print(f"- {j.content.company} | {j.content.role_family} | {j.source.name}")
        return jobs


if __name__ == "__main__":
    asyncio.run(main())