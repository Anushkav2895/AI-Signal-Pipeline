import asyncio
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import aiohttp
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

PAGE_SIZE = 20  # Product Hunt's max per page for this query

POSTS_QUERY = """
query GetPosts($cursor: String) {
  posts(first: %d, after: $cursor, order: NEWEST) {
    edges {
      node {
        id
        name
        tagline
        url
        website
        topics {
          edges {
            node {
              name
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
""" % PAGE_SIZE

FREE_SIGNAL_TOPICS = {"free", "open-source", "open source"}


class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class SourceInfo(BaseModel):
    name: str
    url: str


class ProductContent(BaseModel):
    startupName: str
    pricingModel: PricingModel


class ProductEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "PRODUCT"
    source: SourceInfo
    content: ProductContent
    collectedAt: str


def _get_access_token() -> str:
    # Developer Token from https://api.producthunt.com/v2/oauth/applications
    # (non-expiring, no exchange step needed)
    return os.environ["PH_DEVELOPER_TOKEN"]


def _infer_pricing_model(topic_names: list[str]) -> PricingModel:
    """
    Product Hunt's API does not expose pricing data directly.
    Heuristic: check topic tags for explicit free/open-source signals,
    otherwise default to FREEMIUM (the most common category on PH launches).
    This is a documented, consistent rule -- not a per-product guess.
    """
    lowered = {t.lower() for t in topic_names}
    if lowered & FREE_SIGNAL_TOPICS:
        return PricingModel.FREE
    return PricingModel.FREEMIUM


def _to_product_entity(node: dict) -> ProductEntity:
    topic_names = [edge["node"]["name"] for edge in node.get("topics", {}).get("edges", [])]
    return ProductEntity(
        source=SourceInfo(name="Product Hunt", url=node["url"]),
        content=ProductContent(
            startupName=node["name"].strip(),
            pricingModel=_infer_pricing_model(topic_names),
        ),
        collectedAt=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_products(session: aiohttp.ClientSession, limit: int = 1000) -> list[ProductEntity]:
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    entities: list[ProductEntity] = []
    cursor: Optional[str] = None
    seen = set()

    while len(entities) < limit:
        payload = {"query": POSTS_QUERY, "variables": {"cursor": cursor}}
        async with session.post(
            PH_GRAPHQL_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 429:
                await asyncio.sleep(2)
                continue
            resp.raise_for_status()
            data = await resp.json()

        if "errors" in data:
            raise RuntimeError(f"Product Hunt API error: {data['errors']}")

        posts = data["data"]["posts"]
        for edge in posts["edges"]:
            node = edge["node"]
            key = node["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append(_to_product_entity(node))

        page_info = posts["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

        # be polite -- PH rate limits are generous but not infinite
        await asyncio.sleep(0.3)

    return entities[:limit]


async def main():
    async with aiohttp.ClientSession() as session:
        products = await fetch_products(session, limit=1000)
        print(f"[products] collected {len(products)} unique product records")
        for p in products[:5]:
            print(f"- {p.content.startupName} | {p.content.pricingModel.value} | {p.source.url}")
        return products


if __name__ == "__main__":
    asyncio.run(main())