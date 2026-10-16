
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from person_agents.config.settings import settings
from person_agents.graph.edges import route_after_critic, route_after_executor, route_after_intent
from person_agents.graph.nodes import (
    critic_node,
    executor_node,
    intent_node,
    memory_write_node,
    planner_node,
)
from person_agents.graph.state import AgentState
from person_agents.security.context import RequestContext


def build_graph(checkpointer: AsyncSqliteSaver | None = None):
    builder = StateGraph(AgentState)
    builder.add_node("intent", intent_node)
    builder.add_node("planner", planner_node)
    builder.add_node("executor", executor_node)
    builder.add_node("critic", critic_node)
    builder.add_node("memory_write", memory_write_node)

    builder.set_entry_point("intent")
    builder.add_conditional_edges("intent", route_after_intent, {"planner": "planner", "executor": "executor", "memory_write": "memory_write"})
    builder.add_conditional_edges("executor", route_after_executor, {"executor": "executor", "critic": "critic"})
    builder.add_conditional_edges("critic", route_after_critic, {"executor": "executor", "memory_write": "memory_write"})
    builder.add_edge("planner", "executor")
    builder.add_edge("memory_write", END)

    if checkpointer is None:
        import aiosqlite
        conn = aiosqlite.connect(str(settings.sqlite_path))
        checkpointer = AsyncSqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)


async def run_graph(user_input: str, session_id: str = "cli", context: RequestContext | None = None) -> AgentState:
    context = context or RequestContext(user_id=session_id, tenant_id="default", session_id=session_id)
    graph = build_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": user_input}],
        "intent": "",
        "plan": [],
        "current_step": 0,
        "tool_results": [],
        "critic_feedback": "",
        "memory_context": [],
        "status": "",
        "degraded": False,
        "error": None,
        "retry_count": 0,
        "session_id": context.session_id,
        "tenant_id": context.tenant_id,
        "owner_user_id": context.user_id,
    }
    config = {"configurable": {"thread_id": session_id}}
    result = await graph.ainvoke(initial_state, config)
    return result
