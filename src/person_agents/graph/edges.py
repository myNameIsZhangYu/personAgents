from person_agents.graph.state import AgentState

MAX_RETRIES = 3


def route_after_intent(state: AgentState) -> str:
    if state["intent"] == "chat":
        return "executor"
    if state["intent"] == "memory_write":
        return "memory_write"
    if state["intent"] == "task":
        return "planner"
    if state["intent"] == "tool_use":
        return "planner"
    return "planner"


def route_after_critic(state: AgentState) -> str:
    retry_count = state.get("retry_count", 0)
    if state["critic_feedback"] == "retry" and retry_count < MAX_RETRIES:
        return "executor"
    return "memory_write"


def route_after_executor(state: AgentState) -> str:
    if state["current_step"] < len(state.get("plan", [])):
        return "executor"
    return "critic"
