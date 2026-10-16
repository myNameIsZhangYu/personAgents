import hashlib

import pytest

from person_agents.security.auth import SecurityError, resolve_request_context


def test_resolve_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "person_agents.config.settings.settings.api_key_hash",
        hashlib.sha256(b"deadbeef").hexdigest(),
        raising=False,
    )
    context = resolve_request_context("deadbeef")
    assert context.user_id.startswith("user_")
    assert context.tenant_id == "default"
    assert context.session_id.startswith("session_")


def test_missing_key_denied() -> None:
    with pytest.raises(SecurityError):
        resolve_request_context(None)


def test_unknown_key_denied(monkeypatch) -> None:
    monkeypatch.setattr("person_agents.config.settings.settings.api_key_hash", "a" * 64, raising=False)
    with pytest.raises(SecurityError):
        resolve_request_context("wrong")
