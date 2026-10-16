import hashlib

import httpx

from person_agents.api.app import app
from person_agents.config.settings import settings


async def test_admin_credential_lifecycle(monkeypatch, tmp_path) -> None:
    settings.admin_api_key_hash = hashlib.sha256(b"admin-key").hexdigest()
    settings.sqlite_path = tmp_path / "admin.db"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        created = await api.post(
            "/admin/credentials?tenant_id=tenant-a&user_id=user-a",
            headers={"X-Admin-Key": "admin-key"},
        )
        assert created.status_code == 201
        assert created.json()["plaintext"].startswith("pa_")

        rotated = await api.post(
            "/admin/credentials/rotate",
            json={"key_id": created.json()["key_id"]},
            headers={"X-Admin-Key": "admin-key"},
        )
        assert rotated.status_code == 200

        revoked = await api.post(
            "/admin/credentials/revoke",
            json={"key_id": rotated.json()["key_id"]},
            headers={"X-Admin-Key": "admin-key"},
        )
        assert revoked.status_code == 204


async def test_admin_requires_key() -> None:
    settings.admin_api_key_hash = hashlib.sha256(b"admin-key").hexdigest()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        response = await api.post("/admin/credentials?tenant_id=t&user_id=u")
        assert response.status_code == 401
