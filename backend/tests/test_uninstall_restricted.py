"""Uninstalling restricted software: who may ask, and for what.

Every other remediation is constrained by a fixed allowlist in the registry file. This one
cannot be — the permitted targets are whatever the customer decided they do not want, which
is the point of the feature. That makes the validation the security boundary, so it is
tested from both directions: what it must allow, and what it must refuse even when asked
by an administrator of the organization.
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


async def _create(session, org_id, device, app_name, approver=None):
    return await RemediationService(session).create_task(
        org_id=org_id, device=device, action_id="uninstall_application",
        params={"app_name": app_name}, reason="policy", source=RemediationSource.USER,
        actor_user_id=None, approver=approver,
    )


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
        task = await _create(session, admin_user.org_id, device, "Google Chrome")

    assert task.action_id == "uninstall_application"
    assert task.params == {"app_name": "Google Chrome"}
    # Admin-only work is never queued straight to a device.
    assert task.status is RemediationStatus.PENDING_APPROVAL


async def test_software_nobody_restricted_is_refused(session_factory, admin_user):
    """Without this the parameter is a free-text command to delete any program on the
    machine — the exact shape the allowlists elsewhere in the registry exist to prevent."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="restricted-software list"):
            await _create(session, admin_user.org_id, device, "Microsoft Excel")


async def test_one_org_cannot_reach_another_orgs_list(
    session_factory, admin_user, other_org_user
):
    """The list is per-organization, so the check has to be too — otherwise restricting
    something in one tenant would quietly authorise removing it in every other."""
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=other_org_user, name="Google Chrome")
        device = await _device(session, admin_user.org_id)
        with pytest.raises(RemediationError, match="restricted-software list"):
            await _create(session, admin_user.org_id, device, "Google Chrome")


@pytest.mark.parametrize("protected", [
    "Windows Defender", "CrowdStrike Falcon Sensor", "SentinelOne Agent",
    "ASTRA Agent", "Sophos Endpoint",
])
async def test_protected_software_is_refused_even_when_restricted(
    session_factory, admin_user, protected
):
    """An organization putting its own endpoint protection on the restricted list is the
    move an attacker with portal access would make. The list is a policy statement, not
    an authorisation to disarm the fleet — so this refuses even though the org asked."""
    async with session_factory() as session:
        await ComplianceService(session).add_banned(actor=admin_user, name=protected)
        device = await _device(session, admin_user.org_id)
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
        task = await _create(session, admin_user.org_id, device, "Google Chrome 138.0.7204.51")
    assert task.params["app_name"] == "Google Chrome 138.0.7204.51"
