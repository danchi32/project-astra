from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import EmailSendMethod, EmailVerificationStatus


class EmailDnsRecord(BaseModel):
    type: str          # TXT / MX / CNAME
    name: str          # the host, e.g. send.acme.com
    value: str
    ttl: str = "Auto"
    priority: int | None = None
    purpose: str = ""  # DKIM / SPF / …
    status: str = ""


class EmailSettingsRead(BaseModel):
    """The org's outbound-email identity + what (if anything) still needs doing."""
    configured: bool                       # a sending address has been set
    provider_ready: bool                   # the platform has an email provider configured
    status: EmailVerificationStatus
    #: Which of the two the org has chosen. Not a progress indicator — an org on `shared`
    #: is finished, not stuck partway through setting up `dns`.
    method: EmailSendMethod = EmailSendMethod.SHARED
    #: What a recipient will actually see in the From line, resolved server-side so the
    #: portal shows the same answer the send path will use rather than guessing at it.
    effective_from: str = ""
    reply_to: str | None = None
    from_name: str | None = None
    from_address: str | None = None
    domain: str | None = None
    dns_records: list[EmailDnsRecord] = []
    last_error: str | None = None
    verified_at: datetime | None = None
    # Asset-assignment email template. When null, the built-in default (returned here) is used.
    asset_email_subject: str | None = None
    asset_email_body: str | None = None
    asset_email_placeholders: list[str] = []


class EmailSettingsConfigure(BaseModel):
    """Set up the org's own sending domain (method = dns)."""
    from_name: str = Field(min_length=1, max_length=120)
    from_address: EmailStr


class EmailSenderChoice(BaseModel):
    """Pick how mail goes out.

    `shared` needs nothing but a display name — it works immediately. `dns` only takes
    effect once the domain verifies; until then the shared sender keeps delivering, so
    switching is never a period of silence.
    """
    method: EmailSendMethod
    #: The name recipients see. For `shared` it is shown as "<name> (via ASTRA)".
    from_name: str | None = Field(default=None, max_length=120)
    #: Where replies go. Strongly advised on `shared`: the From address is ASTRA's, so
    #: without this a reply reaches us and not the customer's IT team.
    reply_to: EmailStr | None = None


class AssetEmailTemplateUpdate(BaseModel):
    """Customize the asset-assignment email. Empty strings reset to the default."""
    subject: str = Field(max_length=300)
    body: str = Field(max_length=4000)
