# Personal Agent System Design

## Overview
Production-grade personal agent with multi-agent orchestration via LangGraph, MCP tool layer, persistent memory, governance, observability, Docker sandbox, LLM fallback chain, and evaluation framework.

## Tech Stack
- Orchestration: LangGraph
- Vector store: ChromaDB
- Structured storage: SQLite + Alembic
- Monitoring: Langfuse (self-hosted Docker) + structlog
- Sandbox: Docker
- CLI: Typer + Rich
- LLM: OpenAI SDK + fallback chain (primary → fallback → local Ollama)
- Validation: Pydantic v2
- Config: pydantic-settings + .env

## Architecture
See conversation for full module breakdown and directory structure.

## Key Decisions
- LangGraph over AutoGen: structured task orchestration, checkpointing, production maturity
- ChromaDB over pgvector/Qdrant: zero-ops, local-first, Python native
- Langfuse self-hosted over LangSmith SaaS: data sovereignty, no cloud dependency
- Docker sandbox mandatory for shell/code execution
- LLM fallback: primary → fallback → local, with structured error output on total failure

## Production Checklist
- Health check CLI command
- Graceful shutdown (SIGTERM → save checkpoint)
- Pydantic output validation on tool call params
- SQLite WAL mode for concurrent safety
- Alembic migrations for schema changes
- .env key rotation support
