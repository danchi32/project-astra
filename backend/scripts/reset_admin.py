"""Reset an admin password (or create the admin if missing).

Run it in the Railway backend service Shell — it uses the same database the
running app does:

    python scripts/reset_admin.py admin@astra.com AstraAdmin123456!

If the user exists, its password is reset, its role set to admin, and its
account reactivated. If no such user exists, an admin is created in the first
organization (or a new "My Organization" if the database is empty).
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Organization, User, UserRole  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Reset or create an admin user")
    parser.add_argument("email", help="Admin email address")
    parser.add_argument("password", help="New password (min 12 characters)")
    parser.add_argument("--org", default="My Organization", help="Org name if one must be created")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if len(args.password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is not None:
            user.hashed_password = hash_password(args.password)
            user.role = UserRole.ADMIN
            user.is_active = True
            await session.commit()
            print(f"Password reset for {email} (role=admin, active).")
            return 0

        org_result = await session.execute(select(Organization).limit(1))
        org = org_result.scalar_one_or_none()
        if org is None:
            org = Organization(name=args.org)
            session.add(org)
            await session.flush()

        session.add(
            User(
                org_id=org.id,
                email=email,
                full_name="Administrator",
                hashed_password=hash_password(args.password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()
        print(f"Admin {email} created in organization '{org.name}'.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
