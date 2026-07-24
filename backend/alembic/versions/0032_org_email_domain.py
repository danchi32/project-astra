"""One organisation per corporate email domain

Adds organizations.email_domain and backfills it for existing orgs from their admin's
email (corporate domains only; personal/free providers stay null and may register freely).

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("email_domain", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_organizations_email_domain", "organizations", ["email_domain"], unique=False
    )

    # Backfill existing orgs so already-registered corporate domains are protected too.
    # Offline (SQL-generation) mode has no live connection to read from — skip the data step.
    from alembic import context

    if context.is_offline_mode():
        return

    from app.core.email_domains import corporate_domain

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT o.id AS org_id, u.email AS email, u.created_at AS created_at "
            "FROM organizations o "
            "JOIN users u ON u.org_id = o.id AND u.role = 'admin'"
        )
    ).fetchall()

    # Earliest admin per org wins.
    earliest: dict = {}
    for row in rows:
        key = row.org_id
        if key not in earliest or (row.created_at or "") < (earliest[key][1] or ""):
            earliest[key] = (row.email, row.created_at)

    for org_id, (email, _created) in earliest.items():
        domain = corporate_domain(email or "")
        if domain:
            bind.execute(
                sa.text(
                    "UPDATE organizations SET email_domain = :d "
                    "WHERE id = :id AND email_domain IS NULL"
                ),
                {"d": domain, "id": org_id},
            )


def downgrade() -> None:
    op.drop_index("ix_organizations_email_domain", table_name="organizations")
    op.drop_column("organizations", "email_domain")
