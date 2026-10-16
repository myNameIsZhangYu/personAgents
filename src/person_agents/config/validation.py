from person_agents.config.settings import Settings


class ConfigurationError(RuntimeError):
    pass


def validate_production_settings(config: Settings) -> None:
    errors: list[str] = []
    if not config.api_key_hash:
        errors.append("PERSON_AGENTS_API_KEY_HASH is required")
    if not config.redis_url:
        errors.append("PERSON_AGENTS_REDIS_URL is required")
    if not config.openai_api_key:
        errors.append("OPENAI_API_KEY is required")
    if not config.langfuse_public_key or not config.langfuse_secret_key:
        errors.append("Langfuse keys are required")
    if not config.nextauth_secret:
        errors.append("NEXTAUTH_SECRET is required")

    secrets = [
        config.nextauth_secret,
        config.salt,
        config.encryption_key,
        config.langfuse_secret_key,
    ]
    for name, value in (
        ("NEXTAUTH_SECRET", config.nextauth_secret),
        ("SALT", config.salt),
        ("ENCRYPTION_KEY", config.encryption_key),
    ):
        if value and len(value) < 32:
            errors.append(f"{name} must be at least 32 characters")

    values = [value for value in secrets if value]
    if len(values) != len({value for value in values}):
        errors.append("Production secrets must be unique")
    if any(value in {"langfuse", "minioadmin", "changeme"} for value in secrets):
        errors.append("Default production secrets are forbidden")

    if errors:
        raise ConfigurationError("; ".join(errors))
