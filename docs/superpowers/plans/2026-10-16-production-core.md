# Production Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum production core: authenticated API, user-scoped memory/audit/checkpoints, human confirmation for dangerous tools, validation, and deployable service health.

**Architecture:** FastAPI exposes authenticated `/runs`; request context carries `user_id`, `tenant_id`, and `session_id`. SQLite schemas add owner columns with backward-compatible migration; vector metadata and Langfuse traces carry ownership. Tool middleware enforces JSON Schema validation, human confirmation tokens for dangerous tools, and audit output includes owner identity. A real uvicorn service replaces the placeholder compose command.

**Tech Stack:** FastAPI, Uvicorn, Pydantic v2, jsonschema, SQLite/ChromaDB, Docker Compose, pytest.

**Spec:** The production gap review identified four P0 requirements: service/API boundary, identity and authorization, per-user data isolation, and human confirmation for dangerous tools.

## Global Constraints

- All API requests must resolve an authenticated principal; anonymous access is denied.
- Every memory, vector document, audit record, checkpoint, and trace must be scoped to `user_id` and `tenant_id`.
- Dangerous tools with `requires_confirm=True` must not execute without a valid confirmation token.
- Tool arguments must pass schema validation before policy or handler execution.
- Existing CLI behavior must remain compatible.
- Every task must keep `uv run pytest -q` and `uv run ruff check src tests` green.
- Do not commit real secrets.

---

### Task 1: Request identity model

**Files:**
- Create: `src/person_agents/security/context.py`
- Create: `src/person_agents/security/auth.py`
- Modify: `src/person_agents/config/settings.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `person_agents.config.settings.settings`.
- Produces: `RequestContext(user_id: str, tenant_id: str, session_id: str)`, `SecurityError`, `resolve_request_context(api_key: str | None) -> RequestContext`, and settings `api_key_hash: str`, `default_tenant_id: str`.

- [x] Step 1: Write failing tests for valid key, missing key, and unknown key.
```python
from person_agents.security.auth import resolve_request_context, SecurityError

def test_resolve_context(monkeypatch):
    monkeypatch.setattr("person_agents.config.settings.settings.api_key_hash", "deadbeef", raising=False)
    ctx = resolve_request_context("deadbeef")
    assert ctx.user_id.startswith("user_")
    assert ctx.tenant_id == "default"

def test_missing_key_denied():
    import pytest
    from person_agents.security.auth import SecurityError, resolve_request_context
    with pytest.raises(SecurityError):
        resolve_request_context(None)

def test_unknown_key_denied(monkeypatch):
    import pytest
    monkeypatch.setattr("person_agents.config.settings.settings.api_key_hash", "deadbeef", raising=False)
    from person_agents.security.auth import SecurityError, resolve_request_context
    with pytest.raises(SecurityError):
        resolve_request_context("wrong")
```

- [x] Step 2: Run and confirm failure.
Run: `uv run pytest tests/test_security.py -q`  
Expected: import/module missing failure.

- [x] Step 3: Implement SHA-256 API-key resolver and immutable request context.
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RequestContext:
    user_id: str
    tenant_id: str
    session_id: str
```
SHA-256 the presented key, compare against `api_key_hash`, derive deterministic `user_id`, and build session ID.

- [x] Step 4: Run security tests.
Run: `uv run pytest tests/test_security.py -q`  
Expected: PASS

- [ ] Step 5: Commit.
```bash
git add src/person_agents/security tests/test_security.py src/person_agents/config/settings.py
git commit -m "feat: add authenticated request context"
```

### Task 2: User-scoped structured store

**Files:**
- Modify: `src/person_agents/memory/sqlite_store.py`
- Modify: `src/person_agents/governance/audit.py`
- Test: `tests/test_memory.py`
- Test: `tests/test_governance.py`

**Interfaces:**
- Consumes: `RequestContext`.
- Produces: `SQLiteStore.upsert(..., owner_user_id: str, tenant_id: str)`, `get/search/delete(..., owner_user_id, tenant_id)`, `AuditLogger.record(..., owner_user_id, tenant_id)`, and a real audit `request_id`.

- [x] Step 1: Add failing isolation tests.
```python
def test_user_isolation(store):
    store.upsert("k", "alice", owner_user_id="a", tenant_id="t")
    store.upsert("k", "bob", owner_user_id="b", tenant_id="t")
    assert store.get("k", owner_user_id="a", tenant_id="t")["value"] == "alice"
    assert store.search("alice", owner_user_id="b", tenant_id="t") == []
    assert store.delete("k", owner_user_id="b", tenant_id="t") is False
```

- [x] Step 2: Run memory tests and confirm new test fails.
Run: `uv run pytest tests/test_memory.py -q`  
Expected: new isolation test fails.

- [x] Step 3: Add migration to `owner_user_id` and `tenant_id`, rebuild unique key as `(tenant_id, owner_user_id, key)`, and filter every read/write.
- [x] Step 4: Add audit `request_id` and owner columns. Preserve existing records via `ALTER TABLE ... ADD COLUMN`.
- [x] Step 5: Run all tests.
Run: `uv run pytest -q`  
Expected: PASS

