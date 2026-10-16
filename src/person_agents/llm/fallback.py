from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml
from openai import OpenAIError

from person_agents.config.settings import settings
from person_agents.llm.client import LLMResponse, call_llm

logger = structlog.get_logger()


class LLMFallbackError(Exception):
    pass


def load_fallback_chain(path: Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = Path(__file__).parent / ".." / "config" / "fallback.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    chain = data.get("fallback_chain", [])
    for entry in chain:
        if entry.get("provider") == "openai":
            if "model" not in entry:
                entry["model"] = settings.openai_model
            entry["base_url"] = settings.openai_base_url
        elif entry.get("provider") == "ollama":
            if "model" not in entry:
                entry["model"] = settings.ollama_model
            entry["base_url"] = settings.ollama_base_url
    return chain


async def call_with_fallback(messages: list[dict[str, str]]) -> LLMResponse:
    from person_agents.config.settings import settings

    chain = load_fallback_chain()
    last_error: Exception | None = None
    for entry in chain:
        provider = entry.get("provider", "openai")
        if provider != "ollama" and not settings.openai_api_key:
            logger.info("skipping_provider_no_key", provider=provider)
            continue
        if provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    resp = await client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
                if resp.status_code != 200:
                    logger.info("skipping_ollama_unhealthy", status=resp.status_code)
                    continue
            except httpx.HTTPError:
                logger.info("skipping_ollama_unreachable")
                continue
        model = entry.get("model", "")
        timeout_s = entry.get("timeout_s", 30)
        max_retries = entry.get("max_retries", 1)
        for attempt in range(max_retries):
            try:
                base_url = entry.get("base_url")
                resp = await call_llm(provider, model, messages, timeout_s, base_url)
                resp.degraded = attempt > 0 or entry.get("name") != "primary"
                if resp.degraded:
                    logger.warning("llm_degraded", model=model, provider=provider)
                return resp
            except (httpx.HTTPError, ConnectionError, TimeoutError, OpenAIError) as exc:
                last_error = exc
                logger.warning("llm_attempt_failed", model=model, provider=provider, attempt=attempt, error=str(exc))
    raise LLMFallbackError(f"All models in fallback chain failed: {last_error}") from last_error
