from typing import Any

import structlog

from person_agents.graph.state import AgentState
from person_agents.llm.fallback import call_with_fallback
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.memory.vector_store import VectorStore

logger = structlog.get_logger()

_store: SQLiteStore | None = None
_vector: VectorStore | None = None


def _get_store() -> SQLiteStore:
    global _store
    if _store is None:
        _store = SQLiteStore()
    return _store


def _get_vector() -> VectorStore:
    global _vector
    if _vector is None:
        _vector = VectorStore()
    return _vector


async def intent_node(state: AgentState) -> dict[str, Any]:
    user_input = state["messages"][-1]["content"]
    memory_hits = _get_vector().query(user_input, n_results=3)
    resp = await call_with_fallback([
        {"role": "system", "content": "Classify the user's intent as one of: chat, task, memory_write, tool_use. Return ONLY the intent word."},
        {"role": "user", "content": user_input},
    ])
    intent = resp.content.strip().lower()
    if intent not in ("chat", "task", "memory_write", "tool_use"):
        intent = "chat"
    return {"intent": intent, "degraded": resp.degraded, "memory_context": memory_hits}


async def planner_node(state: AgentState) -> dict[str, Any]:
    user_input = state["messages"][-1]["content"]
    memory_context = "\n".join(m["text"] for m in state.get("memory_context", []))
    resp = await call_with_fallback([
        {"role": "system", "content": "Break the task into a list of steps. Return a JSON array of objects with 'action' and 'tool' fields."},
        {"role": "user", "content": f"Task: {user_input}\nRelevant memory:\n{memory_context}"},
    ])
    import json
    try:
        plan = json.loads(resp.content)
    except json.JSONDecodeError:
        plan = [{"action": user_input, "tool": "none"}]
    return {"plan": plan, "current_step": 0}


async def executor_node(state: AgentState) -> dict[str, Any]:
    step = state["plan"][state["current_step"]]
    action = step.get("action", "")
    tool = step.get("tool", "none")
    context = "\n".join(m["text"] for m in state.get("memory_context", []))
    resp = await call_with_fallback([
        {"role": "system", "content": f"Execute the action. Tool: {tool}. Relevant context:\n{context}"},
        {"role": "user", "content": action},
    ])
    result = {"step": state["current_step"], "action": action, "tool": tool, "output": resp.content}
    return {"tool_results": [result], "current_step": state["current_step"] + 1}


async def critic_node(state: AgentState) -> dict[str, Any]:
    results_summary = "\n".join(r["output"][:200] for r in state.get("tool_results", []))
    resp = await call_with_fallback([
        {"role": "system", "content": "Evaluate if the task was completed successfully. Return 'success' or 'retry' or 'fail'."},
        {"role": "user", "content": results_summary},
    ])
    feedback = resp.content.strip().lower()
    return {"critic_feedback": feedback, "status": feedback}


async def memory_write_node(state: AgentState) -> dict[str, Any]:
    if state.get("critic_feedback") == "success":
        user_input = state["messages"][-1]["content"]
        result = state["tool_results"][-1]["output"][:300]
        key = f"memory_{hash(user_input)}"
        _get_store().upsert(key, result, category="experience")
        _get_vector().add(result, {"source": "agent", "session": state.get("session_id", "")})
        logger.info("memory_written", key=key)
    return {}
