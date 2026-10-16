import hashlib
import uuid

from person_agents.config.settings import settings
from person_agents.security.context import RequestContext


class SecurityError(Exception):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_request_context(api_key: str | None) -> RequestContext:
    if not api_key:
        raise SecurityError("API key is required")
    if not settings.api_key_hash:
        raise SecurityError("API key authentication is not configured")
    if _digest(api_key) != settings.api_key_hash:
        raise SecurityError("Invalid API key")
    user_id = f"user_{_digest(api_key)[:24]}"
    session_id = f"session_{uuid.uuid4().hex}"
    return RequestContext(user_id=user_id, tenant_id=settings.default_tenant_id, session_id=session_id)
