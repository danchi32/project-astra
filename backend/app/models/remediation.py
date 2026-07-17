import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class RemediationStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"  # higher-tier action awaiting a human
    APPROVED = "approved"                  # cleared for the agent to execute
    DISPATCHED = "dispatched"              # agent has picked it up
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class RemediationSource(str, enum.Enum):
    ASSISTANT = "assistant"  # proposed by the AI from a device chat
    USER = "user"            # created by a portal staff member


class RemediationTask(TimestampMixin, Base):
    __tablename__ = "remediation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    action_id: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=RemediationStatus.PENDING_APPROVAL,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)

    source: Mapped[RemediationSource] = mapped_column(
        Enum(RemediationSource, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    # When the AI proposed this from a device chat, the conversation to post the
    # execution result back into ("✅ done" / "⚠️ couldn't complete").
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)

    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
