"""Record whether a remediation was the model's idea.

Every task the assistant creates is stored as source=ASSISTANT, whether the answer came
from Claude or from the built-in keyword rules — the two are indistinguishable afterwards.
That is fine for auditing and wrong for learning: a rule-driven fix teaches nothing, since
the rule already knew the answer, and writing a runbook for it fills the knowledge base
with things the system could always do.

Existing rows default to false. That is the honest value rather than a cautious one: we
cannot tell after the fact which of them the model produced, and guessing would seed the
knowledge base from fixes the rules had already handled.

Revision ID: 0049
Revises: 0048
"""
import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "remediation_tasks",
        sa.Column("from_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("remediation_tasks", "from_llm")
