import secrets
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class Confirmation:
    token: str
    owner_user_id: str
    tenant_id: str
    tool_name: str
    arguments: dict[str, Any]
    expires_at: float


class ConfirmationStore:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, Confirmation] = {}

    def create(self, owner_user_id: str, tenant_id: str, tool_name: str, arguments: dict[str, Any]) -> Confirmation:
        token = secrets.token_urlsafe(32)
        confirmation = Confirmation(
            token=token,
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            arguments=arguments,
            expires_at=time.time() + self.ttl_seconds,
        )
        self._items[token] = confirmation
        return confirmation

    def get(self, token: str) -> Confirmation | None:
        confirmation = self._items.get(token)
        if confirmation and confirmation.expires_at < time.time():
            del self._items[token]
            return None
        return confirmation

    def consume(self, token: str) -> Confirmation | None:
        confirmation = self.get(token)
        if confirmation is None:
            return None
        del self._items[token]
        return confirmation
