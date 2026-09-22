"""Turn remote control on (or off) for one organisation.

Both switches at once, because remote support needs both and setting one without the other
is the misconfiguration this exists to avoid: the entitlement without a device group is a
paid feature that cannot provision, and a group without the entitlement is a mapping that
answers no.

Runs as a Cloud Run job against the production database, the same way seed_builtin_assistant
does — so the connection string stays in Secret Manager and never reaches a laptop.

    gcloud run jobs deploy astra-set-remote-support \
      --image "$IMAGE" --region "$REGION" \
      --set-secrets ASTRA_DATABASE_URL=...,ASTRA_JWT_SECRET_KEY=... \
      --set-env-vars ORG_EMAIL=...,MESH_ID=...  \
      --command python --args scripts/set_org_remote_support.py
    gcloud run jobs execute astra-set-remote-support --region "$REGION" --wait

ORG_EMAIL  identifies the org — the org that user belongs to is the one configured.
MESH_ID    the relay device group id, WITHOUT the "mesh//" prefix. Empty string clears the
           group, which withdraws remote support operationally.
USER_ID    the relay account a viewer link logs in as, WITHOUT the "user//" prefix — the
           per-org account scoped on the relay to THIS org's group alone (never a site
           admin). Both this and MESH_ID are needed for a working, isolated session: the
           group is where the machines live, the user is who the technician's browser
           becomes. Empty string clears it, which stops any viewer link being issued.
DISABLE    set to "1" to also drop the remote_control entitlement (full withdrawal).

The two ids are the two halves of the cross-tenant boundary and are set together, because
a group without its own scoped user would fall back to nothing (no link) and a user
without its group is an account with rights to a group that holds none of this org's
machines. Provision both on the relay first (see infra/relay), then record them here.

Idempotent: re-running with the same values is a no-op that prints "already set".
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Organization, User  # noqa: E402
from app.services.entitlements import REMOTE_CONTROL  # noqa: E402


async def main() -> int:
    email = os.environ.get("ORG_EMAIL", "").strip().lower()
    mesh_id = os.environ.get("MESH_ID", "").strip()
    user_id = os.environ.get("USER_ID", "").strip()
    disable = os.environ.get("DISABLE", "").strip() == "1"
    if not email:
        print("ORG_EMAIL is required")
        return 2
    # A group without a scoped user issues no viewer link, which is a silent half-setup —
    # provisioned to enroll agents but unable to actually connect. Refuse it rather than
    # leave an operator wondering why the button does nothing.
    if mesh_id and not user_id:
        print("USER_ID is required whenever MESH_ID is set (both halves, or neither)")
        return 2

    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"no user with email {email!r}")
            return 1
        org = await session.get(Organization, user.org_id)
        if org is None:
            print("user has no organisation")
            return 1

        overrides = dict(org.entitlement_overrides or {})
        overrides[REMOTE_CONTROL] = not disable
        # None rather than empty string: the columns mean "not set" as NULL, and the
        # provisioning and viewer checks both read them as such.
        new_mesh = ("mesh//" + mesh_id if mesh_id and not mesh_id.startswith("mesh//")
                    else mesh_id or None)
        new_user = ("user//" + user_id if user_id and not user_id.startswith("user//")
                    else user_id or None)

        if (org.entitlement_overrides == overrides
                and org.meshcentral_mesh_id == new_mesh
                and org.meshcentral_user_id == new_user):
            print(f"already set for org {org.name!r} ({org.id})")
            return 0

        org.entitlement_overrides = overrides or None
        org.meshcentral_mesh_id = new_mesh
        org.meshcentral_user_id = new_user
        await session.commit()
        print(f"org {org.name!r} ({org.id}):")
        print(f"  remote_control entitlement = {overrides[REMOTE_CONTROL]}")
        print(f"  meshcentral_mesh_id        = {new_mesh}")
        print(f"  meshcentral_user_id        = {new_user}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
