import hashlib
import sqlite3
import uuid

from person_agents.config.settings import settings
from person_agents.security.context import RequestContext
from person_agents.security.credentials import CredentialManager


class SecurityError(Exception):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_request_context(api_key: str | None) -> RequestContext:
    if not api_key:
        raise SecurityError("API key is required")
    try:
        credential = CredentialManager().verify(api_key)
    except (RuntimeError, sqlite3.Error):
        credential = None
    if credential:
        return RequestContext(
            user_id=credential.user_id,
            tenant_id=credential.tenant_id,
            session_id=f"session_{uuid.uuid4().hex}",
        )
    if not settings.api_key_hash or _digest(api_key) != settings.api_key_hash:
        raise SecurityError("Invalid API key")
    user_id = f"user_{_digest(api_key)[:24]}"
    session_id = f"session_{uuid.uuid4().hex}"
    return RequestContext(user_id=user_id, tenant_id=settings.default_tenant_id, session_id=session_id)


def resolve_registry_context(api_key: str | None, db_path=None) -> RequestContext:
    if not api_key:
        raise SecurityError("API key is required")
    credential = CredentialManager(db_path).verify(api_key)
    if credential is None:
        raise SecurityError("Invalid API key")
    return RequestContext(
        user_id=credential.user_id,
        tenant_id=credential.tenant_id,
        session_id=f"session_{uuid.uuid4().hex}",
    )
