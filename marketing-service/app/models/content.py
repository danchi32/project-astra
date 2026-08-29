import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin


def _enum_values(enum_class) -> list[str]:
    """Store member values, not names — see the note in app/models/lead.py."""
    return [member.value for member in enum_class]


class ContentStatus(enum.StrEnum):
    """Where a piece of content has got to.

    The transitions are enforced in ContentService, not here, but the shape is worth
    reading in one place:

        DRAFT ──► IN_REVIEW ──► APPROVED ──► SCHEDULED ──► PUBLISHED
                     │  ▲
                     ▼  │
              CHANGES_REQUESTED

    There is no edge from anywhere back to PUBLISHED, and none from DRAFT straight to
    APPROVED. Publishing is the one-way door.
    """

    DRAFT = "draft"                          # being written or revised
    IN_REVIEW = "in_review"                  # sent to a human, waiting
    CHANGES_REQUESTED = "changes_requested"  # a human asked for something different
    APPROVED = "approved"                    # a named human said yes to a NAMED VERSION
    SCHEDULED = "scheduled"                  # approved and queued for a time
    PUBLISHED = "published"                  # out in the world
    ARCHIVED = "archived"                    # abandoned; kept, because rejections teach


class ContentChannel(enum.StrEnum):
    LINKEDIN = "linkedin"
    X = "x"
    BLOG = "blog"
    EMAIL = "email"
    YOUTUBE = "youtube"
    GBP = "google_business_profile"


class ContentEventType(enum.StrEnum):
    """Every state change is an event, and events are never deleted.

    This is the audit trail. Who approved what, when, and which version of the words they
    were actually looking at — the last part being the one that matters, and the one a
    status column alone cannot answer.
    """

    CREATED = "created"
    REVISED = "revised"
    CHECKED = "checked"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    PUBLISH_REFUSED = "publish_refused"
    ARCHIVED = "archived"


class ContentItem(TimestampMixin, Base):
    """One piece of content, from brief to publication.

    The item holds the state; the words live in versions. `approved_version_id` is the
    reason for that split: approval attaches to an exact set of words, never to the item.
    Approve, then revise, and the approval no longer applies to anything on screen — which
    is precisely the case a status column would have let through.
    """

    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    channel: Mapped[ContentChannel] = mapped_column(
        Enum(ContentChannel, native_enum=False, length=32, values_callable=_enum_values),
        nullable=False, index=True,
    )
    #: The campaign this belongs to, matching marketing/analytics/utm-conventions.md, so a
    #: published post can be traced to the leads it produced.
    campaign: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    #: What this was asked to be. Kept because a draft that drifted from its brief is the
    #: most common thing a reviewer rejects, and the brief is how they can tell.
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, native_enum=False, length=24, values_callable=_enum_values),
        default=ContentStatus.DRAFT, nullable=False, index=True,
    )

    #: The newest version. What a reviewer sees, and what a revision replaces.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    #: The version a human said yes to. Publishing checks that this still equals
    #: `current_version_id` — approve, revise, publish must not put unreviewed words out.
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The URL the post ended up at, and the platform's own id for it. Both are needed to
    #: collect performance later, and neither can be reconstructed afterwards.
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── The approval desk ──────────────────────────────────────────────────────
    # The Telegram message currently asking for a decision on this item. Stored so a
    # plain reply — "make it more concrete" — can be traced back to what it is about;
    # Telegram gives a reply the id of the message it answers and nothing else.
    #
    # Overwritten when a new version is sent for review. A reply to a superseded message
    # therefore finds nothing, which is the right answer: the conversation moved on, and
    # acting on it would apply feedback to words the sender was not looking at.
    review_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    review_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Eager, because nothing in this domain reads an item without its history: a
    # reviewer needs the versions, an audit needs the events, and lazy loading them under
    # asyncio raises MissingGreenlet rather than quietly working. selectin batches them
    # into one extra query per collection instead of one per row.
    versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="ContentVersion.version_number", lazy="selectin",
    )
    events: Mapped[list["ContentEvent"]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="ContentEvent.created_at", lazy="selectin",
    )

    @property
    def approval_is_current(self) -> bool:
        """Whether the approved words are still the words on screen."""
        return (
            self.approved_version_id is not None
            and self.approved_version_id == self.current_version_id
        )


class ContentVersion(TimestampMixin, Base):
    """One draft. Never updated — a revision is a new row.

    Immutability is the whole point. "Version 3 was approved" means nothing if version 3
    can be edited afterwards, and a reviewer who is asked to trust the system has to be
    able to see exactly what they said yes to.
    """

    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: 1, 2, 3… unique per item. What a human says out loud: "approve v2".
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hashtags: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cta: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Object-store URL. The media itself never lives in the database.
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    #: The model that wrote it, or the person. Kept per version so a bad run is traceable
    #: to the model and prompt that produced it rather than to "the AI".
    authored_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Why this version exists — the feedback that prompted it. Null on v1.
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The claim checker's verdict on THIS text, stored with it. A version that passed and
    #: a version that was waved through are different things, and six months later the
    #: only way to tell them apart is a record made at the time.
    check_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    item: Mapped[ContentItem] = relationship(back_populates="versions")

    @property
    def blocked(self) -> bool:
        """Whether the claim checker refused this text."""
        return bool((self.check_result or {}).get("blockers"))


class ContentEvent(TimestampMixin, Base):
    """An append-only record of everything that happened to a piece of content.

    Separate from the status column because a status says where something is and an event
    log says how it got there. When a post goes out that should not have, the second is
    the only one that can answer why.
    """

    __tablename__ = "content_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Which version this happened to. An approval without one is unattributable.
    version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    event: Mapped[ContentEventType] = mapped_column(
        Enum(ContentEventType, native_enum=False, length=24, values_callable=_enum_values),
        nullable=False, index=True,
    )
    #: A person's identifier, or the name of the automation. Never blank: "the system did
    #: it" is the answer that makes an audit log worthless.
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[ContentItem] = relationship(back_populates="events")
