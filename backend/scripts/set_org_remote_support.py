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
DISABLE    set to "1" to also drop the remote_control entitlement (full withdrawal).

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
    disable = os.environ.get("DISABLE", "").strip() == "1"
    if not email:
        print("ORG_EMAIL is required")
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
        # None rather than empty string: the column means "no group" as NULL, and the
        # provisioning check reads it as such.
        new_mesh = ("mesh//" + mesh_id if mesh_id and not mesh_id.startswith("mesh//")
                    else mesh_id or None)

        if org.entitlement_overrides == overrides and org.meshcentral_mesh_id == new_mesh:
            print(f"already set for org {org.name!r} ({org.id})")
            return 0

        org.entitlement_overrides = overrides or None
        org.meshcentral_mesh_id = new_mesh
        await session.commit()
        print(f"org {org.name!r} ({org.id}):")
        print(f"  remote_control entitlement = {overrides[REMOTE_CONTROL]}")
        print(f"  meshcentral_mesh_id        = {new_mesh}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
