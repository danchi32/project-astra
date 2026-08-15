import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import SupportRequestPriority, SupportRequestStatus


class SupportMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    from_operator: bool
    author_email: str | None = None
    created_at: datetime


class SupportRequestSummary(BaseModel):
    """A row in either side's list. No thread and no diagnostics — those are the detail
    view's job, and a queue of 200 rows should not carry 200 fleet snapshots."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    subject: str
    category: str | None
    status: SupportRequestStatus
    priority: SupportRequestPriority
    created_at: datetime
    last_reply_at: datetime | None
    #: Operator queue only — which customer this came from.
    org_id: uuid.UUID | None = None
    org_name: str | None = None


class SupportRequestRead(SupportRequestSummary):
    """One thread in full.

    `diagnostics` is shown to the customer as well as the operator. What was collected
    about their fleet and sent to us is theirs to see — a support form that quietly
    attaches a snapshot is a support form nobody should trust.
    """
    diagnostics: dict | None = None
    resolved_at: datetime | None = None
    messages: list[SupportMessageRead] = []


class SupportRequestCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    category: str | None = Field(default=None, max_length=40)
    #: Customers may raise up to `high`. Urgent is a scheduling decision the operator
    #: makes, so a request asking for it is accepted and recorded as high.
    priority: SupportRequestPriority = SupportRequestPriority.NORMAL


class SupportReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class SupportRequestUpdate(BaseModel):
    """Operator-only. Customers move a thread by replying to it, not by setting a state."""
    status: SupportRequestStatus | None = None
    priority: SupportRequestPriority | None = None


class SupportQueue(BaseModel):
    """The operator's view: the rows plus how much is waiting overall."""
    requests: list[SupportRequestSummary]
    counts_by_status: dict[str, int]
