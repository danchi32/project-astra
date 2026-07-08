"""Seed the demo SQLite database with one org + admin for local testing.

Self-contained: sets the same demo env as run_demo.py before importing the app,
so it targets the identical database file regardless of CWD.
"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

DB_PATH = os.path.join(BACKEND_DIR, "astra-demo.db").replace("\\", "/")
os.environ.setdefault("ASTRA_DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")
os.environ.setdefault("ASTRA_JWT_SECRET_KEY", "demo-secret-key-local-only-not-for-prod")

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Base, Organization, User, UserRole  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        existing = await session.execute(
            select(User).where(User.email == "admin@test.com")
        )
        if existing.scalar_one_or_none() is not None:
            print("Admin already exists: admin@test.com / TestPassword123!")
            return
        org = Organization(name="Meri Company")
        session.add(org)
        await session.flush()
        session.add(
            User(
                org_id=org.id,
                email="admin@test.com",
                full_name="Admin User",
                hashed_password=hash_password("TestPassword123!"),
                role=UserRole.ADMIN,
            )
        )
        await session.commit()
    print("Seeded: admin@test.com / TestPassword123!")


if __name__ == "__main__":
    asyncio.run(main())
