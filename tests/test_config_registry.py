from pathlib import Path

from person_agents.memory.sqlite_store import SQLiteStore
from person_agents.runtime.config_registry import ConfigRegistry


def test_config_registry_immutability_and_dedup(tmp_path: Path) -> None:
    registry = ConfigRegistry(SQLiteStore(tmp_path / "config.db"))
    first = registry.register("prompt", "template-v1")
    second = registry.register("prompt", "template-v1")
    assert first.version_id == second.version_id
    assert registry.get("prompt", first.version_id).content == "template-v1"
    assert registry.latest("prompt").version_id == first.version_id

    changed = registry.register("prompt", "template-v2")
    assert changed.version_id != first.version_id
    assert registry.get("prompt", first.version_id).content == "template-v1"


def test_register_defaults(tmp_path: Path) -> None:
    registry = ConfigRegistry(SQLiteStore(tmp_path / "defaults.db"))
    versions = registry.register_defaults()
    assert set(versions) == {"prompt", "tool", "policy"}
    assert all(registry.get(kind, version_id) for kind, version_id in versions.items())
