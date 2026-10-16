# Production Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the P1 runtime layer: asynchronous run lifecycle, distributed confirmation/rate-limit state, persistent job records, and Prometheus metrics/SLO groundwork.

**Architecture:** Introduce a state store abstraction with in-memory and Redis implementations. Convert `/runs` into an async job API with persisted `runs` records and a background worker loop. Migrate confirmations and token buckets to the same state store. Expose `/metrics` with request/job/tool/LLM counters and latency histograms.

**Tech Stack:** FastAPI, Redis, redis-py, prometheus-client, Pydantic, pytest, Docker Compose.

**Spec:** The remaining P1 gaps are async task execution, distributed state, persistent run tracking, and metrics/SLO readiness.

## Global Constraints

- Public API must return `202 Accepted` with `run_id` for accepted runs.
- Run state transitions must be persisted: `queued → running → completed | failed | awaiting_confirmation | canceled`.
- Confirmation and rate-limit decisions must survive process restarts when Redis is configured.
- Existing synchronous API and CLI must remain compatible.
- Metrics must not include prompts, outputs, API keys, or raw tool arguments.
- Every task must keep pytest and ruff green.
---

### Task 1: State store abstraction and Redis settings

**Files:**
- Create: `src/person_agents/runtime/state.py`
- Modify: `src/person_agents/config/settings.py`
- Modify: `pyproject.toml`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `StateStore` protocol with `set_json`, `get_json`, `delete`, `increment`, `acquire_bucket`, `store_confirmation`, `get_confirmation`, `consume_confirmation`; `InMemoryStateStore`; `create_state_store()`; settings `redis_url: str = ""`.

- [x] Write tests for JSON persistence, one-time confirmation, and separate token buckets.
- [x] Implement in-memory store and Redis-backed store with TTLs.
- [x] `create_state_store()` returns Redis when `redis_url` is configured, otherwise memory.
- [x] Commit.

### Task 2: Migrate confirmation and rate limiting

**Files:**
- Modify: `src/person_agents/security/confirmation.py`
- Modify: `src/person_agents/governance/rate_limiter.py`
- Modify: `src/person_agents/middleware.py`
- Test: `tests/test_confirmation.py`, `tests/test_governance.py`

**Interfaces:**
- Consumes: `StateStore`.
- Produces: `ConfirmationStore(state_store)`, `RateLimiter(state_store)`.

- [x] Replace local confirmation dict with `StateStore` scoped by tenant/user.
- [x] Replace local token buckets with atomic `acquire_bucket`.
- [x] Keep fallback-compatible memory behavior.
- [x] Commit.

### Task 3: Persistent run job model

**Files:**
- Modify: `src/person_agents/memory/sqlite_store.py`
- Create: `src/person_agents/runtime/jobs.py`
- Modify: `src/person_agents/api/schemas.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Produces: `runs` table with `run_id`, owner/tenant, prompt, status, output, confirmation_token, timestamps; `JobManager.create/get/update/cancel/list`; API `RunAcceptedResponse(run_id,status,session_id)`.

- [x] Add schema migration and owner-scoped access.
- [x] Implement queued/running/failed/awaiting_confirmation lifecycle.
- [x] Add cancellation flag read by worker.
- [x] Commit.

### Task 4: Async run API and worker

**Files:**
- Modify: `src/person_agents/api/app.py`
- Create: `src/person_agents/runtime/worker.py`
- Modify: `src/person_agents/cli.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `JobManager`, graph `run_graph`.
- Produces: `POST /runs → 202`, `GET /runs/{run_id}`, `POST /runs/{run_id}/cancel`, `person-agents worker`.

- [x] Enqueue run and return `202`.
- [x] Worker polls queued jobs, marks running, invokes graph, writes result.
- [x] Map confirmation-required output to `awaiting_confirmation`.
- [x] Add cancel endpoint and worker cancellation check.
- [x] Preserve synchronous execution behind `run_mode=synchronous` if needed.
- [x] Commit.

### Task 5: Prometheus metrics

**Files:**
- Create: `src/person_agents/observability/metrics.py`
- Modify: `src/person_agents/api/app.py`
- Modify: `src/person_agents/middleware.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Produces: `/metrics`; counters `http_requests_total`, `run_jobs_total`, `tool_calls_total`, `llm_calls_total`; histograms `http_request_duration_seconds`, `run_duration_seconds`.

- [x] Add global registry and cardinality-safe labels.
- [x] Instrument API and middleware.
- [x] Assert `/metrics` exposes counters and no prompt/output text.
- [x] Commit.

### Task 6: Compose runtime and documentation

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile.app`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Produces: `redis` service, `worker` service, env `PERSON_AGENTS_REDIS_URL`, `/metrics`, run API docs.

- [x] Add Redis and worker.
- [x] Wire health and metrics.
- [x] Document API lifecycle and Redis behavior.
- [x] Commit.

### Task 7: Final verification

- [x] Run pytest, ruff, lock check, compose config.
- [x] Validate job transitions, confirmation persistence, distributed limiter behavior, and metrics cardinality.
- [x] Push and confirm CI green.
- [x] Mark all plan checkboxes completed.
