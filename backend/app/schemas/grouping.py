import uuid

from pydantic import BaseModel, Field

# A 3/6/8-digit hex colour. Validated at the edge rather than trusted, because this value is
# written straight into a style attribute in the portal — a string that is not a colour is
# the beginning of a CSS injection, and there is no reason to accept one.
COLOUR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"


class GroupWrite(BaseModel):
    """Create/update body, shared by device groups and user teams — the two carry the same
    three fields, and giving them separate identical models only creates a chance for the
    two to drift apart later."""
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    colour: str | None = Field(default=None, pattern=COLOUR_PATTERN)


class DeviceGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    colour: str | None
    # Counted server-side. The alternative is shipping every member id so the client can
    # take its length, which turns a list of 12 groups into a list of 2,000 device ids.
    device_count: int


class UserTeamRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    colour: str | None
    member_count: int


class MembershipWrite(BaseModel):
    """Set a group's membership.

    The whole set, not a delta. Add/remove deltas race: two operators editing the same group
    in two tabs each send "add X", and neither can tell that the other removed Y. Sending
    the set the operator was looking at makes the last write win visibly, which is the
    behaviour they already expect from a list of checkboxes.
    """
    device_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)


class TeamMembershipWrite(BaseModel):
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
