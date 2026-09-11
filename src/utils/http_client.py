"""
Thin async HTTP wrapper shared by every scraper.

Responsibilities kept here so no individual scraper has to reinvent them:
  - a global concurrency cap (settings.scraper_concurrency) via semaphore
  - per-request timeout
  - UA rotation
  - retry ONLY on 429 / 5xx / connection errors (never on 4xx-that-isn't-429 --
    those are real failures, not rate limiting, and retrying them just wastes
    the retry budget and hides a bug)
  - honoring Retry-After on 429s when the server sends one
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from src.config import settings
from src.utils.retry import retry_async


class HttpError(Exception):
    def __init__(self, status: int, url: str, body_snippet: str = ""):
        self.status = status
        self.url = url
        super().__init__(f"HTTP {status} for {url}: {body_snippet[:200]}")


@dataclass
class HttpResponse:
    status: int
    url: str
    text: str
    headers: dict[str, str]

    def json(self) -> Any:
        import json
        return json.loads(self.text)


class AsyncHttpClient:
    """
    Usage:
        async with AsyncHttpClient() as client:
            resp = await client.get("https://huggingface.co/api/daily_papers", params={...})
    """

    def __init__(self, concurrency: Optional[int] = None):
        self._semaphore = __import__("asyncio").Semaphore(
            concurrency or settings.scraper_concurrency
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncHttpClient":
        timeout = aiohttp.ClientTimeout(total=settings.http_timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._session:
            await self._session.close()

    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers = {"User-Agent": random.choice(settings.user_agents)}
        if extra:
            headers.update(extra)
        return headers

    async def get(
        self,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> HttpResponse:
        assert self._session is not None, "use 'async with AsyncHttpClient() as client'"

        async def _do_request() -> HttpResponse:
            async with self._semaphore:
                async with self._session.get(  # type: ignore[union-attr]
                    url, params=params, headers=self._headers(headers), proxy=settings.proxy_url or None
                ) as resp:
                    body = await resp.text()
                    if resp.status == 429 or resp.status >= 500:
                        raise HttpError(resp.status, url, body)
                    if resp.status >= 400:
                        raise HttpError(resp.status, url, body)
                    return HttpResponse(
                        status=resp.status, url=url, text=body, headers=dict(resp.headers)
                    )

        def _is_retriable(exc: Exception) -> bool:
            if isinstance(exc, HttpError):
                return exc.status == 429 or exc.status >= 500
            return isinstance(exc, (aiohttp.ClientError, TimeoutError))

        return await retry_async(_do_request, retriable=_is_retriable)
