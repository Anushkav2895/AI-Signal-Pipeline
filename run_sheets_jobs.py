import asyncio
import aiohttp

from src.sheets_writer import write_records
from src.jobs import fetch_jobs


async def main():
    async with aiohttp.ClientSession() as session:
        jobs = await fetch_jobs(session)
        records = [j.model_dump() for j in jobs]
        write_records("jobs", records)


if __name__ == "__main__":
    asyncio.run(main())