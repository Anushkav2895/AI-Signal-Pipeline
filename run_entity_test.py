import asyncio
import aiohttp

from src.entity_resolution import build_mapping_log
from src.scrapers.startups import fetch_startups
from src.sheets_writer import write_records


async def main():
    async with aiohttp.ClientSession() as session:
        startups = await fetch_startups(session, limit=1000)

    raw_names = [s.content.entityName for s in startups]
    mapping_log = build_mapping_log(raw_names)

    matched_count = sum(1 for m in mapping_log if m["matched"])
    print(f"[entity_resolution] {matched_count}/{len(mapping_log)} names resolved to a known canonical entity")
    print(f"[entity_resolution] {len(mapping_log) - matched_count} treated as distinct/new entities")

    write_records("entity_mapping", mapping_log)


if __name__ == "__main__":
    asyncio.run(main())