"""Workforce Insights ("Tracker") — attendance configuration.

The working-day calendar (which weekdays count, full/half-day thresholds) and the holiday list
that the attendance register scores against. Org-scoped and audited; writes are admin-only at
the router. Settings live on organizations.workforce_attendance; holidays are dated rows.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, WorkHoliday
from app.schemas.workforce import (
    DEFAULT_FULL_DAY_MINUTES,
    DEFAULT_HALF_DAY_MINUTES,
    AttendanceConfigRead,
    AttendanceSettingsWrite,
    HolidayRead,
    HolidayWrite,
)
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError

_DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]  # Mon–Fri


class AttendanceConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _holidays(self, org_id: uuid.UUID) -> list[WorkHoliday]:
        return list((await self.session.execute(
            select(WorkHoliday).where(WorkHoliday.org_id == org_id).order_by(WorkHoliday.day)
        )).scalars().all())

    async def get_config(self, *, org_id: uuid.UUID) -> AttendanceConfigRead:
        org = await self.session.get(Organization, org_id)
        settings = (org.workforce_attendance if org else None) or {}
        holidays = await self._holidays(org_id)
        return AttendanceConfigRead(
            working_days=settings.get("working_days") or list(_DEFAULT_WORKING_DAYS),
            full_day_minutes=settings.get("full_day_minutes", DEFAULT_FULL_DAY_MINUTES),
            half_day_minutes=settings.get("half_day_minutes", DEFAULT_HALF_DAY_MINUTES),
            holidays=[HolidayRead.model_validate(h) for h in holidays],
        )

    async def set_settings(
        self, *, actor: User, body: AttendanceSettingsWrite
    ) -> AttendanceConfigRead:
        org = await self.session.get(Organization, actor.org_id)
        if org is None:
            raise NotFoundError("Organization not found.")
        org.workforce_attendance = {
            "working_days": body.working_days,
            "full_day_minutes": body.full_day_minutes,
            "half_day_minutes": body.half_day_minutes,
        }
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="attendance.settings.update",
            target_type="organization", target_id=str(actor.org_id),
            detail=org.workforce_attendance,
        )
        await self.session.commit()
        return await self.get_config(org_id=actor.org_id)

    async def add_holiday(self, *, actor: User, body: HolidayWrite) -> HolidayRead:
        existing = (await self.session.execute(
            select(WorkHoliday).where(
                WorkHoliday.org_id == actor.org_id, WorkHoliday.day == body.day
            )
        )).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("A holiday is already set for that date.")
        holiday = WorkHoliday(org_id=actor.org_id, day=body.day, name=body.name.strip())
        self.session.add(holiday)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="attendance.holiday.add",
            target_type="work_holiday", target_id=str(holiday.id),
            detail={"day": str(body.day), "name": holiday.name},
        )
        await self.session.commit()
        return HolidayRead.model_validate(holiday)

    async def delete_holiday(self, *, actor: User, holiday_id: uuid.UUID) -> None:
        holiday = await self.session.get(WorkHoliday, holiday_id)
        if holiday is None or holiday.org_id != actor.org_id:
            raise NotFoundError("Holiday not found.")
        day, name = str(holiday.day), holiday.name
        await self.session.delete(holiday)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="attendance.holiday.delete",
            target_type="work_holiday", target_id=str(holiday_id),
            detail={"day": day, "name": name},
        )
        await self.session.commit()
