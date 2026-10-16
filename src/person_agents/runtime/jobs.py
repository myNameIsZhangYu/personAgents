import uuid

from person_agents.memory.sqlite_store import SQLiteStore


class JobManager:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create(self, prompt: str, owner_user_id: str, tenant_id: str, session_id: str) -> str:
        run_id = str(uuid.uuid4())
        self.store.create_run(run_id, prompt, owner_user_id, tenant_id, session_id)
        return run_id

    def get(self, run_id: str, owner_user_id: str, tenant_id: str) -> dict | None:
        return self.store.get_run(run_id, owner_user_id, tenant_id)

    def update(self, run_id: str, owner_user_id: str, tenant_id: str, status: str, output: str | None = None, confirmation_token: str | None = None, error: str | None = None) -> bool:
        return self.store.update_run(run_id, owner_user_id, tenant_id, status, output, confirmation_token, error)

    def next(self) -> dict | None:
        return self.store.next_queued_run()
