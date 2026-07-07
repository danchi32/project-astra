"""Bootstrap the first organization and admin user.

Usage:
    python -m scripts.create_admin --org "Acme Corp" --email admin@acme.com --name "Jane Admin"

The password is read from the ASTRA_BOOTSTRAP_PASSWORD environment variable
so it never appears in shell history.
"""
import argparse
import asyncio
import os
import sys

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Organization, User, UserRole
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create the initial organization and admin user")
    parser.add_argument("--org", required=True, help="Organization name")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--name", required=True, help="Admin full name")
    args = parser.parse_args()

    password = os.environ.get("ASTRA_BOOTSTRAP_PASSWORD")
    if not password or len(password) < 12:
        print("Set ASTRA_BOOTSTRAP_PASSWORD (min 12 characters) before running.", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        orgs = OrganizationRepository(session)
        users = UserRepository(session)

        if await users.get_by_email(args.email) is not None:
            print(f"User {args.email} already exists — nothing to do.", file=sys.stderr)
            return 1

        org = await orgs.get_by_name(args.org)
        if org is None:
            org = await orgs.add(Organization(name=args.org))

        await users.add(
            User(
                org_id=org.id,
                email=args.email.lower(),
                full_name=args.name,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        await session.commit()

    print(f"Admin {args.email} created in organization '{args.org}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
