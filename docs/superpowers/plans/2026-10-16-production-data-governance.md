# Production Data and Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining production essentials: persistent credentials, configuration provenance, cost enforcement, secret validation, audit hygiene, alerting, and evaluation gates.

**Architecture:** Keep SQLite as the test/local backend and defer PostgreSQL infrastructure to P11. Introduce SQLite-backed credential and configuration registries behind small manager classes, then wire API authentication, run provenance, LLM usage, audit redaction, production secret checks, monitoring artifacts, and CI evaluation gates around them.

**Tech Stack:** Python 3.11+, FastAPI, SQLite WAL, Redis, Docker Compose, Prometheus, Grafana, pytest, Ruff.

**Spec:** This plan implements approved P10 scope. PostgreSQL migration is explicitly out of scope and planned as P11.

## Global Constraints

- Default offline/local behavior must keep working with SQLite and in-memory state.
- Unit tests must not call external LLMs.
- Plaintext API keys must not be stored or returned.
- Credential changes must be auditable.
- No default production secret may pass validation.
- Every task must end with targeted tests and commit.

---

### Task 1: Credential Registry and API Authentication

**Files:**
- Create: `src/person_agents/security/credentials.py`
- Modify: `src/person_agents/security/auth.py`
- Modify: `src/person_agents/config/settings.py`
- Test: `tests/test_credentials.py`

**Interfaces:**
- Consumes: `SQLiteStore`, `RequestContext`, `AuditLogger`.
- Produces: `CredentialRecord`, `CredentialManager.create()`, `.verify()`, `.revoke()`, `.rotate()`; `resolve_request_context()` uses active credentials when configured.

- [x] Add credential schema with key ID, key hash, tenant, user, status, created/rotated timestamps.
- [x] Implement create/verify/revoke/rotate with SHA-256 and constant-time comparison.
- [x] Enforce active status and tenant/user identity.
- [x] Add audit records for create, rotate, revoke, failed verification.
- [x] Preserve legacy API key fallback until migration is complete.
- [x] Add tests for identity, revocation, rotation, malformed credentials, and audit behavior.
- [x] Commit.

### Task 2: Configuration Version Registry

**Files:**
- Create: `src/person_agents/runtime/config_registry.py`
- Modify: `src/person_agents/runtime/worker.py`
- Modify: `src/person_agents/api/app.py`
- Test: `tests/test_config_registry.py`

**Interfaces:**
- Consumes: `SQLiteStore`, settings.
- Produces: `ConfigRegistry.register()`, `.get()`, `.latest()`; run metadata contains actual prompt/tool/policy snapshot IDs.

- [x] Add immutable version table for prompt, tool, and policy configs.
- [x] Implement content-addressed version IDs using SHA-256.
- [x] Register current defaults at store initialization.
- [x] Persist registry version IDs on run creation.
- [x] Add tests for immutability, deduplication, latest lookup, and run linkage.
- [x] Commit.

### Task 3: Cost and Token Quota Enforcement

**Files:**
- Modify: `src/person_agents/governance/rate_limiter.py`
- Modify: `src/person_agents/llm/fallback.py`
- Modify: `src/person_agents/middleware.py`
- Modify: `src/person_agents/runtime/worker.py`
- Test: `tests/test_governance.py`

**Interfaces:**
- Consumes: `LLMResponse`, `RateLimiter`, `RequestContext`.
- Produces: `RateLimiter.record_llm_usage()`, fallback context metadata, run usage columns `total_tokens`, `total_cost_usd`.

- [x] Add model-independent estimate for missing usage fields.
- [x] Record prompt/completion tokens and estimated cost after each governed LLM call.
- [x] Enforce token/cost quota before LLM calls and after run completion.
- [x] Persist total usage per run.
- [x] Add tests for usage recording, quota rejection, and run persistence.
- [x] Commit.

### Task 4: Production Secret Validation

**Files:**
- Create: `src/person_agents/config/validation.py`
- Modify: `src/person_agents/config/settings.py`
- Modify: `src/person_agents/cli.py`
- Test: `tests/test_settings_validation.py`

**Interfaces:**
- Consumes: `Settings`.
- Produces: `validate_production_settings(settings, production=True)` raising `ConfigurationError`; CLI `doctor --production`.

- [x] Validate required production credentials, Redis URL, Langfuse keys, and secret uniqueness/length.
- [x] Block known default passwords and repeated secrets.
- [x] Add explicit opt-in production mode rather than auto-detecting containers.
- [x] Add tests for missing, default, duplicate, and valid configurations.
- [x] Commit.

### Task 5: Audit Redaction and Retention

**Files:**
- Modify: `src/person_agents/governance/audit.py`
- Modify: `src/person_agents/config/settings.py`
- Test: `tests/test_governance.py`

**Interfaces:**
- Consumes: audit records and settings.
- Produces: `AuditRedactor.redact()`, settings `audit_retention_days`, `AuditLogger.purge_expired()`.

- [x] Redact email, phone, credit-card, bearer token, OpenAI-style key, and long secrets.
- [x] Apply redaction to input, output, and error fields while preserving status and IDs.
- [x] Add retention purge and index.
- [x] Add tests for redaction, retention cutoff, tenant/user preservation, and metrics-free output.
- [x] Commit.

### Task 6: Monitoring and Deployment Artifacts

**Files:**
- Create: `deploy/prometheus/prometheus.yml`
- Create: `deploy/prometheus/alerts.yml`
- Create: `deploy/grafana/provisioning/dashboards/dashboard.yml`
- Create: `deploy/grafana/dashboards/person-agents.json`
- Modify: `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `/metrics`, `/readyz`, worker gauges.
- Produces: Prometheus scrape/alerts and Grafana dashboard provisioning.

- [x] Add alert rules for API error rate, readiness, queue depth, dead-letter, worker availability, and Redis availability.
- [x] Add Grafana dashboard panels for throughput, latency, errors, queue, dead-letter, fallback, tools, and LLM calls.
- [x] Add profile-gated monitoring services.
- [x] Document startup, alert meanings, and rollback basics.
- [x] Verify compose and JSON/YAML artifacts.
- [x] Commit.

### Task 7: CI Evaluation Gate

**Files:**
- Create: `src/person_agents/eval/storage.py`
- Modify: `src/person_agents/eval/runner.py`
- Modify: `src/person_agents/cli.py`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_eval_storage.py`

**Interfaces:**
- Consumes: `EvalRunner`, settings versions.
- Produces: `EvalStorage.save_result()`, `.latest()`, `.compare(); CLI `person-agents eval --check-threshold`; CI optional eval gate.

- [ ] Persist evaluation results with model, prompt version, pass rate, tokens, and timestamp.
- [ ] Compare latest result against configured pass-rate threshold.
- [ ] Fail CLI gate when threshold is not met.
- [ ] Add CI workflow option using a seeded offline eval stub or scheduled real evaluation job.
- [ ] Add tests for storage, comparison, threshold failure, and version metadata.
- [ ] Commit.

### Task 8: Final Verification

**Files:**
- Modify: `README.md`
- Modify: plan checkboxes

- [ ] Run full pytest, ruff, lock, and compose validation.
- [ ] Verify credential lifecycle, config registry, quota enforcement, production validation, audit redaction, monitoring config, and eval gate.
- [ ] Push and confirm CI green.
- [ ] Mark all plan checkboxes completed.
