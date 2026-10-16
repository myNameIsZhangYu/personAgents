import httpx

from person_agents.api.app import app


async def test_metrics(monkeypatch) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        response = await api.get("/metrics")
        assert response.status_code == 200
        assert b"http_requests_total" in response.content
        assert b"http_request_duration_seconds" in response.content
        assert b"secret" not in response.content.lower()
