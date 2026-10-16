# PersonAgents

Production-grade personal agent with multi-agent orchestration, MCP tool layer, persistent memory, governance, observability, and evaluation framework.

## Architecture

- **Orchestration**: LangGraph (intent → planner → executor → critic → memory_write)
- **LLM**: OpenAI-compatible API with fallback chain (primary → fallback → local Ollama)
- **Memory**: SQLite (WAL) for structured memory + ChromaDB for semantic retrieval
- **Tools**: MCP filesystem (sandboxed) + Docker sandbox for shell execution
- **Governance**: Policy engine (dangerous command blacklist), token bucket rate limiter, SQLite audit log
- **Observability**: Langfuse (self-hosted) + structlog JSON logging + cost tracking
- **CLI**: Typer + Rich (`run` / `chat` / `doctor` / `version`)

## Setup

```bash
uv sync --all-extras
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
```

## Usage

```bash
# Single prompt
uv run person-agents run "Hello"

# Interactive chat
uv run person-agents chat

# Health check
uv run person-agents doctor

# Version
uv run person-agents version
```

## Testing

```bash
uv run pytest -q
uv run ruff check src tests
```

## Observability (Langfuse)

```bash
docker compose up -d
# Open http://localhost:3000, register, create project, copy API keys to .env
```

## Project Structure

```
src/person_agents/
├── cli.py            # Typer entrypoint
├── config/           # pydantic-settings + fallback.yaml
├── llm/              # unified client + fallback chain + router
├── memory/           # SQLite WAL + ChromaDB + Alembic migrations
├── graph/            # LangGraph state/nodes/edges/checkpoint
├── tools/            # MCP filesystem, registry, Docker sandbox
├── governance/       # policy, rate limiter, audit
├── observability/    # Langfuse, structlog, cost tracker
└── eval/             # eval runner + baseline cases
```

## License

MIT
