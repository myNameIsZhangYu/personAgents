from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from person_agents.config.settings import settings


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    degraded: bool = False


async def call_openai(model: str, messages: list[dict[str, str]], timeout_s: int, base_url: str | None = None) -> LLMResponse:
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=base_url or settings.openai_base_url)
    timeout = httpx.Timeout(timeout_s, connect=5.0)
    resp = await client.chat.completions.create(model=model, messages=messages, timeout=timeout)  # type: ignore[arg-type]
    choice = resp.choices[0]
    usage = resp.usage
    return LLMResponse(
        content=choice.message.content or "",
        model=model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )


async def call_ollama(model: str, messages: list[dict[str, str]], timeout_s: int) -> LLMResponse:
    base_url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(base_url, json={"model": model, "messages": messages, "stream": False})
        resp.raise_for_status()
        data = resp.json()
    return LLMResponse(
        content=data["message"]["content"],
        model=model,
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
    )


async def call_llm(provider: str, model: str, messages: list[dict[str, str]], timeout_s: int, base_url: str | None = None) -> LLMResponse:
    if provider == "ollama":
        return await call_ollama(model, messages, timeout_s)
    return await call_openai(model, messages, timeout_s, base_url)
