from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: Optional[str] = Field(None, description="Note title.")
    content: Optional[str] = Field(None, description="Markdown note content.")
    tags: Optional[List[str]] = Field(None, description="List of tags.")
    pinned: Optional[bool] = Field(False, description="Whether the note is pinned.")
    favorite: Optional[bool] = Field(False, description="Whether the note is a favorite.")


class NotePatch(BaseModel):
    title: Optional[str] = Field(None, description="Updated note title.")
    content: Optional[str] = Field(None, description="Updated markdown note content.")
    tags: Optional[List[str]] = Field(None, description="Replace tags with this list.")
    pinned: Optional[bool] = Field(None, description="Set pinned flag.")
    favorite: Optional[bool] = Field(None, description="Set favorite flag.")


class NoteOut(BaseModel):
    id: str = Field(..., description="Note id (UUID).")
    title: str = Field(..., description="Note title.")
    content: str = Field(..., description="Markdown content.")
    tags: List[str] = Field(default_factory=list, description="Tags for this note.")
    pinned: bool = Field(..., description="Pinned flag.")
    favorite: bool = Field(..., description="Favorite flag.")
    createdAt: datetime = Field(..., description="Creation timestamp (ISO).")
    updatedAt: datetime = Field(..., description="Last update timestamp (ISO).")
