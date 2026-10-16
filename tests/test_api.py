import hashlib

import httpx

from person_agents.api.app import app
from person_agents.middleware import _confirmations


async def api_client(monkeypatch):
    monkeypatch.setattr(
        "person_agents.config.settings.settings.api_key_hash",
        hashlib.sha256(b"test-key").hexdigest(),
        raising=False,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_healthz(monkeypatch) -> None:
    async with await api_client(monkeypatch) as api:
        response = await api.get("/healthz")
        assert response.json() == {"status": "ok"}


async def test_run_requires_key(monkeypatch) -> None:
    async with await api_client(monkeypatch) as api:
        response = await api.post("/runs", json={"prompt": "hello"})
        assert response.status_code == 401


async def test_confirmation_endpoints(monkeypatch) -> None:
    async with await api_client(monkeypatch) as api:
        confirmation = _confirmations.create("user_x", "default", "filesystem", {"operation": "write"})
        digest = hashlib.sha256(b"test-key").hexdigest()
        context_user = f"user_{digest[:24]}"
        confirmation.owner_user_id = context_user
        confirm = await api.post(f"/confirmations/{confirmation.token}/confirm", headers={"X-API-Key": "test-key"})
        assert confirm.status_code == 200
        reject = await api.post(f"/confirmations/{confirmation.token}/reject", headers={"X-API-Key": "test-key"})
        assert reject.status_code == 200
