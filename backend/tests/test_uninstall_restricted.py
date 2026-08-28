"""Uninstalling software: who may ask, and for what.

Every other remediation is constrained by a fixed allowlist in the registry file. This one
cannot be — the permitted targets are whatever the customer decided they do not want, which
is the point of the feature. That makes the validation the security boundary, so it is
tested from both directions: what it must allow, and what it must refuse even when asked
by an administrator of the organization.

The latitude differs by caller, and that difference is load-bearing, so both are covered:
the AI may only name software the org restricted; an admin working from a device's own
software inventory may name anything unprotected; UNINSTALL_NEVER refuses both.
"""
import pytest

from app.core.security import hash_opaque_token
from app.models import Device, RemediationSource, RemediationStatus
from app.services.compliance import ComplianceService
from app.services.remediation.actions import ACTIONS, RemediationTier
from app.services.remediation.service import RemediationError, RemediationService


async def _device(session, org_id, hostname="UNINST-PC"):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11", agent_version="0.7.4",
        token_hash=hash_opaque_token(hostname),
    )
    session.add(device)
    await session.flush()
    return device


async def _create(session, org_id, device, app_name, approver=None,
                  source=RemediationSource.USER):
    """An admin pushing the Software tab's per-row Uninstall."""
    return await RemediationService(session).create_task(
        org_id=org_id, device=device, action_id="uninstall_application",
        params={"app_name": app_name}, reason="policy", source=source,
        actor_user_id=None, approver=approver,
    )


async def _propose(session, org_id, device, app_name):
    """The AI engine's path — the constrained one."""
    return await _create(session, org_id, device, app_name,
                         source=RemediationSource.ASSISTANT)


def test_the_action_is_elevated_and_admin_only():
    """It removes software from someone's machine. Neither property is incidental: a
    user-session process could not uninstall a machine-wide install, and no tier below
    admin should be able to authorise destroying software across a fleet."""
    action = ACTIONS["uninstall_application"]
    assert action.tier is RemediationTier.ADMIN_ONLY
    assert action.execution_context == "system"


async def test_software_the_org_restricted_can_be_uninstalled(session_factory, admin_user):
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=admin_user, name="Google Chrome")
        device = await _device(session, admin_user.org_id)
        task = await _propose(session, admin_user.org_id, device, "Google Chrome")

    assert task.action_id == "uninstall_application"
    assert task.params == {"app_name": "Google Chrome"}
    # Admin-only work is never queued straight to a device.
    assert task.status is RemediationStatus.PENDING_APPROVAL


async def test_the_ai_cannot_name_software_nobody_restricted(session_factory, admin_user):
    """Without this the parameter is a free-text command for the model to delete any program
    on the machine — the exact shape the allowlists elsewhere in the registry exist to
    prevent. The organization's own policy list is this action's allowlist."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="restricted-software list"):
            await _propose(session, admin_user.org_id, device, "Microsoft Excel")


async def test_an_admin_may_remove_software_nobody_restricted(session_factory, admin_user):
    """The Software tab's per-row Uninstall. The admin is reading the device's own inventory
    and picked a row from it; making them first edit org-wide policy to remove one app from
    one machine would mean adding entries they intend to delete straight afterwards.

    The tier does not move with the caller: this still lands as PENDING_APPROVAL."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await _create(session, admin_user.org_id, device, "Microsoft Excel")

    assert task.params == {"app_name": "Microsoft Excel"}
    assert task.status is RemediationStatus.PENDING_APPROVAL


async def test_one_org_cannot_reach_another_orgs_list(
    session_factory, admin_user, other_org_user
):
    """The list is per-organization, so the check has to be too — otherwise restricting
    something in one tenant would quietly authorise the AI removing it in every other."""
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=other_org_user, name="Google Chrome")
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="restricted-software list"):
            await _propose(session, admin_user.org_id, device, "Google Chrome")


@pytest.mark.parametrize("protected", [
    "Windows Defender", "CrowdStrike Falcon Sensor", "SentinelOne Agent",
    "ASTRA Agent", "Sophos Endpoint",
])
async def test_protected_software_is_refused_even_when_restricted(
    session_factory, admin_user, protected
):
    """An organization putting its own endpoint protection on the restricted list is the
    move an attacker with portal access would make. The list is a policy statement, not
    an authorisation to disarm the fleet — so this refuses even though the org asked.

    Both callers are checked. The admin path is the one a stolen portal session has, and
    it is the path that widened, so it is the one that most needs holding."""
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=admin_user, name=protected)
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="protected"):
            await _propose(session, admin_user.org_id, device, protected)
        with pytest.raises(RemediationError, match="protected"):
            await _create(session, admin_user.org_id, device, protected)


async def test_a_blank_or_oversized_name_is_refused(session_factory, admin_user):
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=admin_user, name="Google Chrome")
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="required"):
            await _create(session, admin_user.org_id, device, "   ")
        with pytest.raises(RemediationError, match="too long"):
            await _create(session, admin_user.org_id, device, "Google Chrome" + "x" * 400)


async def test_the_match_is_the_orgs_pattern_not_an_exact_name(session_factory, admin_user):
    """Registry display names carry versions and editions the policy list never will —
    "Google Chrome" is what an administrator types, "Google Chrome 138.0.7204.51" is what
    the machine reports. Matching exactly would refuse every real installation."""
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=admin_user, name="Google Chrome")
        device = await _device(session, admin_user.org_id)
        task = await _propose(session, admin_user.org_id, device, "Google Chrome 138.0.7204.51")
    assert task.params["app_name"] == "Google Chrome 138.0.7204.51"
