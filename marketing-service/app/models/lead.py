import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin


class LeadStatus(str, enum.Enum):
    """The pipeline from docs/GO_TO_MARKET.md, as data.

    The stage names are copied from that document deliberately. If the sales process and
    this enum ever disagree, the document is right and this file is the bug — a CRM whose
    stages do not match how the team actually talks is a CRM nobody updates.
    """

    NEW = "new"                          # captured, nothing has happened yet
    CONTACTED = "contacted"              # a human has replied
    QUALIFIED = "qualified"              # meets the ICP bar in the GTM doc
    DISCOVERY_BOOKED = "discovery_booked"
    PILOT_PROPOSED = "pilot_proposed"
    PILOT_ACTIVE = "pilot_active"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    DISQUALIFIED = "disqualified"        # not a fit; kept, never deleted, so we learn


class LeadTier(str, enum.Enum):
    """What the scorer decided, which decides how fast a human must respond.

    Kept separate from `status` because they answer different questions: tier is about the
    lead's quality, status is about where it has got to. A hot lead can sit at NEW; that
    combination is exactly what the alert exists to prevent.
    """

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    UNSCORED = "unscored"


class Lead(TimestampMixin, Base):
    """A person who has raised their hand, deduplicated by email.

    One row per human, not per form fill. Someone who downloads the offboarding checklist
    in August and asks for a demo in September is one lead with two submissions, not two
    leads — otherwise the CRM fills with duplicates and the "have we talked to them?"
    question stops being answerable.

    Nothing here is ever hard-deleted. A disqualified lead is the training data that
    teaches the scorer what a bad lead looks like, and an unsubscribed one must be
    remembered precisely so we do not email it again.
    """

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    #: Lowercased at the service boundary, so the unique constraint actually deduplicates.
    #: "Danish@example.com" and "danish@example.com" are one person.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: Derived from the email at intake. A free-mail domain is the single strongest
    #: negative signal for a B2B endpoint-management product, and computing it once here
    #: keeps the scorer from re-parsing the address every time.
    email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_free_email: Mapped[bool] = mapped_column(default=False, nullable=False)

    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, native_enum=False, length=20),
        default=LeadStatus.NEW, nullable=False, index=True,
    )
    tier: Mapped[LeadTier] = mapped_column(
        Enum(LeadTier, native_enum=False, length=12),
        default=LeadTier.UNSCORED, nullable=False, index=True,
    )
    #: 0-100. The rules produce it; the model may adjust it. Stored alongside the reason
    #: so a human disagreeing with a score can see what it was reasoning from.
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Consent (DPDP Act 2023) ────────────────────────────────────────────────
    # Consent is a property of the person, not of a submission, and it has to be provable.
    # `consent_source` records *which* form and *what it said*, because "they filled in a
    # contact form" is not by itself consent to a nurture sequence.
    consent_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── What has happened to them ──────────────────────────────────────────────
    #: Set when the automatic acknowledgement went out. Null on a lead older than a minute
    #: means the email path is broken, which is a thing worth alerting on.
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Set when a human was told. Separate from acknowledged_at: the prospect being
    #: answered and the founder being told are two different promises.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── CRM ────────────────────────────────────────────────────────────────────
    crm_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    crm_record_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    crm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list["LeadSubmission"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadSubmission.created_at",
    )

    @property
    def is_contactable(self) -> bool:
        """Whether marketing email may be sent to this person right now."""
        return self.unsubscribed_at is None and self.consent_at is not None


class LeadSubmission(TimestampMixin, Base):
    """One form fill, with the attribution that produced it.

    Attribution belongs here rather than on the lead because it is per-touch: the campaign
    that first found someone and the campaign that finally made them ask for a demo are
    usually different, and collapsing them onto the person destroys exactly the fact the
    performance loop needs. The lead's *first* submission is acquisition; the *last* one
    is conversion; both are recoverable from this table and neither is from a flat column.
    """

    __tablename__ = "lead_submissions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: Which surface produced it — "contact_form", "lead_magnet:offboarding-checklist",
    #: "assessment_page". Free text rather than an enum so the website can add a form
    #: without a migration here.
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    #: The "Interested in" dropdown on the contact form.
    interest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    landing_page: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    utm_medium: Mapped[str | None] = mapped_column(String(160), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    utm_content: Mapped[str | None] = mapped_column(String(160), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(160), nullable=True)

    #: Set once the downstream automation (n8n) has been handed this submission. Null on
    #: an old row is the replay job's work queue — this is what makes n8n being down cost
    #: a delay rather than a lead.
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="submissions")
