"""Platform-operator (super-admin) operations that span ALL organizations.

This is the one service that intentionally crosses org boundaries, so every
mutation is audited under the target org.
"""
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Organization, User
from app.models.base import as_utc, utcnow
from app.repositories.organizations import OrganizationRepository
from app.schemas.platform import OrganizationAdminRead, OrganizationUpdate
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError


class PlatformService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.audit = AuditService(session)

    async def list_organizations(self) -> list[OrganizationAdminRead]:
        orgs = (await self.session.execute(select(Organization).order_by(Organization.created_at))).scalars().all()
        user_counts = dict(
            (await self.session.execute(select(User.org_id, func.count()).group_by(User.org_id))).all()
        )
        device_counts = dict(
            (await self.session.execute(select(Device.org_id, func.count()).group_by(Device.org_id))).all()
        )
        result: list[OrganizationAdminRead] = []
        for org in orgs:
            read = OrganizationAdminRead.model_validate(org)
            read.user_count = user_counts.get(org.id, 0)
            read.device_count = device_counts.get(org.id, 0)
            result.append(read)
        return result

    async def get_organization(self, org_id: uuid.UUID) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def update_organization(
        self, *, actor: User, org_id: uuid.UUID, data: OrganizationUpdate
    ) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")

        changes: dict[str, str] = {}
        if data.plan is not None:
            org.plan = data.plan
            changes["plan"] = data.plan
        if data.subscription_status is not None:
            org.subscription_status = data.subscription_status
            changes["status"] = data.subscription_status.value
        if data.trial_ends_at is not None:
            org.trial_ends_at = data.trial_ends_at
            changes["trial_ends_at"] = data.trial_ends_at.isoformat()
        if data.current_period_end is not None:
            org.current_period_end = data.current_period_end
            changes["current_period_end"] = data.current_period_end.isoformat()
        if data.extend_trial_days is not None:
            base = max(as_utc(org.trial_ends_at), utcnow()) if org.trial_ends_at else utcnow()
            org.trial_ends_at = base + timedelta(days=data.extend_trial_days)
            changes["extended_trial_days"] = str(data.extend_trial_days)

        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.update",
            target_type="organization",
            target_id=str(org.id),
            detail=changes,
        )
        await self.session.commit()

        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def set_discount(
        self, *, actor: User, org_id: uuid.UUID, percent: int
    ) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        from app.services.billing import BillingService  # local import avoids a cycle
        await BillingService(self.session).apply_discount(org, percent)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="platform.organization.discount",
            target_type="organization", target_id=str(org.id), detail={"percent": percent},
        )
        await self.session.commit()
        return await self._read(org)

    async def clear_discount(self, *, actor: User, org_id: uuid.UUID) -> OrganizationAdminRead:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        from app.services.billing import BillingService
        await BillingService(self.session).remove_discount(org)
        await self.audit.record(
            org_id=org.id, actor_id=actor.id, action="platform.organization.discount_removed",
            target_type="organization", target_id=str(org.id), detail={},
        )
        await self.session.commit()
        return await self._read(org)

    async def _read(self, org: Organization) -> OrganizationAdminRead:
        read = OrganizationAdminRead.model_validate(org)
        read.user_count = await self._count(User, org.id)
        read.device_count = await self._count(Device, org.id)
        return read

    async def delete_organization(self, *, actor: User, org_id: uuid.UUID) -> None:
        org = await self.orgs.get(org_id)
        if org is None:
            raise NotFoundError("Organization not found")
        name = org.name
        await self.audit.record(
            org_id=org.id,
            actor_id=actor.id,
            action="platform.organization.delete",
            target_type="organization",
            target_id=str(org.id),
            detail={"name": name},
        )
        await self.session.delete(org)
        await self.session.commit()

    async def _count(self, model, org_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                select(func.count()).select_from(model).where(model.org_id == org_id)
            )
        ).scalar_one()
