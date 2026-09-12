import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import aiohttp
import feedparser
from pydantic import BaseModel

# 5 AI news sources via RSS -- stable, gives real publish timestamps directly
NEWS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    ("The Verge AI", "https://www.theverge.com/artificial-intelligence/rss/index.xml"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

FRESHNESS_WINDOW = timedelta(hours=24)


class SourceInfo(BaseModel):
    name: str
    url: str


class NewsContent(BaseModel):
    title: str
    full_text: str
    published_date: str


class NewsEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "NEWS"
    source: SourceInfo
    content: NewsContent
    collectedAt: str


def _parse_pub_date(entry) -> Optional[datetime]:
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass

    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        return datetime(*struct[:6], tzinfo=timezone.utc)

    return None


def _extract_full_text(entry) -> str:
    if "content" in entry and entry["content"]:
        return entry["content"][0].get("value", "").strip()
    if "summary" in entry:
        return entry["summary"].strip()
    return ""


async def _fetch_feed(session: aiohttp.ClientSession, source_name: str, feed_url: str) -> list[NewsEntity]:
    entities = []
    try:
        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            raw = await resp.text()
    except Exception as e:
        print(f"[news] failed to fetch {source_name}: {e}")
        return entities

    parsed = feedparser.parse(raw)
    now = datetime.now(timezone.utc)

    for entry in parsed.entries:
        pub_date = _parse_pub_date(entry)
        if pub_date is None:
            continue
        if now - pub_date > FRESHNESS_WINDOW:
            continue

        entities.append(
            NewsEntity(
                source=SourceInfo(name=source_name, url=entry.get("link", feed_url)),
                content=NewsContent(
                    title=entry.get("title", "").strip(),
                    full_text=_extract_full_text(entry),
                    published_date=pub_date.isoformat(),
                ),
                collectedAt=now.isoformat(),
            )
        )

    return entities


async def fetch_news(session: aiohttp.ClientSession) -> list[NewsEntity]:
    tasks = [_fetch_feed(session, name, url) for name, url in NEWS_FEEDS]
    results = await asyncio.gather(*tasks)
    all_entities = [entity for batch in results for entity in batch]
    print(f"[news] collected {len(all_entities)} articles published within last 24h across {len(NEWS_FEEDS)} sources")
    return all_entities


async def main():
    async with aiohttp.ClientSession() as session:
        news = await fetch_news(session)
        for n in news[:5]:
            print(f"- {n.content.title} | {n.source.name} | {n.content.published_date}")
        return news


if __name__ == "__main__":
    asyncio.run(main())