from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import get_settings
from src.api.db import init_db_schema
from src.api.routers.auth import router as auth_router
from src.api.routers.notes import router as notes_router
from src.api.routers.tags import router as tags_router

openapi_tags = [
    {"name": "Health", "description": "Service health and readiness endpoints."},
    {"name": "Auth", "description": "JWT-based authentication endpoints."},
    {"name": "Notes", "description": "Per-user notes CRUD, search, tags, pin/favorite."},
    {"name": "Tags", "description": "Per-user tag summaries."},
]


# PUBLIC_INTERFACE
def create_app() -> FastAPI:
    """
    Create the FastAPI application.

    The app provides:
      - JWT auth: POST /auth/register, POST /auth/login, GET /auth/me
      - Notes CRUD: GET/POST /notes, GET/PATCH/DELETE /notes/{id}
      - Tag summaries: GET /tags
    """
    settings = get_settings()

    app = FastAPI(
        title="Smart Notes API",
        description="Backend API for the Smart Notes application (JWT auth + per-user notes).",
        version="1.0.0",
        openapi_tags=openapi_tags,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(notes_router)
    app.include_router(tags_router)

    @app.on_event("startup")
    async def _startup() -> None:
        # In production, the `notes_database` container initializes schema.
        # For tests/dev, DB_AUTO_CREATE=true creates tables from SQLAlchemy metadata.
        if settings.db_auto_create:
            await init_db_schema()

    @app.get(
        "/",
        tags=["Health"],
        summary="Health check",
        description="Simple health check endpoint.",
        operation_id="health_check",
    )
    def health_check():
        """Return a simple liveness response."""
        return {"message": "Healthy"}

    return app


app = create_app()
