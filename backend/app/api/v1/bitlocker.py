"""BitLocker recovery keys for an admin (2a+). Metadata lists freely to admins; the password
itself only comes from an explicit, audited reveal, which a view-as session cannot make."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import deny_view_as, require_roles
from app.core import crypto
from app.core.database import get_db
from app.models import User, UserRole
from app.services.bitlocker_keys import BitLockerKeyService

router = APIRouter(prefix="/devices", tags=["bitlocker"])

admin_required_for_keys = require_roles(UserRole.ADMIN)


class BitLockerKeyRead(BaseModel):
    id: uuid.UUID
    drive: str
    protector_id: str
    escrowed_at: datetime


class BitLockerKeyRevealed(BaseModel):
    drive: str
    protector_id: str
    recovery_password: str
    escrowed_at: datetime


@router.get(
    "/{device_id}/bitlocker-keys",
    response_model=list[BitLockerKeyRead],
    summary="BitLocker recovery key IDs escrowed from a device (admin; no passwords)",
)
async def list_bitlocker_keys(
    device_id: uuid.UUID,
    actor: User = Depends(admin_required_for_keys),
    session: AsyncSession = Depends(get_db),
) -> list[BitLockerKeyRead]:
    rows = await BitLockerKeyService(session).list_for_device(actor=actor, device_id=device_id)
    return [BitLockerKeyRead(id=r.id, drive=r.drive, protector_id=r.protector_id,
                             escrowed_at=r.escrowed_at) for r in rows]


@router.post(
    "/{device_id}/bitlocker-keys/{key_id}/reveal",
    response_model=BitLockerKeyRevealed,
    summary="Reveal one BitLocker recovery password (admin; audited every time)",
)
async def reveal_bitlocker_key(
    device_id: uuid.UUID,
    key_id: uuid.UUID,
    actor: User = Depends(admin_required_for_keys),
    _: User = Depends(deny_view_as),
    session: AsyncSession = Depends(get_db),
) -> BitLockerKeyRevealed:
    try:
        data = await BitLockerKeyService(session).reveal(actor=actor, device_id=device_id, key_id=key_id)
    except crypto.CryptoUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Key escrow is not configured on this server.")
    except crypto.DecryptionFailed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="The stored key cannot be decrypted with the current platform key.")
    return BitLockerKeyRevealed(**data)
