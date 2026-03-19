from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    """User object returned to the frontend."""

    id: str = Field(..., description="User id (UUID).")
    email: EmailStr = Field(..., description="User email address.")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address used for login.")
    password: str = Field(..., min_length=6, description="Password (min 6 characters).")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address used for login.")
    password: str = Field(..., description="Password.")


class AuthResponse(BaseModel):
    token: str = Field(..., description="JWT access token (Bearer).")
    user: UserOut = Field(..., description="Authenticated user information.")
