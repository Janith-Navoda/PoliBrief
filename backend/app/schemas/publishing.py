"""
PoliBrief Backend — Pydantic Schemas for Facebook / Meta Publishing
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetaStatusOut(BaseModel):
    configured: bool
    valid: bool
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    page_link: Optional[str] = None
    category: Optional[str] = None
    message: str


class PublishResultOut(BaseModel):
    success: bool
    draft_id: int
    platform: str
    platform_post_id: Optional[str] = None
    fb_url: Optional[str] = None
    published_at: datetime
    message: str


class PublishResolution(BaseModel):
    """Administrator reconciliation after a publish request has an unknown outcome."""

    outcome: Literal["CONFIRMED_PUBLISHED", "CONFIRMED_NOT_PUBLISHED"]
    platform_post_id: Optional[str] = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def require_post_id_for_confirmed_publication(self):
        if self.outcome == "CONFIRMED_PUBLISHED" and not (self.platform_post_id or "").strip():
            raise ValueError("platform_post_id is required when confirming a published post.")
        if self.outcome == "CONFIRMED_NOT_PUBLISHED" and self.platform_post_id:
            raise ValueError("platform_post_id must be omitted when confirming no post exists.")
        return self


class PublishedPostOut(BaseModel):
    id: int
    draft_id: int
    platform: str
    platform_post_id: Optional[str] = None
    published_at: datetime
    status: str
    headline: Optional[str] = None
    publisher_name: Optional[str] = None
    category: Optional[str] = None
    caption: Optional[str] = None
    image_url: Optional[str] = None
    fb_link: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
