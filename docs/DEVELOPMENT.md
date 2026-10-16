# Development Guide

## Setup
```bash
uv sync --all-extras
uv run person-agents version
uv run person-agents doctor
```

## Running
```bash
# Single prompt
uv run person-agents run "Hello"

# Interactive chat
uv run person-agents chat

# Health check
uv run person-agents doctor
```

## Testing
```bash
uv run pytest -q
uv run ruff check src tests
```

## Observability (Langfuse)
```bash
docker compose up -d
# Open http://localhost:3000
```

## Sandbox
```bash
docker build -t person-agents/sandbox:latest .
```

## Project Structure
See `docs/superpowers/specs/2026-10-16-personal-agent-design.md` for architecture.
