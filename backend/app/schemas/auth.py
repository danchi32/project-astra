import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_PHONE_SEPARATORS = re.compile(r"[\s\-.()]")
#: E.164: a country code that does not start with 0, at most 15 digits in all.
_E164 = re.compile(r"\+[1-9]\d{6,14}")


def normalize_phone(value: str) -> str:
    """'+91 85954 92500' / '0091-85954-92500' -> '+918595492500', or ValueError.

    The country code is required: without it a number is ambiguous, and guessing one
    would store a wrong number that looks right.
    """
    phone = _PHONE_SEPARATORS.sub("", value)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not _E164.fullmatch(phone):
        raise ValueError(
            "Enter a valid phone number with its country code, e.g. +91 85954 92500"
        )
    return phone


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Create a new organization + its first admin. Open self-service signup; an
    invite code is optional (still honored/consumed if one is supplied)."""

    invite_code: str | None = Field(default=None)
    organization_name: str = Field(min_length=1, max_length=200)
    admin_name: str = Field(min_length=1, max_length=200)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    #: Required on every new signup; stored E.164-normalised. Existing organisations
    #: predate it, which is why the column is nullable and this field is not.
    phone: str = Field(max_length=40)
    #: The signup form's clickwrap. Defaults to False, so a client that omits it is
    #: REJECTED rather than silently treated as agreeing — the whole point of the record
    #: is that it proves a deliberate act, and a default of True would prove nothing.
    terms_accepted: bool = False

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)


class RegisterVerifyRequest(BaseModel):
    """Second step of email-verified signup: confirm the 6-digit code."""
    admin_email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterStartResponse(BaseModel):
    """When email is configured, `otp_required` is True and a code was emailed —
    the client then calls /register/verify. When email is off, the org is created
    immediately and tokens are returned here."""
    otp_required: bool
    access_token: str | None = None
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
