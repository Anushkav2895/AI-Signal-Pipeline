import asyncio
import json
import os
import random
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

import aiohttp

logger = logging.getLogger("llm_orchestrator")
logging.basicConfig(level=logging.INFO)

MAX_CHARS_PER_CHUNK = 12000
MAX_RETRIES_PER_TIER = 3
BASE_BACKOFF_SECONDS = 1.5

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class AllTiersExhaustedError(Exception):
    pass


@dataclass
class LLMTier:
    name: str
    call_fn: Callable[[aiohttp.ClientSession, str, str], Awaitable[str]]


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(para) > max_chars:
            sentences = para.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|")
            buf = ""
            for sent in sentences:
                cand2 = f"{buf} {sent}".strip()
                if len(cand2) <= max_chars:
                    buf = cand2
                else:
                    if buf:
                        chunks.append(buf)
                    buf = sent
            if buf:
                chunks.append(buf)
        else:
            current = para

    if current:
        chunks.append(current)

    return chunks


async def _sleep_with_jitter(attempt: int):
    delay = BASE_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 1)
    logger.warning(f"Backing off {delay:.1f}s (attempt {attempt + 1})")
    await asyncio.sleep(delay)


class _RateLimitError(Exception):
    def __init__(self, provider: str):
        self.provider = provider


class _PayloadTooLargeError(Exception):
    def __init__(self, provider: str):
        self.provider = provider


async def _call_gemini(session: aiohttp.ClientSession, prompt: str, text_chunk: str) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n---\n{text_chunk}"}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    async with session.post(
        f"{GEMINI_URL}?key={api_key}", json=payload, timeout=aiohttp.ClientTimeout(total=45)
    ) as resp:
        if resp.status == 429:
            raise _RateLimitError("gemini")
        if resp.status == 413:
            raise _PayloadTooLargeError("gemini")
        resp.raise_for_status()
        data = await resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(session: aiohttp.ClientSession, prompt: str, text_chunk: str) -> str:
    api_key = os.environ["GROQ_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
                "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_chunk},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    async with session.post(
        GROQ_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=45)
    ) as resp:
        if resp.status == 429:
            raise _RateLimitError("groq")
        if resp.status == 413:
            raise _PayloadTooLargeError("groq")
        resp.raise_for_status()
        data = await resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_deepseek(session: aiohttp.ClientSession, prompt: str, text_chunk: str) -> str:
    api_key = os.environ["DEEPSEEK_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_chunk},
        ],
        "temperature": 0,
    }
    async with session.post(
        DEEPSEEK_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=45)
    ) as resp:
        if resp.status == 429:
            raise _RateLimitError("deepseek")
        if resp.status == 413:
            raise _PayloadTooLargeError("deepseek")
        resp.raise_for_status()
        data = await resp.json()
        return data["choices"][0]["message"]["content"]


TIERS = [
    LLMTier("gemini-flash", _call_gemini),
    LLMTier("groq-llama3", _call_groq),
    LLMTier("deepseek", _call_deepseek),
]


async def extract_structured(
    session: aiohttp.ClientSession,
    raw_text: str,
    system_prompt: str,
) -> list[dict]:
    chunks = chunk_text(raw_text)
    results: list[dict] = []

    for i, chunk in enumerate(chunks):
        parsed = await _extract_chunk(session, chunk, system_prompt, chunk_index=i)
        if parsed is not None:
            if isinstance(parsed, list):
                results.extend(parsed)
            else:
                results.append(parsed)

    return results


async def _extract_chunk(
    session: aiohttp.ClientSession,
    chunk: str,
    system_prompt: str,
    chunk_index: int,
) -> Optional[dict | list]:
    current_chunk = chunk

    for tier in TIERS:
        for attempt in range(MAX_RETRIES_PER_TIER):
            try:
                raw_output = await tier.call_fn(session, system_prompt, current_chunk)
                return _safe_json_parse(raw_output, tier.name, chunk_index)

            except _RateLimitError as e:
                logger.warning(f"[chunk {chunk_index}] {e.provider} rate-limited, retrying")
                await _sleep_with_jitter(attempt)
                continue

            except _PayloadTooLargeError as e:
                logger.warning(f"[chunk {chunk_index}] {e.provider} 413 — splitting chunk further")
                sub_chunks = chunk_text(current_chunk, max_chars=MAX_CHARS_PER_CHUNK // 2)
                sub_results = []
                for sub in sub_chunks:
                    sub_result = await _extract_chunk(session, sub, system_prompt, chunk_index)
                    if sub_result:
                        sub_results.append(sub_result)
                return sub_results

            except Exception as e:
                logger.error(f"[chunk {chunk_index}] {tier.name} failed: {e}")
                break

        logger.warning(f"[chunk {chunk_index}] exhausted {tier.name}, falling back")

    logger.error(f"[chunk {chunk_index}] all tiers exhausted")
    raise AllTiersExhaustedError(f"chunk {chunk_index} failed on gemini, groq, and deepseek")


def _safe_json_parse(raw_output: str, provider: str, chunk_index: int):
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1) if cleaned.startswith("json\n") else cleaned
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"[chunk {chunk_index}] {provider} returned non-JSON output, discarding")
        return None