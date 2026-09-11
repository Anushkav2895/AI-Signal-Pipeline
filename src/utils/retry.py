"""
Shared retry/backoff policy for every outbound call in the pipeline
(HTTP scraping, GitHub API, Papers with Code API, LLM tier calls).

One implementation, used everywhere, so retry behavior is consistent
and testable in isolation instead of copy-pasted per scraper.
"""
from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

from src.config import settings

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts are used up without success."""

    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error!r}")


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with full jitter, capped at max_backoff_seconds."""
    raw = settings.base_backoff_seconds * (2 ** attempt)
    capped = min(raw, settings.max_backoff_seconds)
    jitter = random.uniform(0, settings.jitter_seconds)
    return capped + jitter


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    retriable: Callable[[Exception], bool] = lambda e: True,
    max_retries: int | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """
    Call an async zero-arg function, retrying on exception.

    - `retriable(exc)` decides whether an exception should trigger a retry
      (e.g. only on 429/5xx, not on 4xx schema errors).
    - `on_retry(attempt, exc, sleep_seconds)` is an optional hook for logging.
    """
    attempts = max_retries if max_retries is not None else settings.max_retries
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - intentionally broad, filtered by retriable()
            last_error = exc
            if not retriable(exc) or attempt == attempts - 1:
                break
            sleep_for = _backoff_seconds(attempt)
            if on_retry:
                on_retry(attempt, exc, sleep_for)
            await asyncio.sleep(sleep_for)

    assert last_error is not None
    raise RetryExhausted(attempts, last_error)
