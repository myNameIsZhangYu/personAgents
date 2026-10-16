
from person_agents.memory.postgres_store import PostgresStore


class FakeResult:
    def __init__(self, rowcount: int = 1):
        self.rowcount = rowcount


class FakeConnection:
    def __init__(self):
        self.calls: list[tuple[object, object | None]] = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))
        return FakeResult()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return self.connection

    def connect(self):
        return self.connection


def test_postgres_store_run_operations(monkeypatch) -> None:
    store = PostgresStore("postgresql+asyncpg://user:pass@localhost/test")
    engine = FakeEngine()
    store.engine = engine

    import asyncio

    asyncio.run(store.create_run("run", "p", "u", "t", "s", provenance={"prompt_version": "pv"}))
    assert engine.connection.calls[0][1]["prompt_version"] == "pv"

    asyncio.run(store.update_run("run", "u", "t", "completed", output="ok", total_tokens=10, total_cost=0.1))
    assert engine.connection.calls[1][1]["status"] == "completed"


def test_postgres_selector_disabled_by_default() -> None:
    from person_agents.api.app import _pg_store
    from person_agents.config.settings import settings

    if not settings.postgres_dsn:
        assert _pg_store is None
