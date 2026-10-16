import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass
class Confirmation:
    token: str
    owner_user_id: str
    tenant_id: str
    tool_name: str
    arguments: dict[str, Any]
    expires_at: float


class StateStore(Protocol):
    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...
    def get_json(self, key: str) -> Any | None: ...
    def delete(self, key: str) -> None: ...
    def acquire_bucket(self, key: str, capacity: int, refill_rate: float) -> bool: ...
    def store_confirmation(self, confirmation: Confirmation, ttl_seconds: int) -> Confirmation: ...
    def get_confirmation(self, token: str) -> Confirmation | None: ...
    def consume_confirmation(self, token: str) -> Confirmation | None: ...


class InMemoryStateStore:
    def __init__(self) -> None:
        self._values: dict[str, tuple[Any, float | None]] = {}

    @staticmethod
    def _bucket_state(value: tuple[Any, float | None]) -> tuple[Any, float | None]:
        return value

    def _expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and expires_at < time.time()

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._values[key] = (value, time.time() + ttl_seconds if ttl_seconds else None)

    def get_json(self, key: str) -> Any | None:
        item = self._values.get(key)
        if item is None or self._expired(item[1]):
            self._values.pop(key, None)
            return None
        return item[0]

    def delete(self, key: str) -> None:
        self._values.pop(key, None)

    def acquire_bucket(self, key: str, capacity: int, refill_rate: float) -> bool:
        now = time.monotonic()
        state = self.get_json(f"bucket:{key}")
        tokens = float(capacity) if state is None else float(state["tokens"])
        last = now if state is None else float(state["last"])
        tokens = min(float(capacity), tokens + (now - last) * refill_rate)
        if tokens < 1:
            self.set_json(f"bucket:{key}", {"tokens": tokens, "last": now})
            return False
        self.set_json(f"bucket:{key}", {"tokens": tokens - 1, "last": now})
        return True

    def store_confirmation(self, confirmation: Confirmation, ttl_seconds: int) -> Confirmation:
        ttl = max(1, int(confirmation.expires_at - time.time()))
        self.set_json(f"confirmation:{confirmation.token}", asdict(confirmation), ttl_seconds=ttl or ttl_seconds)
        return confirmation

    def get_confirmation(self, token: str) -> Confirmation | None:
        value = self.get_json(f"confirmation:{token}")
        if value is None:
            return None
        confirmation = Confirmation(**value)
        if confirmation.expires_at < time.time():
            self.delete(f"confirmation:{token}")
            return None
        return confirmation

    def consume_confirmation(self, token: str) -> Confirmation | None:
        confirmation = self.get_confirmation(token)
        if confirmation is None:
            return None
        self.delete(f"confirmation:{token}")
        return confirmation


class RedisStateStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value)
        if ttl_seconds:
            self._client.set(key, payload, ex=ttl_seconds)
        else:
            self._client.set(key, payload)

    def get_json(self, key: str) -> Any | None:
        value = self._client.get(key)
        return json.loads(value) if value is not None else None

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def acquire_bucket(self, key: str, capacity: int, refill_rate: float) -> bool:
        name = f"bucket:{key}"
        with self._client.pipeline() as pipe:
            try:
                pipe.watch(name)
                value = pipe.get(name)
                if value is None:
                    tokens, last = float(capacity), time.monotonic()
                else:
                    state = json.loads(value)
                    tokens, last = float(state["tokens"]), float(state["last"])
                now = time.monotonic()
                tokens = min(float(capacity), tokens + (now - last) * refill_rate)
                if tokens < 1:
                    pipe.multi()
                    pipe.set(name, json.dumps({"tokens": tokens, "last": now}))
                    pipe.execute()
                    return False
                pipe.multi()
                pipe.set(name, json.dumps({"tokens": tokens - 1, "last": now}))
                pipe.execute()
                return True
            except Exception:
                pipe.unwatch()
                raise

    def store_confirmation(self, confirmation: Confirmation, ttl_seconds: int) -> Confirmation:
        self.set_json(f"confirmation:{confirmation.token}", asdict(confirmation), ttl_seconds=ttl_seconds)
        return confirmation

    def get_confirmation(self, token: str) -> Confirmation | None:
        value = self.get_json(f"confirmation:{token}")
        return Confirmation(**value) if value else None

    def consume_confirmation(self, token: str) -> Confirmation | None:
        name = f"confirmation:{token}"
        value = self._client.getdel(name)
        if value is None:
            return None
        confirmation = Confirmation(**json.loads(value))
        if confirmation.expires_at < time.time():
            return None
        return confirmation


def create_state_store(redis_url: str = "") -> StateStore:
    if redis_url:
        import redis

        return RedisStateStore(redis.Redis.from_url(redis_url, decode_responses=True))
    return InMemoryStateStore()
