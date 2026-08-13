"""Two things a person could do themselves, done for them when they ask.

Both are automatic, and both are validated the same way every other parameter in the
registry is: against a fixed set, not a shape. A value that merely looks right is the
failure worth preventing here — a time zone that Windows accepts but the person did not
mean moves every appointment in their calendar, and neither the user nor the audit log
would show anything wrong.
"""
import pytest

from app.core.security import hash_opaque_token
from app.models import Device, RemediationSource, RemediationStatus
from app.services.remediation.actions import ACTIONS, RemediationTier
from app.services.remediation.service import RemediationError, RemediationService


async def _device(session, org_id, hostname="SELFSVC-PC"):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11 Pro", agent_version="0.7.4",
        token_hash=hash_opaque_token(hostname),
    )
    session.add(device)
    await session.flush()
    return device


async def _create(session, org_id, device, action_id, params):
    return await RemediationService(session).create_task(
        org_id=org_id, device=device, action_id=action_id, params=params,
        reason="user asked", source=RemediationSource.ASSISTANT, actor_user_id=None,
    )


def test_the_clock_is_machine_wide_and_the_printer_belongs_to_a_person():
    """The execution contexts are not interchangeable and getting them the wrong way round
    fails silently: a printer attached by the elevated service lands in LocalSystem's
    profile, reports success, and never appears for the person who asked."""
    assert ACTIONS["set_timezone"].execution_context == "system"
    assert ACTIONS["add_network_printer"].execution_context == "user"
    # Both are things the user could do themselves, so neither waits for an approver.
    assert ACTIONS["set_timezone"].tier is RemediationTier.AUTOMATIC
    assert ACTIONS["add_network_printer"].tier is RemediationTier.AUTOMATIC


async def test_a_real_time_zone_is_accepted(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await _create(session, admin_user.org_id, device, "set_timezone",
                             {"timezone_id": "Eastern Standard Time"})
    assert task.params == {"timezone_id": "Eastern Standard Time"}
    assert task.status is RemediationStatus.APPROVED   # automatic — straight to the device


@pytest.mark.parametrize("bad", [
    "EST",                      # the abbreviation a person would type
    "Eastern standard time",    # right words, wrong case — tzutil is case-sensitive
    "America/New_York",         # the IANA name, which Windows does not use
    "Atlantis Standard Time",   # shaped like an identifier, names nowhere
    "",
])
async def test_anything_windows_would_not_recognise_is_refused(
    session_factory, admin_user, bad
):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError):
            await _create(session, admin_user.org_id, device, "set_timezone",
                          {"timezone_id": bad})


async def test_a_share_path_is_accepted(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await _create(session, admin_user.org_id, device, "add_network_printer",
                             {"printer_path": r"\\printserver\reception"})
    assert task.params == {"printer_path": r"\\printserver\reception"}


@pytest.mark.parametrize("bad", [
    r"printserver\reception",       # no leading \\ — a relative path, not a share
    r"\\printserver",               # a host with no share
    r"\\printserver\a\b",           # deeper than a share: not a printer
    r"\\printserver\rec*ption",     # a wildcard Windows forbids in a share name
    r"C:\Windows\System32",         # a local path
    "",
])
async def test_anything_that_is_not_a_share_path_is_refused(
    session_factory, admin_user, bad
):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="printer"):
            await _create(session, admin_user.org_id, device, "add_network_printer",
                          {"printer_path": bad})


async def test_a_printer_name_may_contain_spaces_and_dashes(session_factory, admin_user):
    """Real printers are called things like "HP LaserJet - 2nd floor". Rejecting those would
    make the action useless for exactly the fleets that have print servers."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await _create(session, admin_user.org_id, device, "add_network_printer",
                             {"printer_path": r"\\print-01\HP LaserJet - 2nd floor"})
    assert task.params["printer_path"] == r"\\print-01\HP LaserJet - 2nd floor"
