"""
PoliBrief Backend — Articles API Router
Endpoints for browsing, searching, filtering, and categorizing collected news articles.
"""
import logging
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.database.session import get_db
from backend.app.models import Administrator, Article, NewsSource
from backend.app.services.publishing.article_status import get_article_publishing_statuses
from backend.app.schemas.article import (
    ArticleListResponse,
    ArticleOut,
    ArticleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticleListResponse)
def list_articles(
    q: Optional[str] = Query(None, description="Search keyword in headline or description"),
    category: Optional[str] = Query(None, description="Filter by political category"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    status: Optional[str] = Query("ACTIVE", description="Filter by article status"),
    date_from: Optional[datetime] = Query(None, description="Filter published on or after"),
    date_to: Optional[datetime] = Query(None, description="Filter published on or before"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Browse, search, and filter collected news articles with pagination."""
    query = db.query(Article)

    if status:
        query = query.filter(Article.status == status)

    if source_id is not None:
        query = query.filter(Article.source_id == source_id)

    if category:
        query = query.filter(Article.category == category)

    if date_from:
        query = query.filter(Article.published_at >= date_from)

    if date_to:
        query = query.filter(Article.published_at <= date_to)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            (Article.headline.ilike(term)) | (Article.description.ilike(term))
        )

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    # Order newest published first, falling back to collected_at
    items = (
        query.order_by(desc(Article.published_at), desc(Article.collected_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Attach publisher names
    source_ids = {a.source_id for a in items if a.source_id is not None}
    sources_map = {}
    if source_ids:
        sources = db.query(NewsSource.id, NewsSource.publisher_name).filter(NewsSource.id.in_(source_ids)).all()
        sources_map = {s.id: s.publisher_name for s in sources}

    publication_statuses = get_article_publishing_statuses(db, [article.id for article in items])
    results = []
    for a in items:
        out = ArticleOut.model_validate(a)
        out.publisher_name = sources_map.get(a.source_id, "Unknown Source")
        status_data = publication_statuses.get(a.id)
        if status_data:
            for key, value in status_data.items():
                setattr(out, key, value)
        results.append(out)

    return ArticleListResponse(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/categories", response_model=list[dict])
def get_categories(
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Return distinct categories along with active article counts."""
    counts = (
        db.query(Article.category, func.count(Article.id))
        .filter(Article.status == "ACTIVE")
        .group_by(Article.category)
        .all()
    )
    return [{"category": cat, "count": cnt} for cat, cnt in counts]


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Retrieve single article details by ID."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")

    out = ArticleOut.model_validate(article)
    if article.source:
        out.publisher_name = article.source.publisher_name
    for key, value in get_article_publishing_statuses(db, [article.id])[article.id].items():
        setattr(out, key, value)
    return out


@router.get("/{article_id}/related", response_model=list[dict])
def get_related_articles(
    article_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Find recent similar coverage from other publishers without suppressing it."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")
    from backend.app.services.deduplication.matcher import find_related_stories
    return find_related_stories(article.headline, article.id, db)


@router.patch("/{article_id}", response_model=ArticleOut)
def update_article(
    article_id: int,
    payload: ArticleUpdate,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Update article properties (manual category correction or status change)."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")

    if payload.category is not None:
        article.category = payload.category.strip()
    if payload.status is not None:
        article.status = payload.status.strip()

    db.commit()
    db.refresh(article)

    out = ArticleOut.model_validate(article)
    if article.source:
        out.publisher_name = article.source.publisher_name
    for key, value in get_article_publishing_statuses(db, [article.id])[article.id].items():
        setattr(out, key, value)
    return out
