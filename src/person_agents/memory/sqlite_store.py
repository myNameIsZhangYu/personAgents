import sqlite3
from pathlib import Path
from typing import Any

import structlog

from person_agents.config.settings import settings

logger = structlog.get_logger()

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    owner_user_id TEXT NOT NULL DEFAULT 'local',
    tenant_id TEXT NOT NULL DEFAULT 'default',
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'fact',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ended_at TEXT,
    total_tokens INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_owner_key ON memories(tenant_id, owner_user_id, key);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    confirmation_token TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_runs_owner ON runs(tenant_id, owner_user_id, status);
"""


class SQLiteStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.sqlite_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def upsert(self, key: str, value: str, category: str = "fact", owner_user_id: str = "local", tenant_id: str = "default") -> None:
        conn = self.connect()
        conn.execute(
            """INSERT INTO memories (key, owner_user_id, tenant_id, value, category) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, owner_user_id, key) DO UPDATE SET value=excluded.value, category=excluded.category,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
            (key, owner_user_id, tenant_id, value, category),
        )
        conn.commit()

    def get(self, key: str, owner_user_id: str = "local", tenant_id: str = "default") -> dict[str, Any] | None:
        conn = self.connect()
        row = conn.execute(
            "SELECT id, key, value, category, created_at, updated_at FROM memories WHERE key=? AND owner_user_id=? AND tenant_id=?",
            (key, owner_user_id, tenant_id),
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "key": row[1], "value": row[2], "category": row[3], "created_at": row[4], "updated_at": row[5]}

    def search(self, query: str, category: str | None = None, limit: int = 10, owner_user_id: str = "local", tenant_id: str = "default") -> list[dict[str, Any]]:
        conn = self.connect()
        sql = "SELECT id, key, value, category FROM memories WHERE value LIKE ? AND owner_user_id=? AND tenant_id=?"
        params: list[Any] = [f"%{query}%", owner_user_id, tenant_id]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [{"id": r[0], "key": r[1], "value": r[2], "category": r[3]} for r in rows]

    def delete(self, key: str, owner_user_id: str = "local", tenant_id: str = "default") -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "DELETE FROM memories WHERE key=? AND owner_user_id=? AND tenant_id=?",
            (key, owner_user_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def record_session_start(self, session_id: str) -> None:
        conn = self.connect()
        conn.execute("INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
        conn.commit()

    def record_session_end(self, session_id: str, total_tokens: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE sessions SET ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), total_tokens=? WHERE session_id=?", (total_tokens, session_id))
        conn.commit()

    def create_run(self, run_id: str, prompt: str, owner_user_id: str, tenant_id: str, session_id: str, status: str = "queued") -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO runs (run_id, tenant_id, owner_user_id, session_id, prompt, status) VALUES (?,?,?,?,?,?)",
            (run_id, tenant_id, owner_user_id, session_id, prompt, status),
        )
        conn.commit()

    def update_run(self, run_id: str, owner_user_id: str, tenant_id: str, status: str, output: str | None = None, confirmation_token: str | None = None, error: str | None = None) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "UPDATE runs SET status=?, output=?, confirmation_token=?, error=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE run_id=? AND owner_user_id=? AND tenant_id=?",
            (status, output, confirmation_token, error, run_id, owner_user_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_run(self, run_id: str, owner_user_id: str, tenant_id: str) -> dict[str, Any] | None:
        conn = self.connect()
        row = conn.execute(
            "SELECT run_id, tenant_id, owner_user_id, session_id, prompt, status, output, confirmation_token, error, created_at, updated_at FROM runs WHERE run_id=? AND owner_user_id=? AND tenant_id=?",
            (run_id, owner_user_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        columns = ["run_id", "tenant_id", "owner_user_id", "session_id", "prompt", "status", "output", "confirmation_token", "error", "created_at", "updated_at"]
        return dict(zip(columns, row))

    def next_queued_run(self) -> dict[str, Any] | None:
        conn = self.connect()
        row = conn.execute(
            "SELECT run_id, tenant_id, owner_user_id, session_id, prompt FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        columns = ["run_id", "tenant_id", "owner_user_id", "session_id", "prompt"]
        return dict(zip(columns, row))
