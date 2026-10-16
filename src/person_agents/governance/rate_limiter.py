import time
from dataclasses import dataclass, field

import structlog

from person_agents.runtime.state import StateStore, create_state_store

logger = structlog.get_logger()


@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float
    tokens: float = 0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if self.tokens == 0:
            self.tokens = self.capacity

    def try_acquire(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimiter:
    def __init__(self, state_store: StateStore | None = None, llm_capacity: int = 10, llm_refill_rate: float = 1.0, tool_capacity: int = 20, tool_refill_rate: float = 2.0):
        self.state_store = state_store or create_state_store()
        self._llm_capacity = llm_capacity
        self._llm_refill_rate = llm_refill_rate
        self._tool_capacity = tool_capacity
        self._tool_refill_rate = tool_refill_rate
    def allow_llm(self, owner_user_id: str = "local", tenant_id: str = "default") -> bool:
        return self.state_store.acquire_bucket(f"llm:{tenant_id}:{owner_user_id}", self._llm_capacity, self._llm_refill_rate)

    def allow_tool(self, owner_user_id: str = "local", tenant_id: str = "default") -> bool:
        return self._tool_buckets[f"{tenant_id}:{owner_user_id}"].try_acquire()
