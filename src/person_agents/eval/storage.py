import json
from datetime import UTC, datetime

from person_agents.config.settings import settings
from person_agents.memory.sqlite_store import SQLiteStore


class EvalStorage:
    def __init__(self, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore()

    def save_result(self, report: dict, model: str = "unknown") -> str:
        conn = self.store.connect()
        result_id = datetime.now(UTC).isoformat() + "_" + model
        conn.execute(
            """CREATE TABLE IF NOT EXISTS eval_results (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                pass_rate REAL NOT NULL,
                total_tokens INTEGER NOT NULL,
                report TEXT NOT NULL
            )"""
        )
        conn.execute(
            "INSERT INTO eval_results (id,created_at,model,prompt_version,pass_rate,total_tokens,report) VALUES (?,?,?,?,?,?,?)",
            (
                result_id,
                datetime.now(UTC).isoformat(),
                model,
                settings.prompt_version,
                float(report["pass_rate"]),
                int(report["total_tokens"]),
                json.dumps(report, ensure_ascii=False),
            ),
        )
        conn.commit()
        return result_id

    def latest(self) -> dict | None:
        row = self.store.connect().execute(
            "SELECT id,created_at,model,prompt_version,pass_rate,total_tokens,report FROM eval_results ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "created_at": row[1],
            "model": row[2],
            "prompt_version": row[3],
            "pass_rate": row[4],
            "total_tokens": row[5],
            "report": json.loads(row[6]),
        }

    def compare(self, threshold: float) -> bool:
        latest = self.latest()
        return latest is not None and latest["pass_rate"] >= threshold
