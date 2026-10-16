import asyncio
import os
import sqlite3

import httpx
import pytest

from person_agents.api.app import app
from person_agents.config.settings import settings
from person_agents.governance.rate_limiter import QuotaExceededError, RateLimiter
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.runtime.jobs import JobManager
from person_agents.runtime.worker import worker_loop


def test_run_quota_daily_and_slots() -> None:
    from person_agents.runtime.state import InMemoryStateStore

    limiter = RateLimiter(InMemoryStateStore(), max_running_runs=1, daily_run_limit=2)
    first = limiter.allow_run("user", "tenant")
    with pytest.raises(QuotaExceededError, match="Concurrent"):
        limiter.allow_run("user", "tenant")
    limiter.release_run_slot(first, "user", "tenant")
    limiter.allow_run("user", "tenant")
    with pytest.raises(QuotaExceededError, match="Daily"):
        limiter.allow_run("user", "tenant")


def test_worker_claim_retry_and_dead_letter(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "runtime.db")
    jobs = JobManager(store)
    run_id = jobs.create("p", "user", "tenant", "session")
    first = jobs.claim_next("worker-a")
    assert first["run_id"] == run_id
    assert first["attempts"] == 1
    assert jobs.claim_next("worker-b") is None
    jobs.update(run_id, "user", "tenant", "queued", error="boom")
    run = jobs.get(run_id, "user", "tenant")
    assert run["attempts"] == 1


def test_worker_loop_graceful_shutdown(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "shutdown.db")
    JobManager(store).create("p", "user", "tenant", "s")
    stop = asyncio.Event()
    stop.set()
    asyncio.run(worker_loop(store, poll_interval=0, stop_event=stop))


def test_readyz_reports_dependencies() -> None:
    original = os.environ.get("PERSON_AGENTS_SQLITE_PATH")
    os.environ["PERSON_AGENTS_SQLITE_PATH"] = "/tmp/person-agents-readyz.db"
    connection = sqlite3.connect("/tmp/person-agents-readyz.db")
    connection.close()
    from person_agents.api.app import _store

    _store.db_path = "/tmp/person-agents-readyz.db"
    _store.close()
    async def query() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
            response = await api.get("/readyz")
            assert response.status_code == 200
            assert b"sqlite_queue_depth" in response.content
            assert not settings.api_key_hash or settings.api_key_hash.encode() not in response.content

    asyncio.run(query())
    if original is None:
        os.environ.pop("PERSON_AGENTS_SQLITE_PATH", None)
    else:
        os.environ["PERSON_AGENTS_SQLITE_PATH"] = original
