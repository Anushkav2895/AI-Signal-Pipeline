import asyncio
import aiohttp

from src.sheets_writer import write_records
from src.scrapers.products import fetch_products


async def main():
    async with aiohttp.ClientSession() as session:
        products = await fetch_products(session, limit=1000)
        records = [p.model_dump() for p in products]
        write_records("products", records)


if __name__ == "__main__":
    asyncio.run(main())