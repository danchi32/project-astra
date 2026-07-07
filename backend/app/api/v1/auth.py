from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.users import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


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
