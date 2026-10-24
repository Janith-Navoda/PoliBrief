"""
PoliBrief Backend — News Sources API Router
Endpoints for managing publisher feeds, testing RSS connectivity, and manual collection triggers.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.database.session import get_db
from backend.app.models import Administrator, Article, NewsSource
from backend.app.schemas.source import (
    SourceCreate,
    SourceOut,
    SourceTestResult,
    SourceUpdate,
)
from backend.app.services.collector.rss import is_safe_feed_url, test_feed_url
from backend.app.services.collector.runner import run_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

DEFAULT_POLITICAL_FEEDS = [
    {
        "publisher_name": "NPR Politics",
        "rss_url": "https://feeds.npr.org/1014/rss.xml",
        "website_url": "https://www.npr.org/sections/politics/",
        "language": "en",
        "content_restrictions": '{"attribution_required": true, "commercial_use": false}',
    },
    {
        "publisher_name": "PBS NewsHour Politics",
        "rss_url": "https://www.pbs.org/newshour/feeds/rss/politics",
        "website_url": "https://www.pbs.org/newshour/politics",
        "language": "en",
        "content_restrictions": '{"attribution_required": true}',
    },
    {
        "publisher_name": "BBC News - Politics",
        "rss_url": "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "website_url": "https://www.bbc.com/news/politics",
        "language": "en",
        "content_restrictions": '{"attribution_required": true}',
    },
]


class TestUrlRequest(BaseModel):
    url: str = Field(min_length=10, max_length=512)


@router.get("", response_model=list[SourceOut])
def list_sources(
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """List all configured news sources with associated article counts."""
    # Count articles per source
    counts_query = (
        db.query(Article.source_id, func.count(Article.id).label("count"))
        .group_by(Article.source_id)
        .all()
    )
    counts = {source_id: count for source_id, count in counts_query if source_id is not None}

    sources = db.query(NewsSource).order_by(NewsSource.publisher_name.asc()).all()
    results = []
    for s in sources:
        out = SourceOut.model_validate(s)
        out.article_count = counts.get(s.id, 0)
        results.append(out)
    return results


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Add a new RSS publisher source."""
    if not is_safe_feed_url(payload.rss_url.strip()):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="RSS URL must be a public HTTP or HTTPS address.")

    existing = db.query(NewsSource).filter(NewsSource.rss_url == payload.rss_url.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A news source with RSS URL '{payload.rss_url}' already exists.",
        )

    source = NewsSource(
        publisher_name=payload.publisher_name.strip(),
        rss_url=payload.rss_url.strip(),
        website_url=payload.website_url.strip() if payload.website_url else None,
        language=payload.language.strip() if payload.language else "en",
        enabled=payload.enabled,
        content_restrictions=payload.content_restrictions,
        status="PENDING",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    out = SourceOut.model_validate(source)
    out.article_count = 0
    return out


@router.get("/{source_id}", response_model=SourceOut)
def get_source(
    source_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Get single news source by ID."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News source not found.")

    article_count = db.query(func.count(Article.id)).filter(Article.source_id == source.id).scalar() or 0
    out = SourceOut.model_validate(source)
    out.article_count = article_count
    return out


@router.put("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Update news source settings (publisher name, RSS URL, enabled status, etc.)."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News source not found.")

    if payload.rss_url is not None and payload.rss_url.strip() != source.rss_url:
        if not is_safe_feed_url(payload.rss_url.strip()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="RSS URL must be a public HTTP or HTTPS address.")
        existing = db.query(NewsSource).filter(NewsSource.rss_url == payload.rss_url.strip()).first()
        if existing and existing.id != source.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RSS URL '{payload.rss_url}' is already in use by another source.",
            )
        source.rss_url = payload.rss_url.strip()

    if payload.publisher_name is not None:
        source.publisher_name = payload.publisher_name.strip()
    if payload.website_url is not None:
        source.website_url = payload.website_url.strip() if payload.website_url else None
    if payload.language is not None:
        source.language = payload.language.strip()
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.content_restrictions is not None:
        source.content_restrictions = payload.content_restrictions

    db.commit()
    db.refresh(source)

    article_count = db.query(func.count(Article.id)).filter(Article.source_id == source.id).scalar() or 0
    out = SourceOut.model_validate(source)
    out.article_count = article_count
    return out


@router.delete("/{source_id}", status_code=status.HTTP_200_OK)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Delete a news source. Existing collected articles will have source_id set to NULL."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News source not found.")

    publisher_name = source.publisher_name
    db.delete(source)
    db.commit()
    return {"detail": f"News source '{publisher_name}' deleted successfully."}


@router.post("/test-url", response_model=SourceTestResult)
async def test_raw_url(
    payload: TestUrlRequest,
    admin: Administrator = Depends(get_current_admin),
):
    """Test any arbitrary RSS URL before adding it as a source."""
    result = await test_feed_url(payload.url.strip())
    return SourceTestResult(**result)


@router.post("/{source_id}/test", response_model=SourceTestResult)
async def test_existing_source(
    source_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Test live connectivity of an existing news source feed."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News source not found.")

    result = await test_feed_url(source.rss_url)
    return SourceTestResult(**result)


@router.post("/{source_id}/refresh")
def refresh_single_source(
    source_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Trigger an immediate fetch for a single news source."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News source not found.")

    result = run_collection(db=db, source_id=source.id)
    return {
        "detail": f"Refresh triggered for '{source.publisher_name}'.",
        "result": result,
    }


@router.post("/refresh-all")
def refresh_all_sources(
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Trigger an immediate fetch across all enabled news sources."""
    result = run_collection(db=db)
    return {
        "detail": "Collection completed across all enabled sources.",
        "result": result,
    }


@router.post("/seed-defaults", response_model=list[SourceOut])
def seed_default_sources(
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Seed standard permitted political news feeds if they do not already exist."""
    seeded = []
    for item in DEFAULT_POLITICAL_FEEDS:
        existing = db.query(NewsSource).filter(NewsSource.rss_url == item["rss_url"]).first()
        if not existing:
            source = NewsSource(
                publisher_name=item["publisher_name"],
                rss_url=item["rss_url"],
                website_url=item["website_url"],
                language=item["language"],
                enabled=True,
                content_restrictions=item.get("content_restrictions"),
                status="PENDING",
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            out = SourceOut.model_validate(source)
            out.article_count = 0
            seeded.append(out)
    return seeded
