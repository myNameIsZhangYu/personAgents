from person_agents.runtime.state import InMemoryStateStore
from person_agents.security.confirmation import ConfirmationStore


def test_confirmation_one_time() -> None:
    store = ConfirmationStore(InMemoryStateStore(), ttl_seconds=60)
    confirmation = store.create("user", "tenant", "filesystem", {"operation": "write"})
    assert store.get(confirmation.token) is not None
    assert store.consume(confirmation.token) is not None
    assert store.consume(confirmation.token) is None


def test_expired_confirmation() -> None:
    store = ConfirmationStore(InMemoryStateStore(), ttl_seconds=0)
    confirmation = store.create("user", "tenant", "filesystem", {"operation": "write"})
    assert store.get(confirmation.token) is None
