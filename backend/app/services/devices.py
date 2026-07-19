import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models import Device, EnrollmentToken, Organization, User
from app.models.base import as_utc, utcnow
from app.repositories.devices import DeviceRepository
from app.repositories.enrollment_tokens import EnrollmentTokenRepository
from app.repositories.organizations import OrganizationRepository
from app.schemas.devices import (
    DeviceUpdate,
    EnrollmentTokenCreate,
    EnrollRequest,
    HeartbeatRequest,
    InstallerRead,
)
from app.services.agent_installer import build_install_script, build_offline_bundle_zip
from app.services.audit import AuditService
from app.services.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.services.settings import SettingsService


class DeviceService:
    """Portal-facing operations are scoped to the actor's organization; agent-facing
    operations (enroll, heartbeat) authenticate with enrollment/device tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.enrollment_tokens = EnrollmentTokenRepository(session)
        self.orgs = OrganizationRepository(session)
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

    # -- Installer (permanent per-org key; no tokens, no expiry) ---------------

    async def _ensure_enrollment_key(self, org_id: uuid.UUID):
        """Return the org's permanent enrollment key, provisioning one on first use
        (covers orgs created before this feature)."""
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        if not org.agent_enrollment_key:
            org.agent_enrollment_key = generate_opaque_token()
            await self.session.commit()
        return org

    async def get_installer(self, *, actor: User) -> InstallerRead:
        """The org's ready-to-run installer — the permanent enrollment key is already
        baked in, so an admin just downloads and runs it. No token, no expiry."""
        org = await self._ensure_enrollment_key(actor.org_id)
        server_url = get_settings().public_api_url.rstrip("/")
        script = build_install_script(server_url=server_url, enrollment_token=org.agent_enrollment_key)
        return InstallerRead(
            enrollment_key=org.agent_enrollment_key,
            server_url=server_url,
            filename="Install-AstraAgent.ps1",
            script=script,
        )

    async def rotate_enrollment_key(self, *, actor: User) -> InstallerRead:
        """Regenerate the org's enrollment key (break-glass if an installer leaks).
        Old installers stop enrolling; the admin re-downloads the new one."""
        org = await self.orgs.get(actor.org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        org.agent_enrollment_key = generate_opaque_token()
        await self.audit.record(
            org_id=actor.org_id,
            actor_id=actor.id,
            action="enrollment_key.rotate",
            target_type="organization",
            target_id=str(actor.org_id),
            detail={},
        )
        await self.session.commit()
        return await self.get_installer(actor=actor)

    async def generate_offline_bundle(self, *, actor: User) -> tuple[str, bytes]:
        """Package a single offline installer zip (agent binary + pre-keyed script +
        Install.bat) for mass deployment, using the org's permanent enrollment key."""
        org = await self._ensure_enrollment_key(actor.org_id)
        settings = get_settings()
        server_url = settings.public_api_url.rstrip("/")
        content = build_offline_bundle_zip(
            server_url=server_url,
            enrollment_token=org.agent_enrollment_key,
            expires_label="never expires",
            # Normally empty: with a resolvable custom domain no hosts pin is needed.
            backend_ip=settings.agent_backend_ip.strip(),
        )
        return "AstraAgent-Portable.zip", content

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
        # Primary path: the permanent per-org enrollment key baked into the installer.
        org = await self.orgs.get_by_enrollment_key(data.enrollment_token)
        if org is not None:
            org_id = org.id
        else:
            # Backward-compat: a legacy (expiring) enrollment token.
            record = await self.enrollment_tokens.get_by_hash(
                hash_opaque_token(data.enrollment_token)
            )
            if (
                record is None
                or record.revoked_at is not None
                or as_utc(record.expires_at) <= utcnow()
            ):
                raise AuthenticationError("Invalid enrollment key")
            org_id = record.org_id

        raw_device_token = generate_opaque_token()
        device = await self.devices.get_by_machine_id(org_id, data.machine_id)

        if device is not None and not device.is_active:
            # Decommissioned hardware must not silently rejoin; an admin must
            # delete the device record first.
            raise AuthenticationError("Device is decommissioned")

        if device is None:
            # A new device consumes a license — hard-capped when the org is licensed.
            await self._enforce_license_capacity(org_id)
            device = await self.devices.add(
                Device(
                    org_id=org_id,
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
            org_id=org_id,
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
            if data.is_active:
                # Reactivating a decommissioned device consumes a license too.
                await self._enforce_license_capacity(actor.org_id)
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

    async def _enforce_license_capacity(self, org_id: uuid.UUID) -> None:
        """Block activating a device beyond the org's purchased licenses. Orgs with
        no licenses (license_count == 0 — trials / not subscribed) are uncapped."""
        org = await self.session.get(Organization, org_id)
        if org is None or org.license_count <= 0:
            return
        active = (
            await self.session.execute(
                select(func.count())
                .select_from(Device)
                .where(Device.org_id == org_id, Device.is_active.is_(True))
            )
        ).scalar_one()
        if active >= org.license_count:
            raise ValidationError(
                f"No available licenses ({active} of {org.license_count} in use). "
                "Ask your administrator to add licenses in ASTRA → Billing."
            )
