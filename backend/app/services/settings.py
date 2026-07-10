import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrganizationSettings, User
from app.repositories.organization_settings import OrganizationSettingsRepository
from app.repositories.organizations import OrganizationRepository
from app.schemas.settings import (
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    PermissionMatrix,
    RolePermissions,
)
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError

# The capability matrix rendered in Settings → Permissions. Keys map to the RBAC
# actually enforced across the API; labels are the column headers in the UI.
_CAPABILITIES: list[tuple[str, str]] = [
    ("view_platform", "View dashboards, assets & reports"),
    ("use_assistant", "Use the AI assistant"),
    ("view_telemetry", "View device telemetry & audit logs"),
    ("manage_assets", "Manage assets"),
    ("manage_knowledge", "Manage the knowledge base"),
    ("run_remediation", "Request self-healing actions"),
    ("approve_standard", "Approve standard remediations"),
    ("approve_admin", "Approve high-risk (admin-only) remediations"),
    ("manage_devices", "Enroll & manage devices"),
    ("manage_users", "Manage users & roles"),
    ("manage_settings", "Manage organization settings"),
]

_ROLE_META: dict[str, tuple[str, str]] = {
    "admin": ("Administrator", "Full control over the organization, users and settings."),
    "technician": ("Technician", "Operates the fleet: telemetry, assets, knowledge and self-healing."),
    "user": ("User", "Read-only access to dashboards and the AI assistant."),
}


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = OrganizationSettingsRepository(session)
        self.orgs = OrganizationRepository(session)
        self.audit = AuditService(session)

    async def ensure(self, org_id: uuid.UUID) -> OrganizationSettings:
        """Return the org's settings, creating a default row on first access.
        Flushes but does not commit — the caller's transaction commits."""
        settings = await self.repo.get_by_org(org_id)
        if settings is None:
            settings = await self.repo.add(OrganizationSettings(org_id=org_id))
        return settings

    async def read(self, *, actor: User) -> OrganizationSettingsRead:
        settings = await self.ensure(actor.org_id)
        org = await self.orgs.get(actor.org_id)
        await self.session.commit()
        return self._to_read(settings, org.name)

    async def update(
        self, *, actor: User, data: OrganizationSettingsUpdate
    ) -> OrganizationSettingsRead:
        settings = await self.ensure(actor.org_id)
        org = await self.orgs.get(actor.org_id)
        changes: dict[str, object] = {}

        if data.org_name is not None and data.org_name != org.name:
            existing = await self.orgs.get_by_name(data.org_name)
            if existing is not None and existing.id != org.id:
                raise ConflictError("An organization with that name already exists")
            org.name = data.org_name
            changes["org_name"] = data.org_name

        for field in (
            "auto_approve_automatic",
            "require_admin_for_approval_tier",
            "min_password_length",
            "enrollment_token_default_days",
        ):
            value = getattr(data, field)
            if value is not None and value != getattr(settings, field):
                setattr(settings, field, value)
                changes[field] = value

        if changes:
            await self.audit.record(
                org_id=actor.org_id,
                actor_id=actor.id,
                action="settings.update",
                target_type="organization",
                target_id=str(actor.org_id),
                detail=changes,
            )
        await self.session.commit()
        return self._to_read(settings, org.name)

    async def permission_matrix(self, *, org_id: uuid.UUID) -> PermissionMatrix:
        settings = await self.ensure(org_id)
        await self.session.commit()

        # Technician may approve standard (approval_required) remediations unless the
        # org has tightened policy to admin-only for that tier.
        tech_approve_standard = not settings.require_admin_for_approval_tier

        grants: dict[str, dict[str, bool]] = {
            "admin": {key: True for key, _ in _CAPABILITIES},
            "technician": {
                "view_platform": True,
                "use_assistant": True,
                "view_telemetry": True,
                "manage_assets": True,
                "manage_knowledge": True,
                "run_remediation": True,
                "approve_standard": tech_approve_standard,
                "approve_admin": False,
                "manage_devices": False,
                "manage_users": False,
                "manage_settings": False,
            },
            "user": {
                "view_platform": True,
                "use_assistant": True,
                "view_telemetry": False,
                "manage_assets": False,
                "manage_knowledge": False,
                "run_remediation": False,
                "approve_standard": False,
                "approve_admin": False,
                "manage_devices": False,
                "manage_users": False,
                "manage_settings": False,
            },
        }

        roles = [
            RolePermissions(
                role=role,
                label=_ROLE_META[role][0],
                description=_ROLE_META[role][1],
                capabilities=grants[role],
            )
            for role in ("admin", "technician", "user")
        ]
        return PermissionMatrix(
            capabilities=[{"key": k, "label": v} for k, v in _CAPABILITIES],
            roles=roles,
        )

    @staticmethod
    def _to_read(settings: OrganizationSettings, org_name: str) -> OrganizationSettingsRead:
        return OrganizationSettingsRead(
            org_name=org_name,
            auto_approve_automatic=settings.auto_approve_automatic,
            require_admin_for_approval_tier=settings.require_admin_for_approval_tier,
            min_password_length=settings.min_password_length,
            enrollment_token_default_days=settings.enrollment_token_default_days,
            updated_at=settings.updated_at,
        )
