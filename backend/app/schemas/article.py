"""
PoliBrief Backend — Pydantic Schemas for Articles
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ArticleBase(BaseModel):
    headline: str
    description: Optional[str] = None
    original_url: str
    canonical_url: Optional[str] = None
    category: str = "Other / Needs Review"
    classification_score: float = 0.0
    published_at: Optional[datetime] = None


class ArticleOut(ArticleBase):
    id: int
    source_id: Optional[int] = None
    publisher_name: Optional[str] = None
    collected_at: datetime
    expires_at: Optional[datetime] = None
    fingerprint: Optional[str] = None
    status: str
    publishing_status: str = "NONE"
    publishing_draft_id: Optional[int] = None
    publication_record_id: Optional[int] = None
    publication_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ArticleUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, max_length=32)


class ArticleListResponse(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int
    total_pages: int
