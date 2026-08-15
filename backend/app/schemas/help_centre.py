"""Customer-facing support documentation.

Separate from `schemas.knowledge` because the audiences differ. A knowledge article is
shown to IT staff who own it and may argue with it, so it carries the learning evidence.
A help article is shown to whoever is stuck right now, so it carries the code they can see
and the category they would browse — and nothing about how ASTRA scores itself.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

#: The sections a customer browses. Kept as a constant so the operator's authoring form and
#: the customer's filter cannot drift apart, and so a typo does not create a category with
#: one article in it that nobody finds.
HELP_CATEGORIES: list[str] = [
    "installation",     # getting the agent onto a machine
    "agent",            # an installed agent misbehaving
    "network",          # firewall, proxy, DNS, TLS
    "portal",           # the web app itself
    "devices",          # enrolment, telemetry, device state
    "billing",          # invoices, seats, plans
    "security",         # permissions, antivirus, policy
    "other",
]


class HelpArticleSummary(BaseModel):
    """One row in a list. Carries no body — a search result page does not need 20 KB
    of article per hit."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    help_category: str | None
    error_code: str | None
    created_at: datetime


class HelpArticleRead(HelpArticleSummary):
    content: str


class HelpArticleAdminRead(HelpArticleRead):
    """What the operator sees. Unlike the customer's view this includes drafts, so
    `published_at` has to travel with it."""
    published_at: datetime | None = None


class HelpArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20000)
    help_category: str | None = Field(default=None, max_length=40)
    error_code: str | None = Field(default=None, max_length=40)


class HelpArticleUpdate(BaseModel):
    """A partial edit.

    Omitting a field leaves it alone; sending it as null clears it. The two are told apart
    by `model_fields_set`, because collapsing them would make it impossible to remove an
    error code that was entered by mistake.
    """
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    help_category: str | None = Field(default=None, max_length=40)
    error_code: str | None = Field(default=None, max_length=40)
    #: True publishes, False withdraws. Withdrawing also stops the assistant answering
    #: from it — one switch, so the help centre and the AI can never disagree.
    published: bool | None = None
