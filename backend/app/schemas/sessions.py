import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SessionState = Literal["active", "disconnected"]
SessionConnection = Literal["console", "rdp"]


class DeviceSessionRead(BaseModel):
    """One row of the Sessions view: a logon session, plus enough of its device to act on it.

    The device fields are denormalized into the row rather than nested, because every one of
    them is a column the operator reads across (hostname, is it online, when did it last
    check in) and a nested object would put them behind an extra hop in the client for no
    gain. They are also what makes a stale row legible: a session on a device that has not
    checked in for 13 hours is not "someone at their desk", and without `device_online` the
    page would present it as though it were.
    """

    id: uuid.UUID
    device_id: uuid.UUID
    hostname: str
    session_id: int
    username: str | None
    state: SessionState
    connection: SessionConnection
    station: str | None
    client_name: str | None
    logon_at: datetime | None
    idle_seconds: int | None

    # The device, not the session. A session's freshness IS its device's freshness — the
    # agent reports the whole set on every push — so these two answer "can I trust this row"
    # and "will an action on it be picked up now or whenever the machine comes back".
    device_online: bool
    device_last_seen_at: datetime | None

    # Group names this device belongs to, for the chips in the row. Names rather than ids:
    # the row renders them and never navigates by them, and resolving ids client-side would
    # mean loading the group table to draw a table of devices.
    groups: list[str] = []


class SessionCounts(BaseModel):
    """The tab counts above the table.

    Computed over the whole filtered set, not the current page — a count that only described
    the 15 rows on screen would say "Active 6" next to a page showing 6 of 40 active
    sessions, which is worse than showing no count at all.
    """
    all: int
    active: int
    disconnected: int
    console: int
    rdp: int


class DeviceSessionPage(BaseModel):
    items: list[DeviceSessionRead]
    total: int
    counts: SessionCounts
