import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from person_agents.config.settings import settings


@dataclass
class ConfigVersion:
    kind: str
    version_id: str
    content: str


class ConfigRegistry:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.sqlite_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS config_versions (
                    kind TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kind, version_id)
                )"""
            )
        return self._conn

    @staticmethod
    def version_id(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]

    def register(self, kind: str, content: str) -> ConfigVersion:
        version_id = self.version_id(content)
        self.connect().execute(
            "INSERT OR IGNORE INTO config_versions (kind,version_id,content) VALUES (?,?,?)",
            (kind, version_id, content),
        )
        self._conn.commit()
        return ConfigVersion(kind, version_id, content)

    def get(self, kind: str, version_id: str) -> ConfigVersion | None:
        row = self.connect().execute(
            "SELECT kind,version_id,content FROM config_versions WHERE kind=? AND version_id=?", (kind, version_id)
        ).fetchone()
        return ConfigVersion(*row) if row else None

    def latest(self, kind: str) -> ConfigVersion | None:
        row = self.connect().execute(
            "SELECT kind,version_id,content FROM config_versions WHERE kind=? ORDER BY created_at DESC, version_id LIMIT 1",
            (kind,),
        ).fetchone()
        return ConfigVersion(*row) if row else None

    def register_defaults(self) -> dict[str, str]:
        defaults: dict[str, Any] = {
            "prompt": settings.prompt_version,
            "tool": settings.tool_config_version,
            "policy": settings.policy_version,
        }
        return {kind: self.register(kind, str(content)).version_id for kind, content in defaults.items()}
