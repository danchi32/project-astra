from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Create a new organization + its first admin. Requires a valid invite code
    (org creation is invite-only, not open self-service)."""

    invite_code: str = Field(min_length=1)
    organization_name: str = Field(min_length=1, max_length=200)
    admin_name: str = Field(min_length=1, max_length=200)
    admin_email: EmailStr
    admin_password: str = Field(min_length=12)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
