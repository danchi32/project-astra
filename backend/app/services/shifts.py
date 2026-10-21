"""Workforce Insights ("Tracker") — department shifts.

Defining named shifts (APAC / UK / US / India General …) and assigning them to teams. A shift
says when a department is expected to be working, in its own timezone; the assignment lives on
the team (user_teams.shift_id) because the team is "who is on shift".

Org-scoped and audited, same discipline as GroupingService. This service owns the shift
definitions and the team→shift assignment; measuring attendance against a shift (late-in,
early-out, overtime) is a separate layer added on top of the existing attendance roll-up.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserTeam, UserTeamMember, WorkShift
from app.schemas.workforce import (
    ShiftAssignmentWrite,
    TeamShiftRead,
    WorkShiftRead,
    WorkShiftWrite,
)
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError


class ShiftService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Reads ────────────────────────────────────────────────────────────────

    async def _team_counts(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """How many teams are assigned each shift, for the org."""
        rows = (await self.session.execute(
            select(UserTeam.shift_id, func.count())
            .where(UserTeam.org_id == org_id, UserTeam.shift_id.isnot(None))
            .group_by(UserTeam.shift_id)
        )).all()
        return {r[0]: int(r[1]) for r in rows}

    async def list_shifts(self, *, org_id: uuid.UUID) -> list[WorkShiftRead]:
        counts = await self._team_counts(org_id)
        shifts = (await self.session.execute(
            select(WorkShift).where(WorkShift.org_id == org_id).order_by(WorkShift.name)
        )).scalars().all()
        return [
            WorkShiftRead(
                id=s.id, name=s.name, timezone=s.timezone,
                start_minute=s.start_minute, end_minute=s.end_minute,
                working_days=list(s.working_days or []), colour=s.colour,
                team_count=counts.get(s.id, 0),
            )
            for s in shifts
        ]

    async def list_team_assignments(self, *, org_id: uuid.UUID) -> list[TeamShiftRead]:
        member_counts = dict((await self.session.execute(
            select(UserTeamMember.team_id, func.count())
            .join(UserTeam, UserTeam.id == UserTeamMember.team_id)
            .where(UserTeam.org_id == org_id)
            .group_by(UserTeamMember.team_id)
        )).all())
        rows = (await self.session.execute(
            select(UserTeam, WorkShift.name)
            .outerjoin(WorkShift, WorkShift.id == UserTeam.shift_id)
            .where(UserTeam.org_id == org_id)
            .order_by(UserTeam.name)
        )).all()
        return [
            TeamShiftRead(
                team_id=team.id, team_name=team.name,
                member_count=int(member_counts.get(team.id, 0)),
                shift_id=team.shift_id, shift_name=shift_name,
            )
            for team, shift_name in rows
        ]

    # ── Writes ───────────────────────────────────────────────────────────────

    async def _owned_shift(self, org_id: uuid.UUID, shift_id: uuid.UUID) -> WorkShift:
        shift = await self.session.get(WorkShift, shift_id)
        if shift is None or shift.org_id != org_id:
            raise NotFoundError("Shift not found.")
        return shift

    async def _name_taken(self, org_id: uuid.UUID, name: str, *, exclude: uuid.UUID | None = None) -> bool:
        stmt = select(WorkShift.id).where(
            WorkShift.org_id == org_id, func.lower(WorkShift.name) == name.lower()
        )
        if exclude is not None:
            stmt = stmt.where(WorkShift.id != exclude)
        return (await self.session.execute(stmt)).first() is not None

    async def create_shift(self, *, actor: User, body: WorkShiftWrite) -> WorkShiftRead:
        name = body.name.strip()
        if await self._name_taken(actor.org_id, name):
            raise ConflictError("A shift with that name already exists.")
        shift = WorkShift(
            org_id=actor.org_id, name=name, timezone=body.timezone,
            start_minute=body.start_minute, end_minute=body.end_minute,
            working_days=body.working_days, colour=body.colour,
        )
        self.session.add(shift)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="work_shift.create",
            target_type="work_shift", target_id=str(shift.id),
            detail={"name": name, "timezone": body.timezone,
                    "start_minute": body.start_minute, "end_minute": body.end_minute},
        )
        await self.session.commit()
        return WorkShiftRead(
            id=shift.id, name=shift.name, timezone=shift.timezone,
            start_minute=shift.start_minute, end_minute=shift.end_minute,
            working_days=list(shift.working_days or []), colour=shift.colour, team_count=0,
        )

    async def update_shift(
        self, *, actor: User, shift_id: uuid.UUID, body: WorkShiftWrite
    ) -> WorkShiftRead:
        shift = await self._owned_shift(actor.org_id, shift_id)
        name = body.name.strip()
        if name.lower() != shift.name.lower() and await self._name_taken(
            actor.org_id, name, exclude=shift.id
        ):
            raise ConflictError("A shift with that name already exists.")
        shift.name = name
        shift.timezone = body.timezone
        shift.start_minute = body.start_minute
        shift.end_minute = body.end_minute
        shift.working_days = body.working_days
        shift.colour = body.colour
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="work_shift.update",
            target_type="work_shift", target_id=str(shift.id), detail={"name": name},
        )
        await self.session.commit()
        counts = await self._team_counts(actor.org_id)
        return WorkShiftRead(
            id=shift.id, name=shift.name, timezone=shift.timezone,
            start_minute=shift.start_minute, end_minute=shift.end_minute,
            working_days=list(shift.working_days or []), colour=shift.colour,
            team_count=counts.get(shift.id, 0),
        )

    async def delete_shift(self, *, actor: User, shift_id: uuid.UUID) -> None:
        shift = await self._owned_shift(actor.org_id, shift_id)
        name = shift.name
        # Teams keep existing; their shift_id is SET NULL by the FK, so deleting a shift
        # un-assigns it rather than cascading into the teams.
        await self.session.delete(shift)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="work_shift.delete",
            target_type="work_shift", target_id=str(shift_id), detail={"name": name},
        )
        await self.session.commit()

    async def assign_shift(
        self, *, actor: User, team_id: uuid.UUID, body: ShiftAssignmentWrite
    ) -> TeamShiftRead:
        team = await self.session.get(UserTeam, team_id)
        if team is None or team.org_id != actor.org_id:
            raise NotFoundError("Team not found.")
        shift_name: str | None = None
        if body.shift_id is not None:
            shift = await self._owned_shift(actor.org_id, body.shift_id)
            shift_name = shift.name
        team.shift_id = body.shift_id
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="work_shift.assign",
            target_type="user_team", target_id=str(team_id),
            detail={"team": team.name, "shift_id": str(body.shift_id) if body.shift_id else None,
                    "shift": shift_name},
        )
        await self.session.commit()
        member_count = int((await self.session.execute(
            select(func.count()).select_from(UserTeamMember)
            .where(UserTeamMember.team_id == team_id)
        )).scalar_one())
        return TeamShiftRead(
            team_id=team.id, team_name=team.name, member_count=member_count,
            shift_id=team.shift_id, shift_name=shift_name,
        )
