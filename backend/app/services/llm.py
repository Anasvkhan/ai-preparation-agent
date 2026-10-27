"""Single entry point for all LLM calls.

LLM_PROVIDER:
  mock   -> no API call; returns the caller-supplied fake response
  replay -> returns a saved response from fixtures/ if this exact request was seen before,
            otherwise calls Gemini once and saves the response (saves free-tier quota)
  gemini -> always calls Gemini

Gemini calls walk LLM_MODEL_CHAIN, moving to the next model on 429 / 503 / 404.
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from google.genai import errors, types

from app.core.config import get_settings
from app.services.gemini_client import make_client

RETRYABLE_CODES = {429, 500, 503}
TIMEOUT_MS = 180_000  # long answers (20 questions + expected points) can take over a minute

log = logging.getLogger("llm")


@dataclass
class LLMResult:
    data: Any
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False


class LLMUnavailable(Exception):
    """Every model in the chain failed (usually the daily free-tier limit)."""


def _request_hash(system: str, prompt: str, schema: dict | None) -> str:
    raw = json.dumps({"system": system, "prompt": prompt, "schema": schema}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _call_gemini(system: str, prompt: str, schema: dict | None) -> LLMResult:
    s = get_settings()
    client = make_client(TIMEOUT_MS)
    config = types.GenerateContentConfig(
        system_instruction=system or None,
        response_mime_type="application/json",
        response_json_schema=schema,
        temperature=0.4,
    )
    last_error: Exception | None = None
    for model in s.model_chain:
        for attempt in range(3):
            try:
                started = time.monotonic()
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
                data = json.loads(resp.text or "")
                usage = resp.usage_metadata
                log.info("%s answered in %.1fs", model, time.monotonic() - started)
                return LLMResult(
                    data=data,
                    model=model,
                    input_tokens=(usage.prompt_token_count or 0) if usage else 0,
                    output_tokens=(usage.candidates_token_count or 0) if usage else 0,
                )
            except errors.APIError as e:
                last_error = e
                log.warning("%s attempt %d: HTTP %s %s", model, attempt + 1, e.code, str(e)[:120])
                if e.code == 404 or _is_daily_limit(e):
                    break  # model unavailable / quota used up -> next model
                if e.code in RETRYABLE_CODES and attempt < 2:
                    time.sleep(5 * 2**attempt)
                    continue
                if e.code in RETRYABLE_CODES:
                    break  # still failing after retries -> next model
                raise
            except (httpx.TransportError, json.JSONDecodeError) as e:  # flaky network / cut-off answer
                last_error = e
                log.warning("%s attempt %d: %s %s", model, attempt + 1, type(e).__name__, str(e)[:120])
                time.sleep(3 * (attempt + 1))
    raise LLMUnavailable(f"All Gemini models failed: {last_error}")


def _is_daily_limit(e: errors.APIError) -> bool:
    return e.code == 429 and "PerDay" in str(e)


def generate_json(
    purpose: str,
    prompt: str,
    schema: dict | None = None,
    system: str = "",
    mock: Callable[[], Any] | None = None,
) -> LLMResult:
    """Ask the LLM for a JSON answer. `purpose` is used for logging (e.g. "generate_questions")."""
    s = get_settings()

    if s.llm_provider == "mock":
        return LLMResult(data=mock() if mock else {}, model="mock", cached=True)

    if s.llm_provider == "replay":
        path = s.replay_path / f"{purpose}-{_request_hash(system, prompt, schema)}.json"
        if path.exists():
            saved = json.loads(path.read_text())
            return LLMResult(data=saved["data"], model=saved["model"], cached=True)
        result = _call_gemini(system, prompt, schema)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"purpose": purpose, "model": result.model, "data": result.data}, indent=2))
        return result

    return _call_gemini(system, prompt, schema)
