import asyncio
import aiohttp

from src.sheets_writer import write_records
from src.news import fetch_news


async def main():
    async with aiohttp.ClientSession() as session:
        news = await fetch_news(session)
        records = [n.model_dump() for n in news]
        write_records("news", records)


if __name__ == "__main__":
    asyncio.run(main())