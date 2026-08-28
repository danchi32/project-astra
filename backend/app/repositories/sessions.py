import uuid
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceGroup, DeviceGroupMember, DeviceSession


class SessionRepository:
    """Reads of the fleet's logon sessions.

    Every query here joins Device and filters on `Device.org_id` rather than
    `DeviceSession.org_id`, even though the session row carries its own copy. The copy is
    there so ingest can write a row without a second lookup; the join is there because the
    device is what the caller is really asking about, and a tenancy check that reads the
    denormalized copy would keep trusting it after a device moved between orgs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base(self, org_id: uuid.UUID) -> Select:
        return (
            select(DeviceSession, Device)
            .join(Device, Device.id == DeviceSession.device_id)
            .where(Device.org_id == org_id, Device.is_active.is_(True))
        )

    @staticmethod
    def _apply(
        stmt: Select,
        *,
        q: str | None,
        state: str | None,
        connection: str | None,
        group_id: uuid.UUID | None,
        online_cutoff: datetime | None,
        online: bool | None,
    ) -> Select:
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Device.hostname).like(like),
                    func.lower(DeviceSession.username).like(like),
                    func.lower(DeviceSession.client_name).like(like),
                )
            )
        if state:
            stmt = stmt.where(DeviceSession.state == state)
        if connection:
            stmt = stmt.where(DeviceSession.connection == connection)
        if group_id is not None:
            # EXISTS rather than a join: a device in three groups would otherwise multiply
            # its session rows by three, and the page would show the same person three times.
            stmt = stmt.where(
                select(DeviceGroupMember.id)
                .where(
                    DeviceGroupMember.device_id == Device.id,
                    DeviceGroupMember.group_id == group_id,
                )
                .exists()
            )
        if online is not None and online_cutoff is not None:
            fresh = and_(
                Device.last_seen_at.is_not(None), Device.last_seen_at >= online_cutoff
            )
            stmt = stmt.where(fresh if online else ~fresh)
        return stmt

    async def page(
        self,
        org_id: uuid.UUID,
        *,
        q: str | None = None,
        state: str | None = None,
        connection: str | None = None,
        group_id: uuid.UUID | None = None,
        online: bool | None = None,
        online_cutoff: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[DeviceSession, Device]], int]:
        stmt = self._apply(
            self._base(org_id), q=q, state=state, connection=connection,
            group_id=group_id, online_cutoff=online_cutoff, online=online,
        )
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = await self.session.execute(
            # Active first, then the machine that reported most recently. A technician
            # opening this page is looking for someone who is on a machine NOW; ordering by
            # hostname would bury every active session behind the alphabet.
            stmt.order_by(
                DeviceSession.state.asc(),          # 'active' < 'disconnected' lexically
                Device.last_seen_at.desc().nullslast(),
                Device.hostname.asc(),
                DeviceSession.session_id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return [(r[0], r[1]) for r in rows.all()], int(total or 0)

    async def counts(
        self,
        org_id: uuid.UUID,
        *,
        q: str | None = None,
        group_id: uuid.UUID | None = None,
        online: bool | None = None,
        online_cutoff: datetime | None = None,
    ) -> dict[str, int]:
        """Counts for the tab strip, over the search + group filter but NOT over the tab
        filters themselves — the point of the strip is to say how many are in each tab
        while you are standing in one of them.

        One grouped query rather than five counts: five round trips to render five numbers
        that must agree with each other is how they end up not agreeing.
        """
        stmt = self._apply(
            select(DeviceSession.state, DeviceSession.connection, func.count())
            .select_from(DeviceSession)
            .join(Device, Device.id == DeviceSession.device_id)
            .where(Device.org_id == org_id, Device.is_active.is_(True)),
            q=q, state=None, connection=None, group_id=group_id,
            online_cutoff=online_cutoff, online=online,
        ).group_by(DeviceSession.state, DeviceSession.connection)

        tally = {"all": 0, "active": 0, "disconnected": 0, "console": 0, "rdp": 0}
        for state, connection, count in (await self.session.execute(stmt)).all():
            n = int(count)
            tally["all"] += n
            if state in tally:
                tally[state] += n
            if connection in tally:
                tally[connection] += n
        return tally

    async def group_names_for(
        self, device_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        """Group names for just the devices on the page being rendered."""
        if not device_ids:
            return {}
        rows = await self.session.execute(
            select(DeviceGroupMember.device_id, DeviceGroup.name)
            .join(DeviceGroup, DeviceGroup.id == DeviceGroupMember.group_id)
            .where(DeviceGroupMember.device_id.in_(device_ids))
            .order_by(DeviceGroup.name)
        )
        out: dict[uuid.UUID, list[str]] = {}
        for device_id, name in rows.all():
            out.setdefault(device_id, []).append(name)
        return out

    async def for_device(self, device_id: uuid.UUID) -> list[DeviceSession]:
        rows = await self.session.execute(
            select(DeviceSession)
            .where(DeviceSession.device_id == device_id)
            .order_by(DeviceSession.state.asc(), DeviceSession.session_id.asc())
        )
        return list(rows.scalars().all())
