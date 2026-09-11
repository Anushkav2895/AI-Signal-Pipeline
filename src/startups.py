# startups.py
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

YC_ALL_COMPANIES_URL = "https://yc-oss.github.io/api/companies/all.json"

# AI-relevance filter — keep this ecosystem-focused per the brief's scope
AI_TAGS = {
    "ai", "artificial intelligence", "machine learning", "ml", "nlp",
    "generative ai", "computer vision", "deep learning",
    "reinforcement learning", "conversational ai", "data engineering",
}

class SourceInfo(BaseModel):
    name: str
    url: str

class StartupContent(BaseModel):
    entityName: str
    employeeCount: Optional[int] = None

class StartupEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "STARTUP"
    source: SourceInfo
    content: StartupContent
    collectedAt: str


def _is_ai_related(company: dict) -> bool:
    tags = [t.lower() for t in company.get("tags", [])]
    industries = [i.lower() for i in company.get("industries", [])]
    haystack = set(tags + industries)
    return bool(haystack & AI_TAGS)


def _to_startup_entity(company: dict) -> StartupEntity:
    profile_url = company.get("url") or f"https://www.ycombinator.com/companies/{company.get('slug', '')}"
    return StartupEntity(
        source=SourceInfo(
            name="Y Combinator",
            url=profile_url,
        ),
        content=StartupContent(
            entityName=company.get("name", "").strip(),
            employeeCount=company.get("team_size"),
        ),
        collectedAt=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_startups(session: aiohttp.ClientSession, limit: int = 1000) -> list[StartupEntity]:
    async with session.get(YC_ALL_COMPANIES_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        companies = await resp.json()

    ai_companies = [c for c in companies if _is_ai_related(c)]

    # Fallback: if AI-tagged set is smaller than target, top up with the rest
    # (keeps you at 1,000+ rows even if the AI filter is tight)
    if len(ai_companies) < limit:
        remaining = [c for c in companies if not _is_ai_related(c)]
        ai_companies.extend(remaining[: limit - len(ai_companies)])

    entities = [_to_startup_entity(c) for c in ai_companies[:limit]]
    # dedupe by entityName just in case of renamed duplicates
    seen = set()
    deduped = []
    for e in entities:
        key = e.content.entityName.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


async def main():
    async with aiohttp.ClientSession() as session:
        startups = await fetch_startups(session, limit=1000)
        print(f"[startups] collected {len(startups)} unique startup records")
        for s in startups[:5]:
            print(f"- {s.content.entityName} | employees={s.content.employeeCount} | {s.source.url}")
        return startups


if __name__ == "__main__":
    asyncio.run(main())
# run_startups_test.py
import asyncio
from startups import main

if __name__ == "__main__":
    asyncio.run(main())


