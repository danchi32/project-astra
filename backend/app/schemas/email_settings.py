from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import EmailVerificationStatus


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
    from_name: str = Field(min_length=1, max_length=120)
    from_address: EmailStr


class AssetEmailTemplateUpdate(BaseModel):
    """Customize the asset-assignment email. Empty strings reset to the default."""
    subject: str = Field(max_length=300)
    body: str = Field(max_length=4000)
