import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin, utcnow


class EmailSendMethod(str, enum.Enum):
    """How ASTRA sends mail on the org's behalf.

    SHARED and DNS are a real choice, not a ladder. Verifying a domain means getting DNS
    records added, which in a lot of companies means a ticket to somebody else and a wait
    of days — while the asset emails they signed up for sit undelivered. SHARED works the
    moment they create the organization, at the cost of the From address being ours.

    The OAuth methods are reserved so the sender-resolution layer can grow into them
    without a schema change.
    """
    SHARED = "shared"              # ASTRA's own verified address, sent on the org's behalf
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
        # SHARED by default: a new organization can send on day one. Choosing DNS is a
        # deliberate upgrade, not the only road out of a broken state.
        nullable=False, default=EmailSendMethod.SHARED,
    )
    status: Mapped[EmailVerificationStatus] = mapped_column(
        Enum(EmailVerificationStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=EmailVerificationStatus.UNCONFIGURED,
    )

    from_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Where a reply goes. Without it, an employee who hits Reply on an asset email sent
    # from our address writes to astra@technomateai.com — which nobody reads on the
    # customer's behalf, so their question simply disappears. That makes it close to
    # required for SHARED and merely useful for DNS, where replies at least land in the
    # org's own domain.
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Provider bookkeeping (Resend): the domain id + the DNS records the org must add.
    provider_domain_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dns_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Who else gets a copy of the asset-assignment email. CC rather than BCC on purpose:
    # the point is that Reply All reaches IT, and a BCC'd address is invisible to the
    # recipient's mail client, so their reply would go only to the sender.
    #
    # Scoped to THIS message deliberately. Password resets, OTPs and login alerts are
    # written for one person and copying an administrator on them would hand that person's
    # account to somebody else.
    asset_email_cc: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Org-customizable asset-assignment email. Null = use the built-in default template.
    # Bodies carry {{placeholders}}; the acknowledge button is appended (or positioned with
    # {{acknowledge_button}}).
    asset_email_subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    asset_email_body: Mapped[str | None] = mapped_column(String(20000), nullable=True)

    # "text" or "html". Bodies written before the rich-text editor existed are plain text and
    # must keep rendering that way — escaped, newlines turned into breaks. Recorded rather
    # than guessed from the content: a sniffer would read a plain-text body that happens to
    # say "<3" as markup and silently eat it.
    asset_email_body_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="text", server_default="text"
    )

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
