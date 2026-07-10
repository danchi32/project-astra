"""Create the first organization + admin on a fresh production database.

Idempotent and safe to run on every deploy: does nothing if any user already
exists. Credentials come from the environment so nothing is hardcoded:

    ASTRA_BOOTSTRAP_ADMIN_EMAIL
    ASTRA_BOOTSTRAP_ADMIN_PASSWORD   (>= 12 chars)
    ASTRA_BOOTSTRAP_ORG_NAME         (default "My Organization")

If the email/password vars are unset, this is a no-op — the deploy proceeds and
an admin can be created another way.
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Organization, User, UserRole  # noqa: E402


async def main() -> None:
    email = os.environ.get("ASTRA_BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("ASTRA_BOOTSTRAP_ADMIN_PASSWORD")
    org_name = os.environ.get("ASTRA_BOOTSTRAP_ORG_NAME", "My Organization")

    if not email or not password:
        print("[bootstrap] No bootstrap admin configured — skipping.")
        return
    if len(password) < 12:
        print("[bootstrap] ASTRA_BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters — skipping.")
        return

    async with SessionLocal() as session:
        existing = await session.execute(select(func.count()).select_from(User))
        if existing.scalar_one() > 0:
            print("[bootstrap] Users already exist — skipping.")
            return

        org = Organization(name=org_name)
        session.add(org)
        await session.flush()
        session.add(
            User(
                org_id=org.id,
                email=email.lower(),
                full_name="Administrator",
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        await session.commit()
        print(f"[bootstrap] Created organization '{org_name}' and admin {email}.")


if __name__ == "__main__":
    asyncio.run(main())
