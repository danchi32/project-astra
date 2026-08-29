"""Print the counts the public stats endpoint would return. Read-only.

Run as a Cloud Run Job so the production database URL never leaves GCP — the alternative
is pulling a customer database credential onto a workstation to answer a question about
four numbers.

    gcloud run jobs deploy astra-stats-peek --image <image> --region asia-southeast1 \
      --set-secrets ASTRA_DATABASE_URL=ASTRA_DATABASE_URL:latest,\
ASTRA_JWT_SECRET_KEY=ASTRA_JWT_SECRET_KEY:latest \
      --command python --args scripts/print_public_stats.py
    gcloud run jobs execute astra-stats-peek --region asia-southeast1 --wait

Deletes nothing, writes nothing, and touches no running service.
"""
import asyncio
import os
import sys

# `python scripts/x.py` puts scripts/ on sys.path, not the backend root — so `app` is not
# importable without this. Same two lines as scripts/bootstrap_admin.py, for the same
# reason and in the same place.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Device, Organization, User  # noqa: E402
from app.services.platform import PlatformService  # noqa: E402


async def main() -> None:
    async with SessionLocal() as session:
        stats = await PlatformService(session).public_stats()

        # Shown alongside so the exclusion is visible rather than assumed: if the two org
        # numbers match, no organisation is being treated as internal and our own
        # workspace would be on the homepage as a customer.
        all_orgs = (await session.execute(
            select(func.count()).select_from(Organization)
        )).scalar_one()
        all_devices = (await session.execute(
            select(func.count()).select_from(Device)
        )).scalar_one()
        internal_orgs = (await session.execute(
            select(func.count(func.distinct(User.org_id)))
            .where(User.is_platform_admin.is_(True))
        )).scalar_one()

    print("=" * 60)
    print("WHAT THE HOMEPAGE WOULD SHOW")
    print("=" * 60)
    print(f"  Organizations onboarded  : {stats.organizations}")
    print(f"  Devices under management : {stats.devices}")
    print(f"  Issues auto-healed       : {stats.remediations}")
    print(f"  Devices reporting in     : {stats.devices_online}")
    print()
    print("context (not published)")
    print(f"  organisations in total   : {all_orgs}")
    print(f"  of those, internal/ours  : {internal_orgs}")
    print(f"  devices in total         : {all_devices}")
    print(f"  devices in internal orgs : {all_devices - stats.devices}")


asyncio.run(main())
