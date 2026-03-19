from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_session
from src.api.deps import get_current_user
from src.api.models import User
from src.api.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from src.api.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register",
    description="Create a new account and return a JWT token.",
    operation_id="auth_register",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Register a new user.

    Body:
      - email: unique email
      - password: min length 6

    Returns:
      - token: JWT access token
      - user: id/email
    """
    email = payload.email.strip().lower()

    existing = await session.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user_id=str(user.id), email=user.email)
    return AuthResponse(token=token, user=_user_out(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login",
    description="Authenticate and return a JWT token.",
    operation_id="auth_login",
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Login using email/password and return a JWT token.
    """
    email = payload.email.strip().lower()

    user = await session.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user_id=str(user.id), email=user.email)
    return AuthResponse(token=token, user=_user_out(user))


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current user",
    description="Return the currently authenticated user.",
    operation_id="auth_me",
)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    """
    Get current user info from the JWT access token.
    """
    return _user_out(user)
