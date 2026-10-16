import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from person_agents.runtime.state import StateStore, create_state_store

logger = structlog.get_logger()


class QuotaExceededError(RuntimeError):
    pass


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
    def __init__(
        self,
        state_store: StateStore | None = None,
        llm_capacity: int = 10,
        llm_refill_rate: float = 1.0,
        tool_capacity: int = 20,
        tool_refill_rate: float = 2.0,
        max_running_runs: int = 3,
        daily_run_limit: int = 1000,
    ):
        self.state_store = state_store or create_state_store()
        self._llm_capacity = llm_capacity
        self._llm_refill_rate = llm_refill_rate
        self._tool_capacity = tool_capacity
        self._tool_refill_rate = tool_refill_rate
        self._max_running_runs = max_running_runs
        self._daily_run_limit = daily_run_limit

    @staticmethod
    def _day_key(prefix: str, tenant_id: str, owner_user_id: str) -> str:
        today = datetime.now(UTC).strftime("%Y%m%d")
        return f"{prefix}:{today}:{tenant_id}:{owner_user_id}"

    def acquire_run_slot(self, owner_user_id: str = "local", tenant_id: str = "default") -> str:
        daily_key = self._day_key("run_daily", tenant_id, owner_user_id)
        current = self.state_store.get_json(daily_key) or 0
        if current >= self._daily_run_limit:
            raise QuotaExceededError("Daily run quota exceeded")
        slot_key = f"run_slot:{tenant_id}:{owner_user_id}"
        slots = self.state_store.get_json(slot_key) or {}
        if len(slots) >= self._max_running_runs:
            raise QuotaExceededError("Concurrent run quota exceeded")
        slot_id = uuid.uuid4().hex
        slots[slot_id] = time.time()
        self.state_store.set_json(slot_key, slots, ttl_seconds=86400)
        self.state_store.set_json(daily_key, current + 1, ttl_seconds=172800)
        return slot_id

    def release_run_slot(self, slot_id: str, owner_user_id: str = "local", tenant_id: str = "default") -> None:
        slot_key = f"run_slot:{tenant_id}:{owner_user_id}"
        slots = self.state_store.get_json(slot_key) or {}
        slots.pop(slot_id, None)
        self.state_store.set_json(slot_key, slots, ttl_seconds=86400)

    def allow_run(self, owner_user_id: str = "local", tenant_id: str = "default") -> str:
        return self.acquire_run_slot(owner_user_id, tenant_id)

    def record_usage(self, owner_user_id: str = "local", tenant_id: str = "default", tokens: int = 0, cost: float = 0.0) -> None:
        if tokens:
            key = self._day_key("token_daily", tenant_id, owner_user_id)
            self.state_store.set_json(key, (self.state_store.get_json(key) or 0) + tokens, ttl_seconds=172800)
        if cost:
            key = self._day_key("cost_daily", tenant_id, owner_user_id)
            self.state_store.set_json(key, (self.state_store.get_json(key) or 0.0) + cost, ttl_seconds=172800)

    def check_usage(self, owner_user_id: str = "local", tenant_id: str = "default") -> None:
        from person_agents.config.settings import settings

        tokens = self.state_store.get_json(self._day_key("token_daily", tenant_id, owner_user_id)) or 0
        cost = self.state_store.get_json(self._day_key("cost_daily", tenant_id, owner_user_id)) or 0.0
        if tokens > settings.tenant_daily_token_limit:
            raise QuotaExceededError("Daily token quota exceeded")
        if cost > settings.tenant_daily_cost_limit:
            raise QuotaExceededError("Daily cost quota exceeded")
    def allow_llm(self, owner_user_id: str = "local", tenant_id: str = "default") -> bool:
        return self.state_store.acquire_bucket(f"llm:{tenant_id}:{owner_user_id}", self._llm_capacity, self._llm_refill_rate)

    def allow_tool(self, owner_user_id: str = "local", tenant_id: str = "default") -> bool:
        if not hasattr(self, "_tool_buckets"):
            self._tool_buckets = {}
        key = f"{tenant_id}:{owner_user_id}"
        if key not in self._tool_buckets:
            self._tool_buckets[key] = TokenBucket(self._tool_capacity, self._tool_refill_rate)
        return self._tool_buckets[key].try_acquire()
