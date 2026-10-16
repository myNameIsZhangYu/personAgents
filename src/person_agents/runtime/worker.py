import asyncio
import sqlite3

import structlog

from person_agents.config.settings import settings
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.runtime.jobs import JobManager
from person_agents.runtime.state import create_state_store
from person_agents.security.context import RequestContext

logger = structlog.get_logger()


async def run_one(job: dict, store: SQLiteStore) -> None:
    from person_agents.graph.engine import run_graph
    state_store = create_state_store(settings.redis_url)

    manager = JobManager(store)
    if state_store.get_json(f"cancel:{job['run_id']}"):
        manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "canceled")
        return
    manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "running")
    context = RequestContext(
        user_id=job["owner_user_id"],
        tenant_id=job["tenant_id"],
        session_id=job["session_id"],
    )
    try:
        result = await asyncio.wait_for(
            run_graph(job["prompt"], session_id=job["session_id"], context=context),
            timeout=120,
        )
    except (TimeoutError, sqlite3.Error) as exc:
        manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "failed", error=str(exc))
        return

    tool_results = result.get("tool_results", [])
    output = tool_results[-1].get("output") if tool_results else None
    confirmation_token = None
    status = result.get("status") or "completed"
    if isinstance(output, dict) and output.get("status") == "confirmation_required":
        status = "awaiting_confirmation"
        confirmation_token = output["confirmation_token"]
        output = None
    manager.update(
        job["run_id"],
        job["owner_user_id"],
        job["tenant_id"],
        status,
        str(output) if output is not None else None,
        confirmation_token,
    )


async def worker_loop(store: SQLiteStore, poll_interval: float = 0.5) -> None:
    manager = JobManager(store)
    while True:
        job = manager.next()
        if job is None:
            await asyncio.sleep(poll_interval)
            continue
        await run_one(job, store)
