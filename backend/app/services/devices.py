import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models import Device, EnrollmentToken, User
from app.models.base import as_utc, utcnow
from app.repositories.devices import DeviceRepository
from app.repositories.enrollment_tokens import EnrollmentTokenRepository
from app.schemas.devices import (
    AgentInstallerRequest,
    AgentInstallerResponse,
    DeviceUpdate,
    EnrollmentTokenCreate,
    EnrollRequest,
    HeartbeatRequest,
)
from app.services.agent_installer import build_install_script
from app.services.audit import AuditService
from app.services.exceptions import AuthenticationError, NotFoundError
from app.services.settings import SettingsService


class DeviceService:
    """Portal-facing operations are scoped to the actor's organization; agent-facing
    operations (enroll, heartbeat) authenticate with enrollment/device tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.enrollment_tokens = EnrollmentTokenRepository(session)
        self.audit = AuditService(session)
        self.settings = SettingsService(session)

    # -- Enrollment tokens (admin) --------------------------------------------

    async def create_enrollment_token(
        self, *, actor: User, data: EnrollmentTokenCreate
    ) -> tuple[EnrollmentToken, str]:
        raw = generate_opaque_token()
        days = data.expires_in_days
        if days is None:
            days = (await self.settings.ensure(actor.org_id)).enrollment_token_default_days
        record = await self.enrollment_tokens.add(
            EnrollmentToken(
                org_id=actor.org_id,
                name=data.name,
                token_hash=hash_opaque_token(raw),
                expires_at=utcnow() + timedelta(days=days),
                created_by=actor.id,
            )
        )
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="enrollment_token.create",
            target_type="enrollment_token",
            target_id=str(record.id),
            detail={"name": data.name, "expires_in_days": days},
        )
        await self.session.commit()
        return record, raw

    async def generate_agent_installer(
        self, *, actor: User, data: AgentInstallerRequest
    ) -> AgentInstallerResponse:
        """Mint a fresh enrollment token and return a pre-configured install script."""
        server_url = (data.server_url or get_settings().public_api_url).rstrip("/")
        record, raw = await self.create_enrollment_token(
            actor=actor,
            data=EnrollmentTokenCreate(name=data.name, expires_in_days=data.expires_in_days),
        )
        script = build_install_script(server_url=server_url, enrollment_token=raw)
        return AgentInstallerResponse(
            token=raw,
            server_url=server_url,
            filename="Install-AstraAgent.ps1",
            script=script,
            expires_at=record.expires_at,
        )

    async def list_enrollment_tokens(self, *, actor: User) -> list[EnrollmentToken]:
        return await self.enrollment_tokens.list_by_org(actor.org_id)

    async def revoke_enrollment_token(self, *, actor: User, token_id: uuid.UUID) -> None:
        record = await self.enrollment_tokens.get(token_id)
        if record is None or record.org_id != actor.org_id:
            raise NotFoundError("Enrollment token not found")
        if record.revoked_at is None:
            record.revoked_at = utcnow()
            await self.audit.record(
                org_id=actor.org_id,
                actor_id=actor.id,
                action="enrollment_token.revoke",
                target_type="enrollment_token",
                target_id=str(record.id),
                detail={"name": record.name},
            )
        await self.session.commit()

    # -- Agent-facing ----------------------------------------------------------

    async def enroll(self, data: EnrollRequest) -> tuple[Device, str]:
        record = await self.enrollment_tokens.get_by_hash(
            hash_opaque_token(data.enrollment_token)
        )
        if (
            record is None
            or record.revoked_at is not None
            or as_utc(record.expires_at) <= utcnow()
        ):
            raise AuthenticationError("Invalid or expired enrollment token")

        raw_device_token = generate_opaque_token()
        device = await self.devices.get_by_machine_id(record.org_id, data.machine_id)

        if device is not None and not device.is_active:
            # Decommissioned hardware must not silently rejoin; an admin must
            # delete the device record first.
            raise AuthenticationError("Device is decommissioned")

        if device is None:
            device = await self.devices.add(
                Device(
                    org_id=record.org_id,
                    hostname=data.hostname,
                    machine_id=data.machine_id,
                    os_version=data.os_version,
                    serial_number=data.serial_number,
                    agent_version=data.agent_version,
                    token_hash=hash_opaque_token(raw_device_token),
                )
            )
            action = "device.enroll"
        else:
            # Re-enrollment (agent reinstall): rotate the credential, refresh facts.
            device.hostname = data.hostname
            device.os_version = data.os_version
            device.serial_number = data.serial_number
            device.agent_version = data.agent_version
            device.token_hash = hash_opaque_token(raw_device_token)
            action = "device.re_enroll"

        await self.audit.record(
            org_id=record.org_id,
            actor_id=None,
            action=action,
            target_type="device",
            target_id=str(device.id),
            detail={"hostname": data.hostname, "machine_id": data.machine_id},
        )
        await self.session.commit()
        return device, raw_device_token

    async def heartbeat(self, *, device: Device, data: HeartbeatRequest) -> None:
        device.last_seen_at = utcnow()
        device.agent_version = data.agent_version
        device.logged_in_user = data.logged_in_user
        await self.session.commit()

    # -- Portal-facing (staff/admin) -------------------------------------------

    async def list_devices(self, *, actor: User) -> list[Device]:
        return await self.devices.list_by_org(actor.org_id)

    async def get_device(self, *, actor: User, device_id: uuid.UUID) -> Device:
        device = await self.devices.get(device_id)
        if device is None or device.org_id != actor.org_id:
            raise NotFoundError("Device not found")
        return device

    async def update_device(
        self, *, actor: User, device_id: uuid.UUID, data: DeviceUpdate
    ) -> Device:
        device = await self.get_device(actor=actor, device_id=device_id)
        if data.is_active is not None and data.is_active != device.is_active:
            device.is_active = data.is_active
            await self.audit.record(
                org_id=actor.org_id,
                actor_id=actor.id,
                action="device.decommission" if not data.is_active else "device.reactivate",
                target_type="device",
                target_id=str(device.id),
                detail={"hostname": device.hostname},
            )
        await self.session.commit()
        return device

    async def delete_device(self, *, actor: User, device_id: uuid.UUID) -> None:
        device = await self.get_device(actor=actor, device_id=device_id)
        hostname = device.hostname
        await self.devices.delete(device)
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="device.delete",
            target_type="device",
            target_id=str(device_id),
            detail={"hostname": hostname},
        )
        await self.session.commit()
