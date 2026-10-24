"""
PoliBrief Backend — Near-Duplicate Detection Engine
Uses RapidFuzz string similarity algorithms (token_set_ratio and partial_ratio)
to detect syndication duplicates while preserving multi-source reporting diversity.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from backend.app.models import Article

# Similarity thresholds
SAME_PUBLISHER_DUPLICATE_THRESHOLD = 85.0   # Same outlet published minor headline revision
CROSS_PUBLISHER_SIMILARITY_THRESHOLD = 70.0  # Different outlets covering the same event
RECENCY_WINDOW_HOURS = 72                    # Compare against recent articles


def normalize_headline(headline: str) -> str:
    """Normalize headline for comparison: lowercase, remove punctuation, collapse whitespace."""
    if not headline:
        return ""
    text = headline.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_near_duplicate(
    headline: str,
    source_id: Optional[int],
    db: Session,
    published_at: Optional[datetime] = None,
) -> Optional[tuple[Article, float]]:
    """
    Check if a candidate article is an unwanted duplicate of an existing article
    from the SAME publisher within the recent recency window.
    Returns: (matching_article, similarity_score) if a duplicate is found, else None.
    """
    if not headline or not source_id:
        return None

    norm_candidate = normalize_headline(headline)
    if not norm_candidate:
        return None

    ref_date = published_at or datetime.now(timezone.utc)
    cutoff = ref_date - timedelta(hours=RECENCY_WINDOW_HOURS)

    # Query recent articles from the same publisher
    recent_articles = (
        db.query(Article)
        .filter(
            Article.source_id == source_id,
            Article.published_at >= cutoff,
        )
        .all()
    )

    for existing in recent_articles:
        norm_existing = normalize_headline(existing.headline)
        # Use token_set_ratio which handles reordered words and minor omissions
        score = fuzz.token_set_ratio(norm_candidate, norm_existing)
        if score >= SAME_PUBLISHER_DUPLICATE_THRESHOLD:
            return existing, score

    return None


def find_related_stories(
    headline: str,
    article_id: int,
    db: Session,
    limit: int = 5,
) -> list[dict]:
    """
    Find other publishers covering the same political story (Preserves source diversity).
    Returns list of related articles with similarity scores.
    """
    norm_candidate = normalize_headline(headline)
    if not norm_candidate:
        return []

    origin = db.query(Article.source_id).filter(Article.id == article_id).first()
    if not origin:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENCY_WINDOW_HOURS)
    query = db.query(Article).filter(
        Article.id != article_id,
        Article.published_at >= cutoff,
        Article.status == "ACTIVE",
    )
    if origin[0] is not None:
        query = query.filter(Article.source_id != origin[0])
    candidates = query.all()

    matches = []
    for art in candidates:
        norm_art = normalize_headline(art.headline)
        score = fuzz.token_set_ratio(norm_candidate, norm_art)
        if score >= CROSS_PUBLISHER_SIMILARITY_THRESHOLD:
            matches.append({
                "article_id": art.id,
                "headline": art.headline,
                "publisher_name": art.source.publisher_name if art.source else "Unknown",
                "similarity": round(score, 1),
                "published_at": art.published_at.isoformat() if art.published_at else None,
            })

    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches[:limit]