- [ ] Step 6: Commit.
```bash
git add src/person_agents/memory/sqlite_store.py src/person_agents/governance/audit.py tests
git commit -m "feat: scope memory and audit records"
```

### Task 3: User-scoped vector memory

**Files:**
- Modify: `src/person_agents/memory/vector_store.py`
- Modify: `src/person_agents/graph/nodes.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `RequestContext` and vector metadata.
- Produces: `VectorStore.add(text, metadata, owner_user_id, tenant_id)`, `query(..., owner_user_id, tenant_id)`, and graph state/context with owner metadata.

- [x] Update intent retrieval and memory writes to pass context ownership.
- [x] Store `tenant_id` and `owner_user_id` in Chroma metadata.
- [ ] Query with metadata filter and assert cross-user documents are not returned.
- [ ] Commit:
```bash
git commit -m "feat: scope vector memory by user"
```

### Task 4: Human confirmation workflow

**Files:**
- Create: `src/person_agents/security/confirmation.py`
- Modify: `src/person_agents/middleware.py`
- Modify: `src/person_agents/graph/nodes.py`
- Test: `tests/test_confirmation.py`

**Interfaces:**
- Consumes: `ToolDef.requires_confirm`, `RequestContext`.
- Produces: `ConfirmationStore.create(context, tool_name, arguments) -> dict`, `consume(token, context) -> bool`, `governed_tool_call(..., confirmation_token: str | None)`.

- [x] Add TTL confirmation store (default 300s) and one-time token consumption.
- [x] Dangerous tool without token is audited and rejected.
- [ ] Valid token executes once; reuse fails.
- [ ] Graph returns confirmation requests instead of raising on missing confirmation.
- [ ] Commit:
```bash
git commit -m "feat: require confirmation for dangerous tools"
```

### Task 5: Tool schema validation and production middleware

**Files:**
- Modify: `src/person_agents/middleware.py`
- Modify: `src/person_agents/tools/registry.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `ToolDef.parameters`, `RequestContext`.
- Produces: `governed_tool_call(..., context: RequestContext, request_id: str)`, owner-scoped rate limiting and audit.

- [x] Add `jsonschema.validate` before policy.
- [ ] Rate-limit and audit by `(tenant_id, user_id)`.
- [x] Include `request_id` in every tool audit.
- [x] Update graph executor to pass context.
- [ ] Commit:
```bash
git commit -m "feat: enforce tool schemas and scoped governance"
```

### Task 6: Run API and authenticated CLI parity

**Files:**
- Modify: `pyproject.toml`
- Create: `src/person_agents/api/app.py`
- Create: `src/person_agents/api/schemas.py`
- Modify: `src/person_agents/graph/engine.py`
- Modify: `src/person_agents/cli.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `RequestContext`, `run_graph`, confirmation store.
- Produces: `POST /runs`, `GET /confirmations/{token}`, `POST /confirmations/{token}/confirm`, `GET /healthz`; `person-agents serve`.

- [x] Add FastAPI/Uvicorn dependencies.
- [x] Implement API-key auth dependency and request validation.
- [x] Implement `RunRequest(prompt, session_id?)`, `RunResponse(session_id, status, output, confirmation_required?, confirmation_token?)`.
- [x] `POST /runs` executes graph within request scope.
- [ ] Confirmation approve/reject endpoints mutate the confirmation store.
- [x] Wire graph context and owner-scoped stores.
- [x] Add CLI `serve`.
- [ ] Commit:
```bash
git commit -m "feat: add authenticated run API"
```

### Task 7: Deployment entrypoint and health

**Files:**
- Modify: `Dockerfile.app`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `person-agents serve`.
- Produces: container `CMD ["serve"]`, health endpoint, service port `8000`, env `API_KEY_HASH`, `DEFAULT_TENANT_ID`.

- [x] Replace app `--help` with `["serve"]`.
- [ ] Add Dockerfile `EXPOSE 8000` and real HTTP healthcheck.
- [x] Compose publishes `8000`.
- [x] Document key hashing and API examples.
- `API_KEY_HASH` should be SHA-256 of the presented key.
- [ ] Commit:
```bash
git commit -m "feat: add deployable API service"
```

### Task 8: Final production-core verification

**Files:**
- Modify: `docs/superpowers/plans/2026-10-16-production-core.md`
- Modify: `.wolf/STATUS.md`

**Interfaces:**
- Consumes: all prior interfaces.
- Produces: completed plan evidence and CI status.

- [ ] Run full tests, ruff, compose config, Docker build, API smoke test.
- [ ] Verify user A cannot access user B memory/audit/vector data.
- [ ] Confirm dangerous tool requires confirmation and token reuse fails.
- [ ] Push and confirm CI green.
- [ ] Mark every plan checkbox completed.
