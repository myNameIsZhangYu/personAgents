import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException

from person_agents.api.schemas import RunRequest, RunResponse
from person_agents.middleware import _confirmations
from person_agents.security.auth import SecurityError, resolve_request_context
from person_agents.security.context import RequestContext

app = FastAPI(title="person-agents", version="0.1.0")


async def current_context(x_api_key: str | None = Header(default=None)) -> RequestContext:
    try:
        return resolve_request_context(x_api_key)
    except SecurityError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


_context_dependency = Depends(current_context)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


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
