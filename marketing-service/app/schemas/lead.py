import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.lead import LeadStatus, LeadTier


class LeadIntake(BaseModel):
    """What contact.php posts. Field names match the website's existing form payload.

    Everything except the email is optional, and that is deliberate: a lead that arrives
    with a valid address and nothing else is still a lead, and rejecting it to enforce a
    schema would throw away the thing we are here to collect. Validation that would reject
    a real prospect belongs in the scorer, not the parser.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)

    source: str = Field(default="contact_form", max_length=80)
    interest: str | None = Field(default=None, max_length=80)
    message: str | None = Field(default=None, max_length=8000)

    landing_page: str | None = Field(default=None, max_length=1000)
    referrer: str | None = Field(default=None, max_length=1000)
    utm_source: str | None = Field(default=None, max_length=160)
    utm_medium: str | None = Field(default=None, max_length=160)
    utm_campaign: str | None = Field(default=None, max_length=160)
    utm_content: str | None = Field(default=None, max_length=160)
    utm_term: str | None = Field(default=None, max_length=160)

    #: What the person actually agreed to, in the words the form used. Stored verbatim so
    #: a consent claim can be defended later rather than inferred.
    consent_text: str | None = Field(default=None, max_length=500)

    @field_validator("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        """The website sends "" for absent UTMs, not null.

        Left as-is, every organic lead would carry five empty strings and the campaign
        index would be full of rows meaning nothing.
        """
        return value or None


class LeadIntakeAccepted(BaseModel):
    """The response contact.php gets back.

    Deliberately thin. The website is a static export served to the public, so anything
    returned here is effectively public — it gets the lead id (opaque) and confirmation,
    and nothing about scoring, tiering, or whether this person is already known to us.
    """

    ok: bool = True
    lead_id: uuid.UUID
    submission_id: uuid.UUID
    #: True when this address had never been seen before. Useful to the website only for
    #: deciding which thank-you copy to show.
    is_new_lead: bool


class LeadSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    source: str
    interest: str | None
    message: str | None
    landing_page: str | None
    referrer: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None
    dispatched_at: datetime | None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    email: str
    name: str | None
    company: str | None
    phone: str | None
    email_domain: str | None
    is_free_email: bool
    status: LeadStatus
    tier: LeadTier
    score: int
    score_reason: str | None
    scored_at: datetime | None
    consent_source: str | None
    consent_at: datetime | None
    unsubscribed_at: datetime | None
    acknowledged_at: datetime | None
    notified_at: datetime | None
    first_contacted_at: datetime | None
    crm_provider: str | None
    crm_record_id: str | None
    crm_synced_at: datetime | None


class LeadDetail(LeadRead):
    submissions: list[LeadSubmissionRead] = []
