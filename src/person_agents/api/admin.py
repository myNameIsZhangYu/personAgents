import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException

from person_agents.api.schemas import (
    CredentialResponse,
    CredentialRevokeRequest,
    CredentialRotateRequest,
)
from person_agents.config.settings import settings
from person_agents.security.credentials import CredentialManager

router = APIRouter(prefix="/admin/credentials", tags=["admin"])


async def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if not x_admin_key or not settings.admin_api_key_hash:
        raise HTTPException(status_code=401, detail="Admin authentication required")
    if hashlib.sha256(x_admin_key.encode()).hexdigest() != settings.admin_api_key_hash:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def credential_manager() -> CredentialManager:
    return CredentialManager(settings.sqlite_path.parent / "credentials.db")


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(
    tenant_id: str,
    user_id: str,
    _: None = Depends(require_admin),
) -> CredentialResponse:
    key_id, plaintext = credential_manager().create(tenant_id, user_id)
    return CredentialResponse(key_id=key_id, plaintext=plaintext)


@router.post("/rotate", response_model=CredentialResponse)
async def rotate_credential(
    request: CredentialRotateRequest,
    _: None = Depends(require_admin),
) -> CredentialResponse:
    result = credential_manager().rotate(request.key_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    key_id, plaintext = result
    return CredentialResponse(key_id=key_id, plaintext=plaintext)


@router.post("/revoke", status_code=204)
async def revoke_credential(
    request: CredentialRevokeRequest,
    _: None = Depends(require_admin),
) -> None:
    if not credential_manager().revoke(request.key_id):
        raise HTTPException(status_code=404, detail="Credential not found")
