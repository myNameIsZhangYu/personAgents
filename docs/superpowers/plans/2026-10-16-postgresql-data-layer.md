# PostgreSQL Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PostgreSQL-backed run and memory persistence with a repository abstraction, async API pool, migration bootstrap, production compose service, health checks, and administrative credential APIs while preserving SQLite local behavior.

**Architecture:** Introduce a `RunStore`/`MemoryStore` protocol and make `SQLiteStore` the default implementation. Add an async PostgreSQL adapter using SQLAlchemy async and asyncpg for API-facing operations. Keep worker lease operations SQLite-backed for this phase, and use PostgreSQL for API reads/writes and memory persistence. Compose exposes PostgreSQL only under the `postgres` profile.

**Tech Stack:** Python 3.11+, SQLAlchemy 2 async, asyncpg, PostgreSQL 16, FastAPI, SQLite fallback, pytest, Ruff.

**Spec:** This plan implements approved P11 scope. Full worker PostgreSQL leasing and Alembic migration parity are deferred to P12.

## Global Constraints

- Default local execution must remain SQLite-only and offline-safe.
- PostgreSQL tests use SQLModel-free SQLAlchemy Core and may use a connection URL without a live database in unit tests.
- No plaintext API key is persisted or returned.
- API must run under async request handlers without blocking DB calls where a PostgreSQL adapter is configured.
- Every task must include targeted tests and a commit.

---

### Task 1: Repository Protocols

**Files:**
- Create: `src/person_agents/memory/protocols.py`
- Modify: `src/person_agents/memory/sqlite_store.py`
- Test: `tests/test_memory_protocols.py`

**Interfaces:**
- Produces: `RunStore`, `MemoryStore` protocols; explicit `SQLiteStore` implementation conformance.

- [ ] Define repository method contracts.
- [ ] Add lightweight static conformance assertions.
- [ ] Run targeted tests.
- [ ] Commit.

### Task 2: Settings and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/person_agents/config/settings.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: settings `postgres_dsn`, `postgres_pool_size`, `postgres_max_overflow`.

- [ ] Add SQLAlchemy and asyncpg dependencies.
- [ ] Add PostgreSQL settings and env examples.
- [ ] Run lock and tests.
- [ ] Commit.

### Task 3: Async PostgreSQL Store

**Files:**
- Create: `src/person_agents/memory/postgres_store.py`
- Test: `tests/test_postgres_store.py`

**Interfaces:**
- Consumes: `RunStore`, `MemoryStore`, SQLAlchemy async engine.
- Produces: `PostgresStore` with bootstrap, create/get/update run, memory CRUD, and queue gauges.

- [ ] Add schema bootstrap SQL compatible with SQLite columns.
- [ ] Implement async PostgreSQL run and memory operations.
- [ ] Add unit tests using mocked engine connections.
- [ ] Verify tenant/user filtering and status lifecycle.
- [ ] Commit.

### Task 4: API Store Selection

**Files:**
- Modify: `src/person_agents/api/app.py`
- Modify: `src/person_agents/api/schemas.py`
- Modify: `src/person_agents/config/settings.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `SQLiteStore`, `PostgresStore`, `RunStore`, `MemoryStore`.
- Produces: FastAPI uses `PostgresStore` when `postgres_dsn` is configured; readyz reports `postgres`.

- [ ] Add async store selector.
- [ ] Wire run endpoints and memory writes to selected repository.
- [ ] Add PostgreSQL readiness check without exposing connection details.
- [ ] Add tests for selector and readiness behavior.
- [ ] Commit.

### Task 5: Compose and Operations

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: PostgreSQL settings and app health.
- Produces: `postgres` profile service, healthcheck, volume, and operational documentation.

- [x] Add PostgreSQL 16 profile service.
- [x] Configure resource limits and health checks.
- [x] Document startup, backup, rollback, and SQLite-to-PostgreSQL caveats.
- [x] Verify compose configuration.
- [x] Commit.

### Task 6: Administrative Credential APIs

**Files:**
- Create: `src/person_agents/api/admin.py`
- Modify: `src/person_agents/api/app.py`
- Modify: `src/person_agents/api/schemas.py`
- Modify: `src/person_agents/security/credentials.py`
- Test: `tests/test_admin_api.py`

**Interfaces:**
- Consumes: `CredentialManager`, admin API key.
- Produces: admin-only create/revoke/rotate endpoints returning plaintext exactly once.

- [ ] Add admin identity check and separate admin key setting.
- [ ] Add credential create/revoke/rotate endpoints.
- [ ] Return plaintext only on create/rotate responses.
- [ ] Add tests for authorization, lifecycle, and absence of key leakage.
- [ ] Commit.

### Task 7: Final Verification

- [ ] Run pytest, ruff, lock check, and compose config.
- [ ] Verify SQLite fallback, PostgreSQL selector, admin APIs, and documentation.
- [ ] Push and confirm CI green.
- [ ] Mark all plan checkboxes completed.
