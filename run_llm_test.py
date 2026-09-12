import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

from src.llm_orchestrator import extract_structured

SAMPLE_RAW_TEXT = """
Title: Mi-Ripple: Restoring Images Degraded by Iterative AI Editing
Authors: Wei Chen, Priya Sharma, Tomasz Nowak
Published: September 8, 2026
This paper introduces Mi-Ripple, a novel technique for restoring images that have
been degraded through repeated AI-based editing passes. The associated code is
available at https://github.com/example-org/mi-ripple.
"""

SYSTEM_PROMPT = """You are a data extraction engine. Given raw text describing a
research paper, extract a JSON object matching this schema exactly:
{"title": str, "authors": [str], "published_date": str, "github_url": str}
Return ONLY the JSON object, no prose, no markdown fences."""


async def main():
    async with aiohttp.ClientSession() as session:
        print("Testing LLM fallback chain (Gemini -> Groq -> DeepSeek)...")
        results = await extract_structured(session, SAMPLE_RAW_TEXT, SYSTEM_PROMPT)
        print(f"\n[llm_chain] extracted {len(results)} record(s):")
        for r in results:
            print(r)


if __name__ == "__main__":
    asyncio.run(main())