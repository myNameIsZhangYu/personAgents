import pytest

from person_agents.config.settings import Settings
from person_agents.config.validation import ConfigurationError, validate_production_settings


def _valid_settings(**overrides) -> Settings:
    values = {
        "api_key_hash": "a" * 64,
        "redis_url": "redis://redis:6379/0",
        "openai_api_key": "sk-test",
        "langfuse_public_key": "pk-lf-test",
        "langfuse_secret_key": "sk-lf-test",
        "nextauth_secret": "nextauth-secret-0123456789abcdef",
        "salt": "salt-secret-0123456789abcdef0123456789",
        "encryption_key": "encryption-secret-0123456789abcdef",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_production_settings() -> None:
    validate_production_settings(_valid_settings())


def test_missing_required_and_defaults() -> None:
    with pytest.raises(ConfigurationError, match="required"):
        validate_production_settings(Settings())
    with pytest.raises(ConfigurationError, match="Default production secrets"):
        validate_production_settings(_valid_settings(salt="minioadmin"))
    with pytest.raises(ConfigurationError, match="must be at least 32"):
        validate_production_settings(_valid_settings(nextauth_secret="short"))
    with pytest.raises(ConfigurationError, match="must be unique"):
        validate_production_settings(_valid_settings(salt="same-secret-0123456789abcdef", encryption_key="same-secret-0123456789abcdef"))
