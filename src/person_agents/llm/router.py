from enum import StrEnum


class TaskComplexity(StrEnum):
    SIMPLE = "simple"
    COMPLEX = "complex"


def route_task(text: str) -> TaskComplexity:
    simple_keywords = {"hi", "hello", "thanks", "what time", "list", "read", "summarize"}
    lower = text.lower().strip()
    if any(lower.startswith(k) for k in simple_keywords) and len(lower) < 100:
        return TaskComplexity.SIMPLE
    return TaskComplexity.COMPLEX
