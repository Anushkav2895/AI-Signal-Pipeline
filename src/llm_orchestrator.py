# example: extracting a research paper record from raw HTML
from llm_orchestrator import extract_structured

SYSTEM_PROMPT = """You are a data extraction engine. Given raw text from a webpage,
extract a JSON object matching this schema exactly:
{"title": str, "authors": [str], "paper_url": str, "github_url": str|null, "published_date": ISO8601}
Return ONLY the JSON object, no prose, no markdown fences."""

async def process_page(session, raw_html_text):
    results = await extract_structured(session, raw_html_text, SYSTEM_PROMPT)
    return results
