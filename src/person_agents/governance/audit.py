import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import structlog

from person_agents.config.settings import settings

logger = structlog.get_logger()


class AuditLogger:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.sqlite_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                input TEXT,
                output TEXT,
                status TEXT NOT NULL,
                error TEXT
            )""")
        return self._conn

    def record(self, agent: str, action: str, input_data: str = "", output_data: str = "", status: str = "success", error: str = "") -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO audit_log (timestamp, agent, action, input, output, status, error) VALUES (?,?,?,?,?,?,?)",
            (datetime.now(UTC).isoformat(), agent, action, input_data, output_data, status, error),
        )
        conn.commit()
