import asyncio

from src.sheets_writer import write_records
from src.scrapers.papers import scrape_papers


async def main():
    papers = await scrape_papers(target_count=1000)
    records = [p.model_dump() for p in papers]
    write_records("papers", records)


if __name__ == "__main__":
    asyncio.run(main())