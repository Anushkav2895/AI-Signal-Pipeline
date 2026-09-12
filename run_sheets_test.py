import asyncio
import aiohttp

from src.sheets_writer import write_records
from src.scrapers.startups import fetch_startups


async def main():
    async with aiohttp.ClientSession() as session:
        startups = await fetch_startups(session, limit=1000)
        records = [s.model_dump() for s in startups]
        write_records("startups", records)


if __name__ == "__main__":
    asyncio.run(main())