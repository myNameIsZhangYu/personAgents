import asyncio
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Response

from person_agents.api.schemas import RunAcceptedResponse, RunRequest, RunResponse
from person_agents.config.settings import settings
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.middleware import _confirmations
from person_agents.runtime.jobs import JobManager
from person_agents.runtime.state import create_state_store
from person_agents.security.auth import SecurityError, resolve_request_context
from person_agents.security.context import RequestContext

app = FastAPI(title="person-agents", version="0.1.0")


async def current_context(x_api_key: str | None = Header(default=None)) -> RequestContext:
    try:
        return resolve_request_context(x_api_key)
    except SecurityError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


_context_dependency = Depends(current_context)
_store = SQLiteStore()
_jobs = JobManager(_store)
_state_store = create_state_store(settings.redis_url)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    from person_agents.observability.metrics import (
        http_request_duration_seconds,
        http_requests_total,
    )

    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    endpoint = getattr(route, "path", request.url.path)
    http_requests_total.labels(request.method, endpoint, str(response.status_code)).inc()
    http_request_duration_seconds.labels(request.method, endpoint).observe(time.perf_counter() - started)
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from person_agents.observability.metrics import registry

    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.post("/confirmations/{token}/confirm")
async def confirm_tool(token: str, context: RequestContext = _context_dependency) -> dict[str, bool]:
    confirmation = _confirmations.get(token)
    if confirmation is None or confirmation.owner_user_id != context.user_id or confirmation.tenant_id != context.tenant_id:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    return {"confirmed": True}


@app.post("/confirmations/{token}/reject")
async def reject_tool(token: str, context: RequestContext = _context_dependency) -> dict[str, bool]:
    confirmation = _confirmations.consume(token)
    if confirmation is None or confirmation.owner_user_id != context.user_id or confirmation.tenant_id != context.tenant_id:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    return {"rejected": True}


@app.post("/runs", response_model=RunResponse)
async def create_run(
    request: RunRequest,
    context: RequestContext = _context_dependency,
) -> RunResponse:
    from person_agents.graph.engine import run_graph

    session_id = request.session_id or context.session_id
    scoped_context = RequestContext(user_id=context.user_id, tenant_id=context.tenant_id, session_id=session_id)
    try:
        result = await asyncio.wait_for(
            run_graph(request.prompt, session_id=session_id, context=scoped_context),
            timeout=120,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Agent run timed out") from exc

    tool_results = result.get("tool_results", [])
    output = tool_results[-1].get("output") if tool_results else None
    confirmation_token = None
    status = result.get("status") or "completed"
    if isinstance(output, dict) and output.get("status") == "confirmation_required":
        status = "confirmation_required"
        confirmation_token = output["confirmation_token"]
        output = None
    return RunResponse(session_id=session_id, status=status, output=output, confirmation_token=confirmation_token)


@app.post("/runs/async", response_model=RunAcceptedResponse, status_code=202)
async def create_async_run(
    request: RunRequest,
    context: RequestContext = _context_dependency,
) -> RunAcceptedResponse:
    session_id = request.session_id or context.session_id
    run_id = _jobs.create(request.prompt, context.user_id, context.tenant_id, session_id)
    return RunAcceptedResponse(run_id=run_id, status="queued", session_id=session_id)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, context: RequestContext = _context_dependency) -> RunResponse:
    run = _jobs.get(run_id, context.user_id, context.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(
        session_id=run["session_id"],
        status=run["status"],
        output=run["output"],
        confirmation_token=run["confirmation_token"],
    )


@app.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, context: RequestContext = _context_dependency) -> RunResponse:
    run = _jobs.get(run_id, context.user_id, context.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] not in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Run is not cancelable")
    _state_store.set_json(f"cancel:{run_id}", True, ttl_seconds=3600)
    _jobs.update(run_id, context.user_id, context.tenant_id, "canceled")
    return RunResponse(session_id=run["session_id"], status="canceled")
