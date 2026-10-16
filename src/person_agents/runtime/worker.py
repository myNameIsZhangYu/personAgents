import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from prometheus_client import Counter

from person_agents.config.settings import settings
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.runtime.jobs import JobManager
from person_agents.runtime.state import create_state_store
from person_agents.security.context import RequestContext

logger = structlog.get_logger()

run_attempts_total = Counter("run_attempts_total", "Run execution attempts", ["status"])
run_dead_letter_total = Counter("run_dead_letter_total", "Runs moved to dead letter")


async def run_one(job: dict, store: SQLiteStore, worker_id: str = "inline", lease_seconds: int = 60) -> None:
    from person_agents.graph.engine import run_graph
    state_store = create_state_store(settings.redis_url)

    manager = JobManager(store)
    if state_store.get_json(f"cancel:{job['run_id']}"):
        manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "canceled")
        return
    manager.renew_lease(job["run_id"], worker_id, lease_seconds)
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
    except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
        attempts = int(job.get("attempts", 1))
        if attempts >= settings.run_max_attempts:
            manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "dead_letter", error=str(exc))
            run_attempts_total.labels("dead_letter").inc()
            run_dead_letter_total.inc()
            return
        retry_at = datetime.now(UTC) + timedelta(seconds=settings.run_retry_backoff_seconds * (2 ** (attempts - 1)))
        manager.update(job["run_id"], job["owner_user_id"], job["tenant_id"], "queued", error=str(exc))
        store.connect().execute("UPDATE runs SET next_retry_at=? WHERE run_id=?", (retry_at.isoformat(), job["run_id"]))
        store.connect().commit()
        run_attempts_total.labels("retry").inc()
        return

    run_attempts_total.labels("completed").inc()

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


async def worker_loop(
    store: SQLiteStore,
    poll_interval: float = 0.5,
    stop_event: asyncio.Event | None = None,
    worker_id: str | None = None,
    lease_seconds: int = 60,
) -> None:
    manager = JobManager(store)
    worker_id = worker_id or uuid.uuid4().hex
    heartbeat_task: asyncio.Task | None = None
    while stop_event is None or not stop_event.is_set():
        job = manager.claim_next(worker_id, lease_seconds)
        if job is None:
            await asyncio.sleep(poll_interval)
            continue
        heartbeat_stop = asyncio.Event()

        run_id = job["run_id"]

        async def heartbeat(
            stop: asyncio.Event = heartbeat_stop,
            active_run_id: str = run_id,
            active_worker_id: str = worker_id,
            active_manager: JobManager = manager,
            active_lease_seconds: int = lease_seconds,
        ) -> None:
            while not stop.is_set():
                active_manager.renew_lease(active_run_id, active_worker_id, active_lease_seconds)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=max(1, active_lease_seconds // 3))
                except TimeoutError:
                    pass

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            await run_one(job, store, worker_id, lease_seconds)
        finally:
            heartbeat_stop.set()
            await asyncio.sleep(0)
            if heartbeat_task:
                heartbeat_task.cancel()
    if heartbeat_task:
        heartbeat_task.cancel()
