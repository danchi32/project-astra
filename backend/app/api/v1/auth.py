from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterStartResponse,
    RegisterVerifyRequest,
    TokenResponse,
)
from app.schemas.settings import ChangePasswordRequest, ProfileUpdate
from app.schemas.users import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization + first admin (direct, no OTP)",
)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    access, refresh = await AuthService(session).register(body)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post(
    "/register/start",
    response_model=RegisterStartResponse,
    summary="Begin signup — emails a verification code when email is configured",
)
async def register_start(
    body: RegisterRequest, session: AsyncSession = Depends(get_db)
) -> RegisterStartResponse:
    otp_required, access, refresh = await AuthService(session).register_start(body)
    return RegisterStartResponse(otp_required=otp_required, access_token=access, refresh_token=refresh)


@router.post(
    "/register/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm the emailed code and create the organization",
)
async def register_verify(
    body: RegisterVerifyRequest, session: AsyncSession = Depends(get_db)
) -> TokenResponse:
    access, refresh = await AuthService(session).register_verify(body)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    access, refresh = await AuthService(session).login(body.email, body.password)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token")
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    access, new_refresh = await AuthService(session).refresh(body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
async def logout(body: RefreshRequest, session: AsyncSession = Depends(get_db)) -> None:
    await AuthService(session).logout(body.refresh_token)


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead, summary="Update your own profile")
async def update_me(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    return await AuthService(session).update_profile(
        user=current_user, full_name=body.full_name
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change your own password",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await AuthService(session).change_password(
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
