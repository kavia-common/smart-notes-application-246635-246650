from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.db import get_session
from src.api.deps import get_current_user
from src.api.models import Note, Tag, User
from src.api.schemas.notes import NoteCreate, NoteOut, NotePatch

router = APIRouter(prefix="/notes", tags=["Notes"])


def _normalize_tag(name: str) -> Optional[str]:
    t = name.strip().lower()
    return t or None


async def _get_or_create_tags(
    session: AsyncSession, *, user_id: UUID, names: List[str]
) -> List[Tag]:
    normalized = []
    for n in names:
        v = _normalize_tag(n)
        if v and v not in normalized:
            normalized.append(v)

    if not normalized:
        return []

    # Fetch existing tags
    existing = (
        await session.scalars(
            select(Tag).where(and_(Tag.user_id == user_id, Tag.name.in_(normalized)))
        )
    ).all()
    existing_by_name = {t.name: t for t in existing}

    tags: List[Tag] = []
    for name in normalized:
        tag = existing_by_name.get(name)
        if not tag:
            tag = Tag(user_id=user_id, name=name)
            session.add(tag)
        tags.append(tag)

    # Flush so new tags get ids before association updates
    await session.flush()
    return tags


def _note_out(note: Note) -> NoteOut:
    return NoteOut(
        id=str(note.id),
        title=note.title,
        content=note.content,
        tags=[t.name for t in (note.tags or [])],
        pinned=bool(note.pinned),
        favorite=bool(note.favorite),
        createdAt=note.created_at,
        updatedAt=note.updated_at,
    )


async def _get_note_or_404(
    session: AsyncSession, *, user_id: UUID, note_id: UUID
) -> Note:
    note = await session.scalar(
        select(Note)
        .options(selectinload(Note.tags))
        .where(and_(Note.id == note_id, Note.user_id == user_id, Note.deleted_at.is_(None)))
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.get(
    "",
    response_model=List[NoteOut],
    summary="List notes",
    description="List notes for the current user with optional filters (search/tag/pinned/favorite).",
    operation_id="notes_list",
)
async def list_notes(
    q: Optional[str] = Query(None, description="Search query (matches title/content)."),
    tag: Optional[str] = Query(None, description="Filter by a tag name."),
    pinned: Optional[bool] = Query(None, description="Filter by pinned."),
    favorite: Optional[bool] = Query(None, description="Filter by favorite."),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> List[NoteOut]:
    """
    List notes (newest updated first). Supports:
      - q: simple ILIKE search over title/content
      - tag: tag name
      - pinned/favorite booleans
    """
    stmt = (
        select(Note)
        .options(selectinload(Note.tags))
        .where(and_(Note.user_id == user.id, Note.deleted_at.is_(None)))
    )

    if q:
        qq = f"%{q.strip()}%"
        stmt = stmt.where(or_(Note.title.ilike(qq), Note.content.ilike(qq)))

    if pinned is not None:
        stmt = stmt.where(Note.pinned == pinned)

    if favorite is not None:
        stmt = stmt.where(Note.favorite == favorite)

    if tag:
        t = _normalize_tag(tag)
        if t:
            stmt = stmt.join(Note.tags).where(Tag.name == t).distinct()

    stmt = stmt.order_by(Note.updated_at.desc())

    notes = (await session.scalars(stmt)).all()
    return [_note_out(n) for n in notes]


@router.get(
    "/{note_id}",
    response_model=NoteOut,
    summary="Get note",
    description="Fetch a single note by id (must belong to the current user).",
    operation_id="notes_get",
)
async def get_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> NoteOut:
    """Get a note by id."""
    try:
        nid = UUID(note_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Note not found")

    note = await _get_note_or_404(session, user_id=user.id, note_id=nid)
    return _note_out(note)


@router.post(
    "",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
    description="Create a new note for the current user.",
    operation_id="notes_create",
)
async def create_note(
    payload: NoteCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> NoteOut:
    """
    Create a note.

    Notes:
      - Title defaults to 'Untitled'
      - Tags are normalized to lowercase and de-duplicated
    """
    now = datetime.now(timezone.utc)

    note = Note(
        user_id=user.id,
        title=(payload.title or "Untitled").strip() or "Untitled",
        content=(payload.content or ""),
        pinned=bool(payload.pinned),
        favorite=bool(payload.favorite),
        created_at=now,
        updated_at=now,
    )

    tags = await _get_or_create_tags(session, user_id=user.id, names=payload.tags or [])
    note.tags = tags

    session.add(note)
    await session.commit()
    await session.refresh(note)

    # Ensure tags are loaded for response
    note = await _get_note_or_404(session, user_id=user.id, note_id=note.id)
    return _note_out(note)


@router.patch(
    "/{note_id}",
    response_model=NoteOut,
    summary="Update note",
    description="Autosave-friendly partial update (PATCH) for a note.",
    operation_id="notes_patch",
)
async def patch_note(
    note_id: str,
    payload: NotePatch,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> NoteOut:
    """
    Partial update for autosave.

    Accepts any subset of:
      - title, content, tags, pinned, favorite
    """
    try:
        nid = UUID(note_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Note not found")

    note = await _get_note_or_404(session, user_id=user.id, note_id=nid)

    if payload.title is not None:
        note.title = payload.title.strip()

    if payload.content is not None:
        note.content = payload.content

    if payload.pinned is not None:
        note.pinned = bool(payload.pinned)

    if payload.favorite is not None:
        note.favorite = bool(payload.favorite)

    if payload.tags is not None:
        tags = await _get_or_create_tags(session, user_id=user.id, names=payload.tags)
        note.tags = tags

    # Ensure updatedAt changes for engines without triggers (e.g., SQLite tests).
    note.updated_at = datetime.now(timezone.utc)

    await session.commit()

    note = await _get_note_or_404(session, user_id=user.id, note_id=nid)
    return _note_out(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Soft-delete a note (marks deleted_at).",
    operation_id="notes_delete",
)
async def delete_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a note by id."""
    try:
        nid = UUID(note_id)
    except Exception:
        # Idempotent delete behavior: treat invalid ids as not found.
        raise HTTPException(status_code=404, detail="Note not found")

    note = await session.scalar(
        select(Note).where(and_(Note.id == nid, Note.user_id == user.id, Note.deleted_at.is_(None)))
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.deleted_at = datetime.now(timezone.utc)
    note.updated_at = datetime.now(timezone.utc)
    await session.commit()
