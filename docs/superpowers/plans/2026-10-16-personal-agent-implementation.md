# Personal Agent Implementation Plan

## P0 — Skeleton (Day 1-2)
- [ ] pyproject.toml (uv, dependencies)
- [ ] src/person_agents/cli.py (Typer entrypoint, `run` command)
- [ ] src/person_agents/config/settings.py (pydantic-settings)
- [ ] src/person_agents/config/fallback.yaml
- [ ] src/person_agents/llm/client.py (unified LLM interface)
- [ ] src/person_agents/llm/fallback.py (fallback chain)
- [ ] src/person_agents/llm/router.py (simple/complex routing)
- [ ] src/person_agents/observability/logging.py (structlog)
- [ ] src/person_agents/observability/cost.py (token tracking)
- [ ] Person agent responds to simple chat via CLI
- [ ] Health check: `person-agents doctor`
- [ ] Graceful shutdown (signal handler)

## P1 — Memory (Day 3-4)
- [ ] src/person_agents/memory/sqlite_store.py (WAL mode, CRUD)
- [ ] src/person_agents/memory/vector_store.py (ChromaDB)
- [ ] src/person_agents/memory/migrations/ (Alembic setup)
- [ ] Memory read/write integration in agent loop
- [ ] Semantic retrieval test

## P2 — Tools & Sandbox (Day 5-7)
- [ ] src/person_agents/tools/mcp_client.py (MCP protocol)
- [ ] src/person_agents/tools/registry.py
- [ ] src/person_agents/tools/sandbox.py (Docker exec)
- [ ] Dockerfile for sandbox image
- [ ] Filesystem tool via MCP
- [ ] Shell tool via Docker sandbox

## P3 — Orchestration (Day 8-11)
- [ ] src/person_agents/graph/state.py
- [ ] src/person_agents/graph/nodes.py (intent, planner, executor, critic, memory agent)
- [ ] src/person_agents/graph/edges.py (conditional routing)
- [ ] src/person_agents/graph/checkpoint.py (SqliteSaver)
- [ ] Multi-step task execution
- [ ] Failure retry logic

## P4 — Governance (Day 12-13)
- [ ] src/person_agents/governance/policy.py
- [ ] src/person_agents/governance/rate_limiter.py
- [ ] src/person_agents/governance/audit.py
- [ ] Dangerous command blacklist
- [ ] Audit trail persistence

## P5 — Observability & Eval (Day 14-16)
- [ ] docker-compose.yml (Langfuse stack)
- [ ] src/person_agents/observability/langfuse.py
- [ ] src/person_agents/eval/runner.py
- [ ] src/person_agents/eval/cases/ (baseline test set)
- [ ] Regression benchmark
- [ ] docs/DEVELOPMENT.md
