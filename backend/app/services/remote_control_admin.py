"""Turning remote control on or off for an organisation — the platform-operator action.

Enabling is not just a flag. The org needs two things on the relay before a session can
happen: a device group its machines enroll into, and a scoped account — not a site admin —
that the viewer cookie names and that can reach that group alone. This creates both the first
time it is enabled, stores their ids, then sets the entitlement.

Disabling is ONLY the entitlement. The agent uninstalls the relay agent from the whole fleet
on its own once `/agent/remote-support` starts answering false, so nothing more is needed —
and the relay's group and account are LEFT in place, so re-enabling is instant and no device
loses the group it was enrolled into. The two ids therefore outlive a disable on purpose.
"""
import re
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User
from app.services.audit import AuditService
from app.services.entitlements import REMOTE_CONTROL
from app.services.exceptions import NotFoundError, ServiceError
from app.services.meshcentral import (
    REMOTE_CONTROL_MESH_RIGHTS,
    MeshCentralClient,
    MeshCentralError,
)


class RemoteControlAdminError(ServiceError):
    pass


def _user_slug(org: Organization) -> str:
    """The relay account name for an org: astra-org-<full 32-hex of its id>. Stable, unique,
    and ascii — it becomes a MeshCentral account name.

    The WHOLE uuid, not a prefix: this name is the cross-tenant boundary. The viewer cookie
    names this account and MeshCentral confines it to the one device group it was granted, so
    two orgs must never resolve to the same account. A truncated slug made that a birthday
    problem — two orgs sharing a few leading hex digits would collide, and provision's
    "account already exists is fine" branch would then silently grant a SECOND org's device
    group to the FIRST org's account, letting one org's technician reach the other's screens.
    The full uuid makes a collision mean the same org, which is the only safe collision."""
    return f"astra-org-{org.id.hex}"


def _mesh_name(org: Organization) -> str:
    """The device group's display name on the relay. Kept readable but stripped to what
    MeshCentral's name validation accepts (1–128 chars, no control characters)."""
    clean = re.sub(r"[^\w .-]", "", org.name or "").strip()[:96]
    return f"ASTRA - {clean or ('Org ' + str(org.id)[:8])}"


class RemoteControlAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def set_enabled(
        self, *, actor: User, org_id: uuid.UUID, enabled: bool
    ) -> Organization:
        org = await self.session.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization not found")

        if enabled:
            await self._provision_if_needed(org)

        overrides = dict(org.entitlement_overrides or {})
        overrides[REMOTE_CONTROL] = enabled
        org.entitlement_overrides = overrides or None

        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="org.remote_control." + ("enable" if enabled else "disable"),
            target_type="organization",
            target_id=str(org.id),
            detail={
                "mesh_id": org.meshcentral_mesh_id,
                "user_id": org.meshcentral_user_id,
            },
        )
        await self.session.commit()
        return org

    async def _provision_if_needed(self, org: Organization) -> None:
        # Already stood up (group AND account both present) — re-enable is only the flag.
        if org.meshcentral_mesh_id and org.meshcentral_user_id:
            return
        # Exactly one present is a half-provisioned state this must not paper over by
        # creating a second group; it needs a human to reconcile, not a silent duplicate.
        if org.meshcentral_mesh_id or org.meshcentral_user_id:
            raise RemoteControlAdminError(
                "This organization is half-provisioned on the relay — one of the device group "
                "or the account is set and the other is not. Reconcile it before enabling."
            )

        client = MeshCentralClient()
        if not client.configured:
            raise RemoteControlAdminError(
                "No remote-control relay is configured on this deployment, so remote control "
                "cannot be enabled. Configure the MeshCentral connection first."
            )
        # A random password that meets any reasonable complexity rule. It is never used — the
        # browser logs into this account by a cookie ASTRA signs, never by password — so it
        # exists only so the account can be created to hold the group grant.
        password = "Aa1!" + secrets.token_urlsafe(24)
        try:
            mesh_id, user_id = await client.provision_scoped_access(
                mesh_name=_mesh_name(org),
                user_slug=_user_slug(org),
                password=password,
                rights=REMOTE_CONTROL_MESH_RIGHTS,
            )
        except MeshCentralError as exc:
            raise RemoteControlAdminError(
                f"Could not set the organization up on the relay: {exc}"
            ) from exc

        org.meshcentral_mesh_id = mesh_id
        org.meshcentral_user_id = user_id
