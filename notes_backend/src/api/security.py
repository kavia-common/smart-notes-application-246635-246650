from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from src.api.config import get_settings


_PBKDF2_ALG = "sha256"
_PBKDF2_ITERS = 210_000
_SALT_BYTES = 16


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64d(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Stored format:
      pbkdf2$sha256$<iters>$<salt_b64>$<dk_b64>
    """
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_ALG, password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return f"pbkdf2${_PBKDF2_ALG}${_PBKDF2_ITERS}${_b64e(salt)}${_b64e(dk)}"


# PUBLIC_INTERFACE
def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        scheme, alg, iters_s, salt_b64, dk_b64 = stored_hash.split("$", 4)
        if scheme != "pbkdf2" or alg != _PBKDF2_ALG:
            return False
        iters = int(iters_s)
        salt = _b64d(salt_b64)
        dk_expected = _b64d(dk_b64)
        dk = hashlib.pbkdf2_hmac(_PBKDF2_ALG, password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


# PUBLIC_INTERFACE
def create_access_token(*, user_id: str, email: str) -> str:
    """
    Create a signed JWT access token for the given user.

    Claims:
      - sub: user id
      - email: user email
      - exp: expiration (UTC)
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


# PUBLIC_INTERFACE
def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
