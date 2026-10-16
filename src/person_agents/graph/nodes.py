import time
from typing import Any

import structlog

from person_agents.graph.state import AgentState
from person_agents.llm.fallback import call_with_fallback
from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.memory.vector_store import VectorStore
from person_agents.middleware import governed_llm_call, governed_tool_call
from person_agents.observability.langfuse import trace_graph_node
from person_agents.tools.registry import ToolRegistry, register_default_tools

logger = structlog.get_logger()

_store: SQLiteStore | None = None
_vector: VectorStore | None = None
_registry: ToolRegistry | None = None


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


def _get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        register_default_tools(_registry)
    return _registry


async def intent_node(state: AgentState) -> dict[str, Any]:
    started = time.monotonic()
    user_input = state["messages"][-1]["content"]
    memory_hits = _get_vector().query(user_input, n_results=3)
    memory_text = "\n".join(f"- {m['text']}" for m in memory_hits if m.get("text"))
    resp = await call_with_fallback([
        {"role": "system", "content": f"Classify the user's intent as one of: chat, task, memory_write, tool_use. Return ONLY the intent word.\n\nRelevant memory context:\n{memory_text}"},
        {"role": "user", "content": user_input},
    ])
    intent = resp.content.strip().lower()
    if intent not in ("chat", "task", "memory_write", "tool_use"):
        intent = "chat"
    output = {"intent": intent, "degraded": resp.degraded, "memory_context": memory_hits}
    trace_graph_node(state.get("session_id", "agent"), "intent", {"input": user_input}, output, int((time.monotonic() - started) * 1000))
    return output


async def planner_node(state: AgentState) -> dict[str, Any]:
    started = time.monotonic()
    user_input = state["messages"][-1]["content"]
    memory_context = "\n".join(f"- {m['text']}" for m in state.get("memory_context", []) if m.get("text"))
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in _get_registry().list_tools()
    ]
    resp = await call_with_fallback([
        {
            "role": "system",
            "content": (
                "Break the task into executable steps. Return ONLY a JSON array of objects with "
                "'action', 'tool', and optional 'arguments' fields. Use 'none' only for direct LLM actions. "
                f"Available tools: {tools}"
            ),
        },
        {"role": "user", "content": f"Task: {user_input}\nRelevant memory:\n{memory_context}"},
    ])
    import json
    try:
        plan = json.loads(resp.content)
    except json.JSONDecodeError:
        plan = [{"action": user_input, "tool": "none"}]
    output = {"plan": plan, "current_step": 0}
    trace_graph_node(state.get("session_id", "agent"), "planner", {"input": user_input}, output, int((time.monotonic() - started) * 1000))
    return output


async def executor_node(state: AgentState) -> dict[str, Any]:
    started = time.monotonic()
    plan = state.get("plan", [])
    if not plan or state["current_step"] >= len(plan):
        user_input = state["messages"][-1]["content"]
        async def _llm(messages):
            return await call_with_fallback(messages)
        resp = await governed_llm_call([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input},
        ], _llm)
        result = {"step": 0, "action": user_input, "tool": "none", "output": resp.content}
        trace_graph_node(state.get("session_id", "agent"), "executor", {"input": user_input}, result, int((time.monotonic() - started) * 1000))
        return {"tool_results": [result], "current_step": 1}

    step = state["plan"][state["current_step"]]
    action = step.get("action", "")
    tool = step.get("tool", "none")
    context = "\n".join(m["text"] for m in state.get("memory_context", []))

    if tool != "none":
        tool_def = _get_registry().get(tool)
        if tool_def:
            arguments = step.get("arguments") or {"operation": "read", "path": action.strip()}
            if not isinstance(arguments, dict):
                arguments = {"operation": "read", "path": action.strip()}
            try:
                tool_result = await governed_tool_call(tool, arguments, tool_def.handler)
                output = str(tool_result)
            except (PermissionError, RuntimeError) as exc:
                output = f"Tool execution rejected: {exc}"
                if state["current_step"] + 1 >= len(plan):
                    return {
                        "tool_results": [result],
                        "current_step": len(plan),
                        "critic_feedback": "fail",
                        "status": "fail",
                        "error": str(exc),
                    }
        else:
            output = f"Unknown tool: {tool}"
    else:
        async def _llm(messages):
            return await call_with_fallback(messages)
        resp = await governed_llm_call([
            {"role": "system", "content": f"Execute the action. Relevant context:\n{context}"},
            {"role": "user", "content": action},
        ], _llm)
        output = resp.content

    result = {"step": state["current_step"], "action": action, "tool": tool, "output": output}
    trace_graph_node(state.get("session_id", "agent"), "executor", {"input": action, "tool": tool}, result, int((time.monotonic() - started) * 1000))
    return {"tool_results": [result], "current_step": state["current_step"] + 1}


async def critic_node(state: AgentState) -> dict[str, Any]:
    started = time.monotonic()
    results_summary = "\n".join(r["output"][:200] for r in state.get("tool_results", []))
    resp = await call_with_fallback([
        {"role": "system", "content": "Evaluate if the task was completed successfully. Return 'success' or 'retry' or 'fail'."},
        {"role": "user", "content": results_summary},
    ])
    feedback = resp.content.strip().lower()
    output = {"critic_feedback": feedback, "status": feedback}
    trace_graph_node(state.get("session_id", "agent"), "critic", {"results": results_summary}, output, int((time.monotonic() - started) * 1000))
    return output


async def memory_write_node(state: AgentState) -> dict[str, Any]:
    if state.get("critic_feedback") == "success":
        user_input = state["messages"][-1]["content"]
        result = state["tool_results"][-1]["output"][:300]
        key = f"memory_{hash(user_input)}"
        _get_store().upsert(key, result, category="experience")
        _get_vector().add(result, {"source": "agent", "session": state.get("session_id", "")})
        logger.info("memory_written", key=key)
    return {}
