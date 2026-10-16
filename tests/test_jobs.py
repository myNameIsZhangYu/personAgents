from pathlib import Path

from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.runtime.jobs import JobManager


def test_job_lifecycle(tmp_path: Path) -> None:
    manager = JobManager(SQLiteStore(db_path=tmp_path / "jobs.db"))
    run_id = manager.create("prompt", "owner", "tenant", "session")
    assert manager.get(run_id, "owner", "tenant")["status"] == "queued"
    assert manager.next()["run_id"] == run_id
    assert manager.update(run_id, "owner", "tenant", "completed", "done")
    assert manager.get(run_id, "owner", "tenant")["status"] == "completed"


def test_job_owner_isolation(tmp_path: Path) -> None:
    manager = JobManager(SQLiteStore(db_path=tmp_path / "jobs.db"))
    run_id = manager.create("prompt", "a", "tenant", "session")
    assert manager.get(run_id, "b", "tenant") is None
