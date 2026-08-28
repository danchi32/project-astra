"""Device groups and user teams.

Two near-identical CRUD surfaces over two pairs of tables. They are written out rather than
generated from a shared base, because the one place they differ is the place it matters: a
device group's membership is checked against the org's DEVICES and a team's against its
USERS, and a clever base class that took the model as a parameter would make that check the
easiest thing in the file to get wrong.

Membership writes are set-replacements, and every one of them re-checks that each id
belongs to the caller's organization. A group is a filter that later drives bulk
remediation, so an id smuggled into a membership list would be an id that later receives
commands.
"""
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    DeviceGroup,
    DeviceGroupMember,
    User,
    UserTeam,
    UserTeamMember,
)
from app.schemas.grouping import DeviceGroupRead, GroupWrite, UserTeamRead
from app.services.audit import AuditService
from app.services.exceptions import ConflictError, NotFoundError


class GroupingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Device groups ──────────────────────────────────────────────────────

    async def list_groups(self, *, org_id: uuid.UUID) -> list[DeviceGroupRead]:
        counts = dict(
            (await self.session.execute(
                select(DeviceGroupMember.group_id, func.count())
                .join(DeviceGroup, DeviceGroup.id == DeviceGroupMember.group_id)
                .where(DeviceGroup.org_id == org_id)
                .group_by(DeviceGroupMember.group_id)
            )).all()
        )
        groups = (await self.session.execute(
            select(DeviceGroup).where(DeviceGroup.org_id == org_id).order_by(DeviceGroup.name)
        )).scalars().all()
        return [
            DeviceGroupRead(
                id=g.id, name=g.name, description=g.description, colour=g.colour,
                device_count=int(counts.get(g.id, 0)),
            )
            for g in groups
        ]

    async def create_group(self, *, actor: User, body: GroupWrite) -> DeviceGroupRead:
        name = body.name.strip()
        if not name:
            raise ValueError("A group name is required.")
        if await self._group_name_taken(actor.org_id, name):
            raise ConflictError("A device group with that name already exists.")
        group = DeviceGroup(
            org_id=actor.org_id, name=name,
            description=(body.description or None), colour=body.colour,
        )
        self.session.add(group)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="device_group.create",
            target_type="device_group", target_id=str(group.id), detail={"name": name},
        )
        await self.session.commit()
        return DeviceGroupRead(
            id=group.id, name=group.name, description=group.description,
            colour=group.colour, device_count=0,
        )

    async def update_group(
        self, *, actor: User, group_id: uuid.UUID, body: GroupWrite
    ) -> DeviceGroupRead:
        group = await self._owned_group(actor.org_id, group_id)
        name = body.name.strip()
        if not name:
            raise ValueError("A group name is required.")
        if name.lower() != group.name.lower() and await self._group_name_taken(
            actor.org_id, name
        ):
            raise ConflictError("A device group with that name already exists.")
        before = group.name
        group.name = name
        group.description = body.description or None
        group.colour = body.colour
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="device_group.update",
            target_type="device_group", target_id=str(group.id),
            detail={"from": before, "to": name},
        )
        await self.session.commit()
        count = await self._group_member_count(group.id)
        return DeviceGroupRead(
            id=group.id, name=group.name, description=group.description,
            colour=group.colour, device_count=count,
        )

    async def delete_group(self, *, actor: User, group_id: uuid.UUID) -> None:
        """Deleting a group deletes its memberships and nothing else.

        Worth stating because the opposite is a plausible reading of "delete the Finance
        laptops group", and it is the reading that would end a fleet. Devices are not owned
        by groups; a group is a label on them.
        """
        group = await self._owned_group(actor.org_id, group_id)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="device_group.delete",
            target_type="device_group", target_id=str(group.id),
            detail={"name": group.name},
        )
        await self.session.delete(group)
        await self.session.commit()

    async def group_member_ids(
        self, *, org_id: uuid.UUID, group_id: uuid.UUID
    ) -> list[uuid.UUID]:
        await self._owned_group(org_id, group_id)
        return list((await self.session.execute(
            select(DeviceGroupMember.device_id).where(
                DeviceGroupMember.group_id == group_id
            )
        )).scalars().all())

    async def set_group_members(
        self, *, actor: User, group_id: uuid.UUID, device_ids: list[uuid.UUID]
    ) -> int:
        group = await self._owned_group(actor.org_id, group_id)
        wanted = set(device_ids)
        if wanted:
            # Only devices this organization owns. Silently dropping the rest would let a
            # caller learn which ids exist elsewhere by watching the returned count, so an
            # id that isn't theirs is an error, not a no-op.
            owned = set((await self.session.execute(
                select(Device.id).where(
                    Device.org_id == actor.org_id, Device.id.in_(wanted)
                )
            )).scalars().all())
            if owned != wanted:
                raise NotFoundError("One or more of those devices does not exist.")

        await self.session.execute(
            delete(DeviceGroupMember).where(DeviceGroupMember.group_id == group_id)
        )
        self.session.add_all(
            [DeviceGroupMember(group_id=group_id, device_id=d) for d in wanted]
        )
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="device_group.set_members",
            target_type="device_group", target_id=str(group.id),
            detail={"name": group.name, "device_count": len(wanted)},
        )
        await self.session.commit()
        return len(wanted)

    async def groups_for_devices(
        self, device_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        if not device_ids:
            return {}
        rows = (await self.session.execute(
            select(DeviceGroupMember.device_id, DeviceGroup.name)
            .join(DeviceGroup, DeviceGroup.id == DeviceGroupMember.group_id)
            .where(DeviceGroupMember.device_id.in_(device_ids))
            .order_by(DeviceGroup.name)
        )).all()
        out: dict[uuid.UUID, list[str]] = {}
        for device_id, name in rows:
            out.setdefault(device_id, []).append(name)
        return out

    # ── User teams ─────────────────────────────────────────────────────────

    async def list_teams(self, *, org_id: uuid.UUID) -> list[UserTeamRead]:
        counts = dict(
            (await self.session.execute(
                select(UserTeamMember.team_id, func.count())
                .join(UserTeam, UserTeam.id == UserTeamMember.team_id)
                .where(UserTeam.org_id == org_id)
                .group_by(UserTeamMember.team_id)
            )).all()
        )
        teams = (await self.session.execute(
            select(UserTeam).where(UserTeam.org_id == org_id).order_by(UserTeam.name)
        )).scalars().all()
        return [
            UserTeamRead(
                id=t.id, name=t.name, description=t.description, colour=t.colour,
                member_count=int(counts.get(t.id, 0)),
            )
            for t in teams
        ]

    async def create_team(self, *, actor: User, body: GroupWrite) -> UserTeamRead:
        name = body.name.strip()
        if not name:
            raise ValueError("A team name is required.")
        if await self._team_name_taken(actor.org_id, name):
            raise ConflictError("A team with that name already exists.")
        team = UserTeam(
            org_id=actor.org_id, name=name,
            description=(body.description or None), colour=body.colour,
        )
        self.session.add(team)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="user_team.create",
            target_type="user_team", target_id=str(team.id), detail={"name": name},
        )
        await self.session.commit()
        return UserTeamRead(
            id=team.id, name=team.name, description=team.description,
            colour=team.colour, member_count=0,
        )

    async def update_team(
        self, *, actor: User, team_id: uuid.UUID, body: GroupWrite
    ) -> UserTeamRead:
        team = await self._owned_team(actor.org_id, team_id)
        name = body.name.strip()
        if not name:
            raise ValueError("A team name is required.")
        if name.lower() != team.name.lower() and await self._team_name_taken(
            actor.org_id, name
        ):
            raise ConflictError("A team with that name already exists.")
        before = team.name
        team.name = name
        team.description = body.description or None
        team.colour = body.colour
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="user_team.update",
            target_type="user_team", target_id=str(team.id),
            detail={"from": before, "to": name},
        )
        await self.session.commit()
        count = int((await self.session.execute(
            select(func.count()).select_from(UserTeamMember)
            .where(UserTeamMember.team_id == team.id)
        )).scalar_one())
        return UserTeamRead(
            id=team.id, name=team.name, description=team.description,
            colour=team.colour, member_count=count,
        )

    async def delete_team(self, *, actor: User, team_id: uuid.UUID) -> None:
        team = await self._owned_team(actor.org_id, team_id)
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="user_team.delete",
            target_type="user_team", target_id=str(team.id), detail={"name": team.name},
        )
        await self.session.delete(team)
        await self.session.commit()

    async def team_member_ids(
        self, *, org_id: uuid.UUID, team_id: uuid.UUID
    ) -> list[uuid.UUID]:
        await self._owned_team(org_id, team_id)
        return list((await self.session.execute(
            select(UserTeamMember.user_id).where(UserTeamMember.team_id == team_id)
        )).scalars().all())

    async def set_team_members(
        self, *, actor: User, team_id: uuid.UUID, user_ids: list[uuid.UUID]
    ) -> int:
        """Membership is not permission.

        Nothing downstream reads this table to decide whether someone may do something —
        RBAC does that, from `users.role`. A team is who works together, and keeping the two
        apart is what stops "add them to the on-call team" from quietly becoming a way to
        hand out admin.
        """
        team = await self._owned_team(actor.org_id, team_id)
        wanted = set(user_ids)
        if wanted:
            owned = set((await self.session.execute(
                select(User.id).where(User.org_id == actor.org_id, User.id.in_(wanted))
            )).scalars().all())
            if owned != wanted:
                raise NotFoundError("One or more of those users does not exist.")

        await self.session.execute(
            delete(UserTeamMember).where(UserTeamMember.team_id == team_id)
        )
        self.session.add_all([UserTeamMember(team_id=team_id, user_id=u) for u in wanted])
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="user_team.set_members",
            target_type="user_team", target_id=str(team.id),
            detail={"name": team.name, "member_count": len(wanted)},
        )
        await self.session.commit()
        return len(wanted)

    # ── Lookups ────────────────────────────────────────────────────────────

    async def _owned_group(self, org_id: uuid.UUID, group_id: uuid.UUID) -> DeviceGroup:
        group = (await self.session.execute(
            select(DeviceGroup).where(
                DeviceGroup.id == group_id, DeviceGroup.org_id == org_id
            )
        )).scalar_one_or_none()
        if group is None:
            raise NotFoundError("Device group not found.")
        return group

    async def _owned_team(self, org_id: uuid.UUID, team_id: uuid.UUID) -> UserTeam:
        team = (await self.session.execute(
            select(UserTeam).where(UserTeam.id == team_id, UserTeam.org_id == org_id)
        )).scalar_one_or_none()
        if team is None:
            raise NotFoundError("Team not found.")
        return team

    async def _group_name_taken(self, org_id: uuid.UUID, name: str) -> bool:
        return (await self.session.execute(
            select(DeviceGroup.id).where(
                DeviceGroup.org_id == org_id, func.lower(DeviceGroup.name) == name.lower()
            )
        )).first() is not None

    async def _team_name_taken(self, org_id: uuid.UUID, name: str) -> bool:
        return (await self.session.execute(
            select(UserTeam.id).where(
                UserTeam.org_id == org_id, func.lower(UserTeam.name) == name.lower()
            )
        )).first() is not None

    async def _group_member_count(self, group_id: uuid.UUID) -> int:
        return int((await self.session.execute(
            select(func.count()).select_from(DeviceGroupMember)
            .where(DeviceGroupMember.group_id == group_id)
        )).scalar_one())
