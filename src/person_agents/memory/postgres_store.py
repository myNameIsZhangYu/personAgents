from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from person_agents.config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL,
    owner_user_id TEXT NOT NULL DEFAULT 'local',
    tenant_id TEXT NOT NULL DEFAULT 'default',
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'fact',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, owner_user_id, key)
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    confirmation_token TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts INTEGER NOT NULL DEFAULT 0,
    agent_version TEXT,
    prompt_version TEXT,
    tool_config_version TEXT,
    policy_version TEXT,
    metadata_json TEXT,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_runs_owner_pg ON runs(tenant_id, owner_user_id, status);
"""


class PostgresStore:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or settings.postgres_dsn
        self.engine: AsyncEngine = create_async_engine(
            self.dsn,
            pool_size=settings.postgres_pool_size,
            max_overflow=settings.postgres_max_overflow,
        )

    async def bootstrap(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(SCHEMA))

    async def create_run(
        self,
        run_id: str,
        prompt: str,
        owner_user_id: str,
        tenant_id: str,
        session_id: str,
        status: str = "queued",
        provenance: dict[str, str] | None = None,
    ) -> None:
        provenance = provenance or {}
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """INSERT INTO runs (
                        run_id,tenant_id,owner_user_id,session_id,prompt,status,
                        agent_version,prompt_version,tool_config_version,policy_version,metadata_json
                    ) VALUES (:run_id,:tenant_id,:owner_user_id,:session_id,:prompt,:status,
                        :agent_version,:prompt_version,:tool_config_version,:policy_version,:metadata_json)"""
                ),
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "owner_user_id": owner_user_id,
                    "session_id": session_id,
                    "prompt": prompt,
                    "status": status,
                    "agent_version": provenance.get("agent_version"),
                    "prompt_version": provenance.get("prompt_version"),
                    "tool_config_version": provenance.get("tool_config_version"),
                    "policy_version": provenance.get("policy_version"),
                    "metadata_json": provenance.get("metadata_json"),
                },
            )

    async def update_run(
        self,
        run_id: str,
        owner_user_id: str,
        tenant_id: str,
        status: str,
        output: str | None = None,
        confirmation_token: str | None = None,
        error: str | None = None,
        total_tokens: int = 0,
        total_cost: float = 0.0,
    ) -> bool:
        async with self.engine.begin() as conn:
            result = await conn.execute(
                text(
                    """UPDATE runs SET status=:status,output=:output,confirmation_token=:confirmation_token,
                        error=:error,total_tokens=total_tokens+:total_tokens,
                        total_cost_usd=total_cost_usd+:total_cost,updated_at=now()
                        WHERE run_id=:run_id AND owner_user_id=:owner_user_id AND tenant_id=:tenant_id"""
                ),
                {
                    "status": status,
                    "output": output,
                    "confirmation_token": confirmation_token,
                    "error": error,
                    "total_tokens": total_tokens,
                    "total_cost": total_cost,
                    "run_id": run_id,
                    "owner_user_id": owner_user_id,
                    "tenant_id": tenant_id,
                },
            )
            return result.rowcount > 0

    async def get_run(self, run_id: str, owner_user_id: str, tenant_id: str) -> dict[str, Any] | None:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT * FROM runs WHERE run_id=:run_id AND owner_user_id=:owner_user_id AND tenant_id=:tenant_id"),
                    {"run_id": run_id, "owner_user_id": owner_user_id, "tenant_id": tenant_id},
                )
            ).mappings().first()
            return dict(row) if row else None

    async def upsert_memory(self, key: str, value: str, category: str, owner_user_id: str, tenant_id: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """INSERT INTO memories (key,value,category,owner_user_id,tenant_id)
                        VALUES (:key,:value,:category,:owner_user_id,:tenant_id)
                        ON CONFLICT (tenant_id,owner_user_id,key)
                        DO UPDATE SET value=EXCLUDED.value,category=EXCLUDED.category,updated_at=now()"""
                ),
                {"key": key, "value": value, "category": category, "owner_user_id": owner_user_id, "tenant_id": tenant_id},
            )

    async def depth(self, status: str) -> int:
        async with self.engine.connect() as conn:
            return int((await conn.execute(text("SELECT count(*) FROM runs WHERE status=:status"), {"status": status})).scalar_one())
