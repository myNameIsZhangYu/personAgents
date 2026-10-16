"""Unified middleware for LLM and tool calls.

Every call goes through: rate_limit → policy → audit → trace.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from person_agents.config.settings import settings
from person_agents.governance.audit import AuditLogger
from person_agents.governance.policy import Permission, PolicyEngine
from person_agents.governance.rate_limiter import RateLimiter
from person_agents.observability.langfuse import trace_llm_call

logger = structlog.get_logger()

_policy = PolicyEngine()
_rate_limiter = RateLimiter()
_audit = AuditLogger()

def _configure_policy() -> None:
    for value in settings.granted_permissions.split(","):
        permission = Permission(value.strip().lower())
        _policy.grant(permission)


_configure_policy()


async def governed_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    handler: Callable[..., Awaitable[Any]],
) -> Any:
    if not _rate_limiter.allow_tool():
        _audit.record("middleware", f"tool:{tool_name}", str(arguments), status="rate_limited")
        raise RuntimeError(f"Tool call rate limited: {tool_name}")

    required_permission = Permission.SHELL if "sandbox" in tool_name else Permission.WRITE if "write" in str(arguments.get("operation", "")) else Permission.READ
    if not _policy.check(required_permission):
        _audit.record("middleware", f"tool:{tool_name}", str(arguments), status="permission_denied")
        raise PermissionError(f"Permission denied for {required_permission.value}: {tool_name}")

    result = await handler(arguments)
    _audit.record("middleware", f"tool:{tool_name}", str(arguments), str(result)[:200])
    return result


async def governed_llm_call(
    messages: list[dict[str, str]],
    call_fn: Callable[..., Awaitable[Any]],
) -> Any:
    if not _rate_limiter.allow_llm():
        _audit.record("middleware", "llm", "rate limited", status="rate_limited")
        raise RuntimeError("LLM call rate limited")

    import time
    start = time.monotonic()
    result = await call_fn(messages)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    _audit.record("middleware", "llm", str(messages)[-200:], str(result.content)[:200], "success")
    trace_llm_call(
        "agent-llm",
        result.model,
        result.prompt_tokens,
        result.completion_tokens,
        elapsed_ms,
        messages=messages,
        output=result.content,
        degraded=result.degraded,
    )
    return result
