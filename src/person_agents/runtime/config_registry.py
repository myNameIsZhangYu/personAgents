import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from person_agents.config.settings import settings
from person_agents.memory.sqlite_store import SQLiteStore


@dataclass
class ConfigVersion:
    kind: str
    version_id: str
    content: str


class ConfigRegistry:
    def __init__(self, store: SQLiteStore | None = None, db_path: Path | None = None):
        self.store = store or SQLiteStore(db_path)

    def connect(self) -> sqlite3.Connection:
        return self.store.connect()

    @staticmethod
    def version_id(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]

    def register(self, kind: str, content: str) -> ConfigVersion:
        version_id = self.version_id(content)
        self.connect().execute(
            "INSERT OR IGNORE INTO config_versions (kind,version_id,content) VALUES (?,?,?)",
            (kind, version_id, content),
        )
        self.store.connect().commit()
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
