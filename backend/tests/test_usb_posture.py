"""The USB state a device reports, and how the fleet count reads it.

The one property that has to hold is that the flag reflects what the agent reported and not
what ASTRA asked for — and, at the seam, that an agent too old to report it does not blank
out or fabricate a state. False is a real value here (allowed), so the usual truthiness
guard would be a bug; that is what these tests pin.
"""
from app.core.security import hash_opaque_token
from app.models import Device
from app.schemas.devices import HeartbeatRequest
from app.services.compliance import ComplianceService
from app.services.devices import DeviceService


async def _device(session, org_id, *, hostname="USB-1", blocked=None):
    device = Device(
        org_id=org_id, hostname=hostname, machine_id=hostname.lower(),
        os_version="Windows 11", agent_version="0.8.1",
        token_hash=hash_opaque_token(hostname), usb_storage_blocked=blocked,
    )
    session.add(device)
    await session.flush()
    return device


async def test_a_reported_state_is_stored(session_factory, admin_user):
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id)
        await DeviceService(session).heartbeat(
            device=device,
            data=HeartbeatRequest(agent_version="0.8.1", usb_storage_blocked=True),
        )
        assert device.usb_storage_blocked is True

        await DeviceService(session).heartbeat(
            device=device,
            data=HeartbeatRequest(agent_version="0.8.1", usb_storage_blocked=False),
        )
        assert device.usb_storage_blocked is False, "a device must be able to report allowed"


async def test_an_old_agent_that_omits_it_leaves_the_state_alone(session_factory, admin_user):
    """The field defaults to None when an agent does not send it. Reading that as 'allowed'
    would silently flip a blocked device to allowed on its next beat from an old agent."""
    async with session_factory() as session:
        device = await _device(session, admin_user.org_id, blocked=True)
        await DeviceService(session).heartbeat(
            device=device,
            data=HeartbeatRequest(agent_version="0.7.4"),  # no usb field at all
        )
        assert device.usb_storage_blocked is True, "an omitted field must not clear the state"


async def test_the_posture_counts_split_blocked_allowed_and_unknown(session_factory, admin_user):
    async with session_factory() as session:
        await _device(session, admin_user.org_id, hostname="B1", blocked=True)
        await _device(session, admin_user.org_id, hostname="B2", blocked=True)
        await _device(session, admin_user.org_id, hostname="A1", blocked=False)
        await _device(session, admin_user.org_id, hostname="U1", blocked=None)
        await session.commit()

    async with session_factory() as session:
        summary = await ComplianceService(session).summary(org_id=admin_user.org_id)

    assert summary.usb.blocked == 2
    assert summary.usb.allowed == 1
    # A device no reporting agent has beaten for is unknown, not assumed allowed.
    assert summary.usb.unknown == 1
