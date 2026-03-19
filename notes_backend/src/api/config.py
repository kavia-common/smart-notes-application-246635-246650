import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv


def _parse_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _normalize_async_database_url(database_url: str) -> str:
    """
    Convert common Postgres DSNs into an async SQLAlchemy URL.

    Examples:
      - postgresql://user:pass@host:5432/db -> postgresql+asyncpg://...
      - postgres://... -> postgresql+asyncpg://...
    """
    url = database_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "postgresql+asyncpg://" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    database_url: str
    jwt_secret: str
    jwt_access_token_expire_minutes: int
    cors_allow_origins: List[str]
    db_auto_create: bool


def _build_database_url_from_postgres_env() -> Optional[str]:
    """
    Try to construct DATABASE_URL from common POSTGRES_* env vars.

    Supported:
      - POSTGRES_URL (may not include auth)
      - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    """
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url:
        # If POSTGRES_URL already contains credentials, use it directly.
        # Otherwise, try to inject credentials from POSTGRES_USER/POSTGRES_PASSWORD.
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        if "://" in postgres_url and "@" in postgres_url:
            return postgres_url
        if postgres_url.startswith("postgresql://") and user and password:
            # postgresql://host:port/db -> postgresql://user:pass@host:port/db
            rest = postgres_url[len("postgresql://") :]
            return f"postgresql://{user}:{password}@{rest}"
        return postgres_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if port and db and user and password:
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    return None


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and validate settings.

    Required env vars:
      - DATABASE_URL (or compatible POSTGRES_* variables)
      - JWT_SECRET
    """
    # Load .env if present (local/dev). Does nothing in environments without .env.
    load_dotenv()

    database_url = os.getenv("DATABASE_URL") or _build_database_url_from_postgres_env()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Provide it in the environment (see .env.example)."
        )

    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is required. Provide it in the environment (see .env.example)."
        )

    expires_min = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

    cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS") or os.getenv("ALLOWED_ORIGINS")
    if not cors_origins_env:
        # Convenience: allow using FRONTEND_URL alone in simple deployments.
        cors_origins_env = os.getenv("FRONTEND_URL") or "http://localhost:3000"
    cors_allow_origins = _parse_csv(cors_origins_env) if cors_origins_env else []

    db_auto_create = os.getenv("DB_AUTO_CREATE", "false").lower() in {"1", "true", "yes"}

    normalized_db_url = _normalize_async_database_url(database_url)

    return Settings(
        database_url=normalized_db_url,
        jwt_secret=jwt_secret,
        jwt_access_token_expire_minutes=expires_min,
        cors_allow_origins=cors_allow_origins,
        db_auto_create=db_auto_create,
    )
