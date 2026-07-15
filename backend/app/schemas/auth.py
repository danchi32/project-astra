from pydantic import BaseModel, EmailStr, Field


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
    admin_password: str = Field(min_length=12)


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
    new_password: str = Field(min_length=12)
