import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class EmailSendMethod(str, enum.Enum):
    """How ASTRA sends mail on the org's behalf. Only DNS is implemented today; the
    OAuth methods are reserved so the sender-resolution layer can grow into them
    without a schema change."""
    DNS = "dns"                    # verified sending domain via Resend (SPF/DKIM)
    OAUTH_GOOGLE = "oauth_google"  # reserved — Gmail API
    OAUTH_MICROSOFT = "oauth_microsoft"  # reserved — Microsoft Graph


class EmailVerificationStatus(str, enum.Enum):
    UNCONFIGURED = "unconfigured"  # no sender set yet
    PENDING = "pending"            # domain created, waiting on DNS records
    VERIFIED = "verified"          # DNS confirmed — sends as the org
    FAILED = "failed"              # verification attempted but records not found


class EmailSettings(TimestampMixin, Base):
    """One organization's outbound-email identity. For the DNS method we register the
    org's domain with the email provider (Resend), cache the DNS records they must add,
    and only send as them once the domain is verified."""

    __tablename__ = "email_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    method: Mapped[EmailSendMethod] = mapped_column(
        Enum(EmailSendMethod, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=EmailSendMethod.DNS,
    )
    status: Mapped[EmailVerificationStatus] = mapped_column(
        Enum(EmailVerificationStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=EmailVerificationStatus.UNCONFIGURED,
    )

    from_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Provider bookkeeping (Resend): the domain id + the DNS records the org must add.
    provider_domain_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dns_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Org-customizable asset-assignment email. Null = use the built-in default template.
    # Bodies are plain text with {{placeholders}}; the acknowledge button is appended
    # (or positioned with {{acknowledge_button}}).
    asset_email_subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    asset_email_body: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
