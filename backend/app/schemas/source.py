"""
PoliBrief Backend — Pydantic Schemas for News Sources
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceBase(BaseModel):
    publisher_name: str = Field(min_length=2, max_length=128, description="Name of the publisher/outlet")
    rss_url: str = Field(min_length=10, max_length=512, description="Public RSS or Atom feed URL")
    website_url: Optional[str] = Field(default=None, max_length=512, description="Publisher main website URL")
    language: str = Field(default="en", max_length=10, description="ISO language code")
    enabled: bool = Field(default=True, description="Whether this feed is actively fetched")
    content_restrictions: Optional[str] = Field(default=None, description="Optional JSON content use notes")


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    publisher_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    rss_url: Optional[str] = Field(default=None, min_length=10, max_length=512)
    website_url: Optional[str] = Field(default=None, max_length=512)
    language: Optional[str] = Field(default=None, max_length=10)
    enabled: Optional[bool] = None
    content_restrictions: Optional[str] = None


class SourceOut(SourceBase):
    id: int
    last_checked: Optional[datetime] = None
    last_success: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    article_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class SourceTestResult(BaseModel):
    valid: bool
    title: Optional[str] = None
    description: Optional[str] = None
    entry_count: int = 0
    sample_headlines: list[str] = Field(default_factory=list)
    message: str
