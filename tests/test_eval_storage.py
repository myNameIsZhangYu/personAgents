from pathlib import Path

from person_agents.eval.storage import EvalStorage
from person_agents.memory.sqlite_store import SQLiteStore


def test_eval_storage_threshold(tmp_path: Path) -> None:
    storage = EvalStorage(SQLiteStore(tmp_path / "eval.db"))
    report = {"pass_rate": 0.75, "total_tokens": 42}
    storage.save_result(report, "test-model")
    latest = storage.latest()
    assert latest is not None
    assert latest["model"] == "test-model"
    assert latest["pass_rate"] == 0.75
    assert storage.compare(0.5) is True
    assert storage.compare(0.9) is False
