"""Issue a single-use invite code that authorizes creating ONE new organization.

Org creation is invite-only, so a new customer can't sign up without a code you
hand them. Run locally or in the Railway backend shell:

    python scripts/create_invite.py --note "Acme Corp" --days 30

The raw code is printed once — deliver it to the customer; they enter it on the
Sign-up page. Only its hash is stored.
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.services.invites import InviteService  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Issue an organization invite code")
    parser.add_argument("--note", default=None, help="A label, e.g. the customer name")
    parser.add_argument("--days", type=int, default=30, help="Days until the code expires")
    args = parser.parse_args()

    async with SessionLocal() as session:
        record, raw = await InviteService(session).create(note=args.note, expires_in_days=args.days)

    print(f"Invite code (single-use, expires {record.expires_at:%Y-%m-%d}):")
    print(f"    {raw}")
    if args.note:
        print(f"Note: {args.note}")


if __name__ == "__main__":
    asyncio.run(main())
