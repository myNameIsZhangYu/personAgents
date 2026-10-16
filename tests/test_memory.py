from pathlib import Path

import pytest

from person_agents.memory.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(db_path=tmp_path / "test.db")


class TestSQLiteStore:
    def test_upsert_and_get(self, store: SQLiteStore) -> None:
        store.upsert("pref_style", "concise replies", category="preference")
        result = store.get("pref_style")
        assert result is not None
        assert result["value"] == "concise replies"

    def test_upsert_updates_existing(self, store: SQLiteStore) -> None:
        store.upsert("pref_style", "verbose")
        store.upsert("pref_style", "concise")
        assert store.get("pref_style")["value"] == "concise"

    def test_search(self, store: SQLiteStore) -> None:
        store.upsert("fact1", "user likes Python")
        store.upsert("fact2", "user dislikes Java")
        results = store.search("Python")
        assert len(results) == 1

    def test_delete(self, store: SQLiteStore) -> None:
        store.upsert("key1", "val1")
        assert store.delete("key1") is True
        assert store.get("key1") is None

    def test_wal_mode(self, store: SQLiteStore) -> None:
        conn = store.connect()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
