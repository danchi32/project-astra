"""USB storage block / unblock — the registry properties this pair must keep.

There is no parameter to validate and no per-org list to check, so what matters here is
the shape of the two actions: both destructive-adjacent enough to demand an admin, both run
by the elevated service, and a genuine reversible pair. Those are exactly the properties a
later edit could weaken without any test noticing, so they are pinned.
"""
from app.core.security import hash_opaque_token
from app.models import Device, RemediationSource, RemediationStatus
from app.services.remediation.actions import ACTIONS, RemediationTier
from app.services.remediation.service import RemediationService


def test_the_pair_is_elevated_and_admin_only():
    for action_id in ("block_usb_storage", "unblock_usb_storage"):
        action = ACTIONS[action_id]
        # Admin-only: closing a port across a fleet, or reopening one, is not a change any
        # lower tier should be able to wave through.
        assert action.tier is RemediationTier.ADMIN_ONLY, action_id
        # Elevated: the driver switch lives under HKLM and needs LocalSystem.
        assert action.execution_context == "system", action_id
        # No parameters — the action is the whole instruction, so there is no free-text field
        # to constrain and nothing an org could pass to widen what it does.
        assert action.params == (), action_id


def test_they_are_a_reversible_pair():
    # Each names the other's effect, so an operator can always undo what they did.
    assert "unblock_usb_storage" in ACTIONS["block_usb_storage"].description
    assert "block_usb_storage" in ACTIONS["unblock_usb_storage"].description


async def _device(session, org_id):
    device = Device(
        org_id=org_id, hostname="USB-PC", machine_id="usb-pc",
        os_version="Windows 11", agent_version="0.8.0",
        token_hash=hash_opaque_token("USB-PC"),
    )
    session.add(device)
    await session.flush()
    return device


async def test_blocking_is_created_pending_approval(session_factory, admin_user):
    """Admin-only work is never queued straight to a device — it waits for an approver even
    when the person creating it is one, unless they approve in the same call."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        task = await RemediationService(session).create_task(
            org_id=admin_user.org_id, device=device, action_id="block_usb_storage",
            params=None, reason="policy", source=RemediationSource.USER,
            actor_user_id=None,
        )
    assert task.action_id == "block_usb_storage"
    assert task.status is RemediationStatus.PENDING_APPROVAL
