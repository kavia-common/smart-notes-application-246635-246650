from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_session
from src.api.deps import get_current_user
from src.api.models import Tag, User, note_tags
from src.api.schemas.tags import TagSummaryOut

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "",
    response_model=List[TagSummaryOut],
    summary="List tags",
    description="Return tag usage counts for the current user's notes.",
    operation_id="tags_list",
)
async def list_tags(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> List[TagSummaryOut]:
    """
    Returns tag summaries for the current user:
      - name
      - count (number of notes associated with the tag)
    """
    stmt = (
        select(Tag.name, func.count(note_tags.c.note_id).label("count"))
        .select_from(Tag)
        .join(note_tags, Tag.id == note_tags.c.tag_id, isouter=True)
        .where(Tag.user_id == user.id)
        .group_by(Tag.name)
        .order_by(Tag.name.asc())
    )
    rows = (await session.execute(stmt)).all()
    return [TagSummaryOut(name=name, count=int(count or 0)) for name, count in rows]
