# P7 — Production Upgrade Plan

## Phase 1 — Core Pipeline
- [x] 1.1 Compile LangGraph StateGraph, CLI uses compiled graph
- [x] 1.2 Executor calls real tools via function calling → registry handler
- [x] 1.3 Governance middleware (rate limit + policy + audit) wired into LLM and tool calls
- [x] 1.4 Memory injection (intent retrieval → planner/executor system prompt)
- [x] 1.5 Docker sandbox wired into executor for shell tool

## Phase 2 — Production Hardening
- [x] 2.1 App Dockerfile + compose service
- [x] 2.2 GitHub Actions CI (pytest + ruff)
- [x] 2.3 Full-chain Langfuse trace (per-node spans)
- [x] 2.4 Eval runner with real LLM + report

## Phase 3 — Final Integration
- [x] 3.1 E2E CLI verification (multi-step task → tool → memory → trace)
- [x] 3.2 README update
