from __future__ import annotations

from pydantic import BaseModel, Field


class TagSummaryOut(BaseModel):
    name: str = Field(..., description="Tag name.")
    count: int = Field(..., description="Number of notes using this tag.")
