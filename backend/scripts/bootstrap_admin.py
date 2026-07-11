"""Ensure the bootstrap admin exists with a known password — on every deploy.

Idempotent and self-healing. Runs on each start from entrypoint.sh. Credentials
come from the environment so nothing is hardcoded:

    ASTRA_BOOTSTRAP_ADMIN_EMAIL
    ASTRA_BOOTSTRAP_ADMIN_PASSWORD   (>= 12 chars)
    ASTRA_BOOTSTRAP_ORG_NAME         (default "My Organization")

Behaviour when the vars are set:
  - admin missing            -> created (in the first org, or a new one)
  - admin exists, pw matches -> nothing to do
  - admin exists, pw drifted -> password reset, account reactivated, role=admin

This guarantees you can always log in with the configured credentials, instead
of relying on a one-off manual reset that can drift on later deploys. If the
email/password vars are unset this is a no-op.
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402
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

    email = email.lower()

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is not None:
            already_ok = user.is_active and verify_password(password, user.hashed_password)
            if already_ok:
                print(f"[bootstrap] Admin {email} already present with the configured password.")
                return
            user.hashed_password = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            await session.commit()
            print(f"[bootstrap] Admin {email} password re-asserted (role=admin, active).")
            return

        # No such admin — create it, reusing an existing org if there is one.
        org_result = await session.execute(select(Organization).limit(1))
        org = org_result.scalar_one_or_none()
        if org is None:
            org = Organization(name=org_name)
            session.add(org)
            await session.flush()

        session.add(
            User(
                org_id=org.id,
                email=email,
                full_name="Administrator",
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()
        print(f"[bootstrap] Created admin {email} in organization '{org.name}'.")


if __name__ == "__main__":
    asyncio.run(main())
