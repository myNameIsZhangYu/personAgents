from pydantic import BaseModel, Field


class Provenance(BaseModel):
    agent_version: str
    prompt_version: str
    tool_config_version: str
    policy_version: str


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None


class RunResponse(BaseModel):
    session_id: str
    status: str
    output: str | None = None
    confirmation_token: str | None = None
    provenance: Provenance | None = None


class RunAcceptedResponse(BaseModel):
    run_id: str
    status: str
    session_id: str
