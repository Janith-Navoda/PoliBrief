"""
PoliBrief Backend — Pydantic Schemas for Post Drafts
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DraftBase(BaseModel):
    article_id: int
    headline_override: Optional[str] = Field(default=None, max_length=512)
    caption: Optional[str] = Field(default=None)
    template_id: str = Field(default="modern", max_length=64)
    headline_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    hashtag_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")


class DraftCreate(DraftBase):
    pass


class DraftUpdate(BaseModel):
    headline_override: Optional[str] = Field(default=None, max_length=512)
    caption: Optional[str] = None
    template_id: Optional[str] = Field(default=None, max_length=64)
    headline_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    hashtag_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    status: Optional[str] = Field(default=None, max_length=32)


class DraftArticleSummary(BaseModel):
    id: int
    headline: str
    original_url: str
    category: str
    publisher_name: Optional[str] = None
    published_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DraftOut(BaseModel):
    id: int
    article_id: int
    headline_override: Optional[str] = None
    caption: Optional[str] = None
    template_id: Optional[str] = "modern"
    headline_color: str = "#FFFFFF"
    hashtag_color: str = "#FFFFFF"
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    article: Optional[DraftArticleSummary] = None

    model_config = ConfigDict(from_attributes=True)


class PreviewResponse(BaseModel):
    image_url: str
    caption: str
    headline: str
    template_id: str
