"""
One-off manual test: run the paper scraper for a small count and print
what came back, so we can see it actually works before wiring it into
the full pipeline.
"""
import asyncio

from src.scrapers.papers import scrape_papers


async def main():
    papers = await scrape_papers(target_count=20)  # small number for a quick test
    print(f"\nGot {len(papers)} papers:\n")
    for p in papers[:5]:
        print(f"- {p.content.title}")
        print(f"  stars: {p.content.github_stars}, url: {p.content.paper_url}")


if __name__ == "__main__":
    asyncio.run(main())
