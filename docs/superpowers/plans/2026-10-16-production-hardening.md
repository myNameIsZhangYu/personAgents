# Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing prototype into a safer multi-instance production runtime without breaking the SQLite/Redis fallback path.

**Architecture:** Keep SQLite as the zero-dependency development backend while introducing a repository layer for job lifecycle operations. Add worker leases, graceful shutdown, bounded retries/dead-letter, tenant quotas, cost guards, richer readiness checks, operational metrics, production deployment guardrails, and version metadata snapshots. SQLite remains the default in this phase; PostgreSQL migration is explicitly deferred because it requires a larger data-layer refactor.

**Tech Stack:** Python 3.11+, FastAPI, SQLite WAL, Redis, Docker Compose, Prometheus, pytest, Ruff.

**Spec:** This plan implements the approved P9 scope: worker safety, tenant quotas, readiness/SLO signals, production configuration, and run provenance. PostgreSQL migration is deferred, not part of acceptance.

## Global Constraints

- Default behavior must remain offline-safe with SQLite and in-memory Redis fallback.
- Redis must be optional; configured Redis behavior must not be silently replaced by memory state.
- No provider API calls are required by unit tests.
- All job lifecycle mutations must remain tenant/user scoped.
- Preserve synchronous `/runs` behavior.
- Production image must run as a non-root user.
- All code must pass `pytest`, `ruff check`, `uv lock --check`, and `docker compose config`.

---

### Task 1: Tenant Runtime Quotas

**Files:**
- Modify: `src/person_agents/config/settings.py`
- Modify: `src/person_agents/middleware.py`
- Modify: `src/person_agents/api/app.py`
- Test: `tests/test_governance.py`

**Interfaces:**
- Consumes: `RequestContext`, `RateLimiter`, FastAPI dependencies.
- Produces: `TenantQuota` dataclass; `QuotaExceededError`; `RateLimiter.allow_run(owner_user_id, tenant_id)`; settings `tenant_max_running_runs`, `tenant_daily_run_limit`, `tenant_daily_token_limit`, `tenant_daily_cost_limit`.

- [x] Add settings and a `QuotaExceededError` that maps to HTTP 429.
- [x] Implement atomic run-slot acquisition/release using Redis-compatible `StateStore`.
- [x] Add daily run/token/cost counters with UTC-day keys and TTLs.
- [x] Apply quota checks before async enqueue and synchronous execution.
- [x] Add tests for run slot release, daily limits, tenant isolation, and API 429 mapping.
- [x] Commit.
- [ ] Commit.

### Task 2: Worker Leases and Graceful Shutdown

**Files:**
- Modify: `src/person_agents/memory/sqlite_store.py`
- Modify: `src/person_agents/runtime/jobs.py`
- Modify: `src/person_agents/runtime/worker.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: SQLite `runs` table and `JobManager`.
- Produces: run columns `lease_owner`, `lease_expires_at`, `attempts`, `next_retry_at`; `JobManager.claim_next(worker_id, lease_seconds)`; `JobManager.complete_lease(run_id, ...)`; `JobManager.recover_expired_leases()`; `worker_loop(..., stop_event, worker_id, lease_seconds)`.

- [x] Add lease/attempt/retry schema columns and backfill defaults.
- [x] Implement atomic SQLite lease claim and expired lease recovery.
- [x] Preserve queued fallback compatibility and owner/tenant scoping.
- [x] Add SIGTERM/SIGINT stop event handling that prevents new claims and lets the current job finish.
- [x] Add heartbeat renewal during execution.
- [x] Add tests for atomic claims, stale recovery, cancellation, heartbeat, and shutdown.
- [x] Commit.
- [ ] Commit.

### Task 3: Retry and Dead-Letter Policy

**Files:**
- Modify: `src/person_agents/config/settings.py`
- Modify: `src/person_agents/runtime/worker.py`
- Modify: `src/person_agents/observability/metrics.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: run attempts and `JobManager`.
- Produces: settings `run_max_attempts`, `run_retry_backoff_seconds`; metrics `run_attempts_total`, `run_dead_letter_total`; terminal status `dead_letter`.

- [x] Catch execution failures without terminating the worker loop.
- [x] Implement attempt increment and bounded exponential retry with `next_retry_at`.
- [x] Move runs to `dead_letter` after the configured maximum attempts.
- [x] Expose attempt and dead-letter metrics with safe labels.
- [x] Add tests for retry, backoff scheduling, exhaustion, dead-letter, and worker-loop survival.
- [x] Commit.
- [ ] Commit.

### Task 4: Run Provenance Snapshots

**Files:**
- Modify: `src/person_agents/config/settings.py`
- Modify: `src/person_agents/memory/sqlite_store.py`
- Modify: `src/person_agents/runtime/worker.py`
- Modify: `src/person_agents/api/app.py`
- Modify: `src/person_agents/api/schemas.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: settings, graph result, job metadata.
- Produces: run columns `agent_version`, `prompt_version`, `tool_config_version`, `policy_version`, `metadata_json`; `AgentVersionInfo.from_settings()`; response `provenance` object.

- [x] Add settings and run provenance columns with safe defaults.
- [x] Capture model, prompt version, tool config, policy version, and runtime version on each run.
- [x] Persist and expose provenance in run responses.
- [x] Add tests proving provenance is immutable after creation and owner-scoped on read.
- [x] Commit.
- [ ] Commit.

### Task 5: Readiness and Operational Metrics

**Files:**
- Modify: `src/person_agents/api/app.py`
- Modify: `src/person_agents/observability/metrics.py`
- Test: `tests/test_api.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: SQLiteStore, StateStore, Prometheus registry.
- Produces: `/readyz` returning 503 when required dependencies fail; gauge `runtime_dependencies_total{dependency,status}`; gauges `sqlite_queue_depth`, `sqlite_running_jobs`, `sqlite_dead_letter_jobs`.

- [x] Implement dependency checks for SQLite and Redis when configured.
- [x] read/test: SQLite queue depth, running jobs, and dead-letter jobs.
- read/test: SQLite queue depth, running jobs, and dead-letter jobs.
- [x] Expose gauges for queue depth, running jobs, and dead-letter jobs.
- [x] Return dependency diagnostics without leaking secrets or prompt/output data.
- [x] Add tests for healthy, degraded, and secret-free responses.
- [x] Commit.
- [ ] Commit.

### Task 6: Production Deployment Guardrails

**Files:**
- Modify: `Dockerfile.app`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `docker compose config`

**Interfaces:**
- Consumes: existing compose services and app image.
- Produces: production compose profile with strict Redis requirement, worker replicas, safe health checks, resource limits, restart policies, and secrets guidance.

- [x] Add non-root Docker image verification and pinned base image digest placeholder policy.
- [x] Add a `production` compose profile for app, worker, and Redis.
- [x] Require Redis in production and fail fast when absent.
- [x] Add restart policies, CPU/memory limits, and app/worker health checks.
- [x] Document required environment variables, secret generation, backup strategy, and rollback basics.
- [x] Verify compose configuration and README examples.
- [x] Commit.
- [ ] Commit.

### Task 7: Final Verification

**Files:**
- Modify: `README.md`
- Test: full local suite

**Interfaces:**
- Consumes: all prior tasks.
- Produces: validated P9 release candidate.

- [x] Run `pytest`, `ruff check`, `uv lock --check`, and `docker compose config`.
- [x] Verify API lifecycle, quota rejection, worker retry, dead-letter, readiness, metrics, and provenance.
- [x] Push and confirm CI green.
- [x] Mark all plan checkboxes completed.
