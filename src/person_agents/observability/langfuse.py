import structlog

from person_agents.config.settings import settings

logger = structlog.get_logger()

_client = None


def get_langfuse():
    global _client
    if _client is None and settings.langfuse_public_key and settings.langfuse_secret_key:
        from langfuse import Langfuse
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _client


def trace_llm_call(
    session_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    messages: list[dict[str, str]] | None = None,
    output: str | None = None,
    degraded: bool = False,
    error: str | None = None,
) -> None:
    client = get_langfuse()
    if client is None:
        return
    try:
        with client.start_as_current_observation(
            name="llm_call",
        ) as obs:
            obs.update(
                input=messages or {},
                output={"content": output or ""},
                metadata={
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "latency_ms": latency_ms,
                    "degraded": degraded,
                    "session_id": session_id,
                },
            )
        client.flush()
        if error:
            logger.warning("langfuse_error", error=error)
    except Exception:
        logger.warning("langfuse_trace_failed", exc_info=True)
