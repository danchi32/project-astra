"""Grant (or revoke) platform-admin — the super-admin who manages ALL organizations.

Usage (locally, or in the Railway backend shell):
    python scripts/set_platform_admin.py admin@yourco.com
    python scripts/set_platform_admin.py admin@yourco.com --off   # revoke

The user must already exist (register an org first, then promote its admin).
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Grant/revoke platform-admin")
    parser.add_argument("email")
    parser.add_argument("--off", action="store_true", help="Revoke instead of grant")
    args = parser.parse_args()

    email = args.email.strip().lower()
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email}. Register/create the user first.", file=sys.stderr)
            return 1
        user.is_platform_admin = not args.off
        await session.commit()
        print(f"{email}: is_platform_admin = {user.is_platform_admin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
