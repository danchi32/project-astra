"""BitLocker recovery key escrow (2a+): the key an admin needs to unlock a drive when a PC asks.

What SAVIO does, and does not, do with the password:
* It is stored encrypted with the platform key (`app.core.crypto`). Without that key the agent
  is refused (503) and retries later, rather than a plaintext key being written.
* A list never returns it. Only an explicit reveal by an org admin does, and every reveal is
  audited with who, which device, which drive and which key. The audit never holds the password.
* A device re-sending a key it already escrowed is a no-op: the key does not change for a given
  protector, so there is nothing to update and no extra copy to keep.
"""
import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models import Device, DeviceBitLockerKey, User
from app.models.base import utcnow
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError, ValidationError

_DRIVE = re.compile(r"^[A-Z]:$")
_PROTECTOR = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# The 48-digit recovery password BitLocker prints: eight groups of six digits.
_RECOVERY = re.compile(r"^\d{6}(-\d{6}){7}$")

MAX_KEYS_PER_PUSH = 10


def normalize_protector(value: str) -> str:
    """BitLocker writes protector IDs in braces and upper case; store one form."""
    return value.strip().strip("{}").lower()


class BitLockerKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(self, device: Device, items: list[tuple[str, str, str]]) -> int:
        """Escrow the keys a device reported. Returns how many were new."""
        if len(items) > MAX_KEYS_PER_PUSH:
            raise ValidationError(f"At most {MAX_KEYS_PER_PUSH} keys per report.")
        cleaned: list[tuple[str, str, str]] = []
        for drive, protector, password in items:
            drive = drive.strip().upper()
            protector = normalize_protector(protector)
            password = password.strip()
            if not _DRIVE.match(drive):
                raise ValidationError(f"'{drive}' is not a drive letter.")
            if not _PROTECTOR.match(protector):
                raise ValidationError("A key ID is not a valid protector ID.")
            if not _RECOVERY.match(password):
                raise ValidationError("A recovery password is not in the 48-digit form.")
            cleaned.append((drive, protector, password))

        stored = 0
        for drive, protector, password in cleaned:
            existing = await self.session.scalar(select(DeviceBitLockerKey.id).where(
                DeviceBitLockerKey.device_id == device.id,
                DeviceBitLockerKey.drive == drive,
                DeviceBitLockerKey.protector_id == protector,
            ))
            if existing is not None:
                continue
            # Raises CryptoUnavailable when no key is configured: nothing is written in clear.
            self.session.add(DeviceBitLockerKey(
                device_id=device.id, org_id=device.org_id, drive=drive, protector_id=protector,
                recovery_password_enc=crypto.encrypt(password), escrowed_at=utcnow(),
            ))
            stored += 1

        if stored:
            await AuditService(self.session).record(
                org_id=device.org_id, actor_id=None, action="device.bitlocker_key_escrow",
                target_type="device", target_id=str(device.id),
                detail={"new_keys": stored, "drives": sorted({d for d, _, _ in cleaned})},
            )
        await self.session.commit()
        return stored

    async def list_for_device(self, *, actor: User, device_id: uuid.UUID) -> list[DeviceBitLockerKey]:
        await self._device(actor, device_id)
        result = await self.session.execute(
            select(DeviceBitLockerKey).where(DeviceBitLockerKey.device_id == device_id)
            .order_by(DeviceBitLockerKey.drive, DeviceBitLockerKey.escrowed_at)
        )
        return list(result.scalars().all())

    async def reveal(self, *, actor: User, device_id: uuid.UUID, key_id: uuid.UUID) -> dict:
        """Decrypt one key for an admin. The reveal itself is the audited event."""
        device = await self._device(actor, device_id)
        row = await self.session.get(DeviceBitLockerKey, key_id)
        if row is None or row.device_id != device.id or row.org_id != actor.org_id:
            raise NotFoundError("Recovery key not found")
        password = crypto.decrypt(row.recovery_password_enc)
        await AuditService(self.session).record(
            org_id=actor.org_id, actor_id=actor.id, action="device.bitlocker_key_reveal",
            target_type="device", target_id=str(device.id),
            detail={"drive": row.drive, "protector_id": row.protector_id, "by": actor.email},
        )
        await self.session.commit()
        return {"drive": row.drive, "protector_id": row.protector_id, "recovery_password": password,
                "escrowed_at": row.escrowed_at}

    async def _device(self, actor: User, device_id: uuid.UUID) -> Device:
        device = await self.session.get(Device, device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found")
        return device
