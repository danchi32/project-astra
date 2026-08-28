import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin

# Two things that look alike and are not interchangeable, kept in one module so the
# difference is stated once:
#
#   * A DEVICE GROUP answers "which machines". It is what an operator filters the fleet by,
#     what a bulk remediation is aimed at, and what a report is broken down by.
#   * A USER TEAM answers "which people". It is who is on shift, who owns an escalation,
#     who a report is addressed to.
#
# Locations already exist and are not a substitute for either: a location is where a thing
# physically is, one value per asset, and it cannot express "the finance laptops" (which
# span three floors) or "everything on the 2019 hardware refresh" (which spans two sites).
# Groups overlap by design; a location cannot.


class DeviceGroup(TimestampMixin, Base):
    """A named, overlapping set of devices within one organization."""

    __tablename__ = "device_groups"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_device_groups_org_name"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # A hex colour chosen when the group is created, so groups are distinguishable at a
    # glance in a table of chips. Stored rather than derived from the name, because a
    # derived colour changes when the group is renamed and operators navigate by colour.
    colour: Mapped[str | None] = mapped_column(String(9), nullable=True)


class DeviceGroupMember(TimestampMixin, Base):
    """A device's membership of a group. Static membership: someone put this device here.

    Rule-based membership ("every device whose hostname starts with FIN-") is a later
    addition and belongs beside this table, not instead of it — a rule that stops matching
    should not silently empty a group an operator is relying on.
    """

    __tablename__ = "device_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "device_id", name="uq_device_group_members"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("device_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )


class UserTeam(TimestampMixin, Base):
    """A named set of portal users — the IT side, not the fleet side."""

    __tablename__ = "user_teams"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_user_teams_org_name"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    colour: Mapped[str | None] = mapped_column(String(9), nullable=True)


class UserTeamMember(TimestampMixin, Base):
    """A user's membership of a team.

    Membership is NOT permission. A team says who works together; RBAC still decides what
    each of them may do, and nothing in this table is ever consulted to authorise an action.
    Keeping those separate is what stops "add them to the team" quietly becoming a way to
    grant admin.
    """

    __tablename__ = "user_team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_user_team_members"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("user_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
