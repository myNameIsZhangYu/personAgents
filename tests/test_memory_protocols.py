from person_agents.memory.protocols import MemoryStore, RunStore
from person_agents.memory.sqlite_store import SQLiteStore


def test_sqlite_store_conformance() -> None:
    assert isinstance(SQLiteStore(), RunStore)
    assert isinstance(SQLiteStore(), MemoryStore)
