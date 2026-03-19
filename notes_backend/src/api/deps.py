from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_session
from src.api.models import User
from src.api.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


# PUBLIC_INTERFACE
async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Resolve the authenticated user from Authorization: Bearer <token>.

    Returns:
      ORM User instance.
    """
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = decode_access_token(creds.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing sub claim")
        uid = UUID(str(user_id))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await session.scalar(select(User).where(User.id == uid))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user
