"""
Central configuration, loaded from environment variables (.env).
Nothing here is hardcoded so the same code scales from a laptop run
of a few hundred records to a distributed run targeting 500k+.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    # --- LLM fallback chain (tier 1 -> tier N) ---
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    groq_model: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # --- Chunking / payload limits ---
    max_chunk_chars: int = _int("MAX_CHUNK_CHARS", 12000)
    chunk_overlap_chars: int = _int("CHUNK_OVERLAP_CHARS", 400)

    # --- Rate limiting / retries ---
    max_retries: int = _int("MAX_RETRIES", 5)
    base_backoff_seconds: float = _float("BASE_BACKOFF_SECONDS", 1.5)
    max_backoff_seconds: float = _float("MAX_BACKOFF_SECONDS", 60.0)
    jitter_seconds: float = _float("JITTER_SECONDS", 0.5)

    # --- Concurrency ---
    scraper_concurrency: int = _int("SCRAPER_CONCURRENCY", 20)
    llm_concurrency: int = _int("LLM_CONCURRENCY", 8)
    http_timeout_seconds: int = _int("HTTP_TIMEOUT_SECONDS", 30)

    # --- Freshness window for Phase II (news/jobs) ---
    freshness_hours: int = _int("FRESHNESS_HOURS", 24)

    # --- Storage ---
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/pipeline.db")
    google_sheets_credentials_path: str = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_PATH", "./credentials.json"
    )
    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")

    # --- Anti-bot ---
    playwright_headless: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    proxy_url: str = os.getenv("PROXY_URL", "")  # residential/rotating proxy, if any
    user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36",
    ])

    # --- Targets (Phase I minimums) ---
    min_startups: int = _int("MIN_STARTUPS", 1000)
    min_products: int = _int("MIN_PRODUCTS", 1000)
    min_papers: int = _int("MIN_PAPERS", 1000)


settings = Settings()
