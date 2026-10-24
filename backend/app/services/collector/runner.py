"""
PoliBrief Backend — News Collection Pipeline Runner
Iterates through enabled NewsSource records, fetches feeds asynchronously,
creates Article records, updates source health stats, and logs run outcomes.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models import Article, DuplicateFingerprint, JobLog, NewsSource
from backend.app.services.collector.rss import (
    clean_html_summary,
    compute_fingerprint,
    fetch_feed_data,
    parse_entry_datetime,
    sanitize_url,
)

logger = logging.getLogger(__name__)


async def collect_from_source(source: NewsSource, db: Session) -> dict:
    """Fetch and ingest new articles from a single NewsSource."""
    now = datetime.now(timezone.utc)
    result = {
        "source_id": source.id,
        "publisher_name": source.publisher_name,
        "new_articles": 0,
        "skipped_duplicates": 0,
        "skipped_expired": 0,
        "uncertain_dates": 0,
        "error": None,
    }
    pending_new_articles = 0
    seen_canonical_urls = set()
    seen_fingerprints = set()

    try:
        feed = await fetch_feed_data(source.rss_url)
        entries = getattr(feed, "entries", [])

        # Preload existing fingerprints and canonical URLs to minimize DB roundtrips
        retention_cutoff = now - timedelta(days=settings.NEWS_RETENTION_DAYS)

        for entry in entries:
            raw_url = entry.get("link") or ""
            if not raw_url:
                continue

            canonical = sanitize_url(raw_url)
            if not canonical:
                continue

            # The session has autoflush disabled, so queries alone do not see
            # candidates staged earlier in this same feed transaction.
            if canonical in seen_canonical_urls:
                result["skipped_duplicates"] += 1
                continue

            headline = entry.get("title") or "Untitled"
            headline = headline.strip()
            if not headline:
                continue

            # Publication date normalization
            published_at = parse_entry_datetime(entry)
            if published_at and published_at > now + timedelta(days=1):
                published_at = None

            date_uncertain = published_at is None
            if date_uncertain:
                result["uncertain_dates"] += 1

            # Safeguard: reject articles that are already older than the 30-day retention window
            if published_at is not None and published_at < retention_cutoff:
                result["skipped_expired"] += 1
                continue

            fingerprint = compute_fingerprint(canonical, headline)

            if fingerprint in seen_fingerprints:
                result["skipped_duplicates"] += 1
                continue

            # Check if canonical URL or fingerprint already exists
            existing_article = db.query(Article).filter(
                (Article.canonical_url == canonical) | (Article.fingerprint == fingerprint)
            ).first()

            if existing_article:
                result["skipped_duplicates"] += 1
                continue

            # Check duplicate_fingerprints table
            existing_fp = db.query(DuplicateFingerprint).filter(
                DuplicateFingerprint.fingerprint == fingerprint
            ).first()

            if existing_fp:
                result["skipped_duplicates"] += 1
                continue

            # RapidFuzz near-duplicate check against recent articles from the same publisher
            from backend.app.services.deduplication.matcher import find_near_duplicate
            near_dup = (
                find_near_duplicate(headline, source.id, db, published_at)
                if published_at is not None else None
            )
            if near_dup:
                result["skipped_duplicates"] += 1
                continue

            # Description snippet
            raw_summary = entry.get("summary") or entry.get("description") or ""
            cleaned_desc = clean_html_summary(raw_summary)

            # Expiration date (30 days from publication)
            expires_at = (published_at or now) + timedelta(days=settings.NEWS_RETENTION_DAYS)

            # Political news classification
            from backend.app.services.classifier.rules import classify_article
            feed_category_hint = entry.get("category")
            category, score = classify_article(headline, cleaned_desc, feed_category_hint)

            # Create Article
            article = Article(
                source_id=source.id,
                headline=headline[:512],
                description=cleaned_desc,
                original_url=raw_url[:1024],
                canonical_url=canonical[:1024],
                category=category,
                classification_score=score,
                published_at=published_at,
                collected_at=now,
                expires_at=expires_at,
                fingerprint=fingerprint,
                status="DATE_REVIEW" if date_uncertain else "ACTIVE",
            )
            db.add(article)

            # Record duplicate fingerprint with 90-day retention
            fp_record = DuplicateFingerprint(
                fingerprint=fingerprint,
                first_seen_at=now,
                expires_at=now + timedelta(days=settings.FINGERPRINT_RETENTION_DAYS),
            )
            db.add(fp_record)
            seen_canonical_urls.add(canonical)
            seen_fingerprints.add(fingerprint)
            pending_new_articles += 1

        source.last_success = now
        source.last_checked = now
        source.status = "ACTIVE"
        source.error_message = None
        db.commit()
        # Report only rows whose transaction has committed.
        result["new_articles"] = pending_new_articles

    except Exception as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            error_msg = "IntegrityError: feed batch conflicted with existing records; transaction rolled back"
        else:
            error_msg = f"{type(exc).__name__}: feed fetch or processing failed"
        logger.warning("Error fetching feed for source #%s (%s): %s", source.id, source.publisher_name, type(exc).__name__)
        # Persist the check time separately from the failed article transaction;
        # last_success remains unchanged because the transaction was rolled back.
        source.last_checked = now
        source.status = "ERROR"
        source.error_message = error_msg
        result["error"] = error_msg
        try:
            db.commit()
        except Exception:
            db.rollback()

    return result


def run_collection(db: Optional[Session] = None, source_id: Optional[int] = None) -> dict:
    """Synchronous entry point called by scheduler or API to trigger news collection."""
    started_at = datetime.now(timezone.utc)
    close_db_when_done = False

    if db is None:
        db = SessionLocal()
        close_db_when_done = True

    overall_result = {
        "started_at": started_at.isoformat(),
        "sources_processed": 0,
        "new_articles": 0,
        "skipped_duplicates": 0,
        "skipped_expired": 0,
        "uncertain_dates": 0,
        "errors": [],
    }

    try:
        query = db.query(NewsSource)
        if source_id is not None:
            query = query.filter(NewsSource.id == source_id)
        else:
            query = query.filter(NewsSource.enabled == True)  # noqa: E712

        sources = query.all()
        overall_result["sources_processed"] = len(sources)

        for source in sources:
            # Run async fetch synchronously in runner context
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(collect_from_source(source, db))
                loop.close()
            except Exception as e:
                res = {"source_id": source.id, "error": str(e), "new_articles": 0, "skipped_duplicates": 0, "skipped_expired": 0, "uncertain_dates": 0}

            overall_result["new_articles"] += res["new_articles"]
            overall_result["skipped_duplicates"] += res["skipped_duplicates"]
            overall_result["skipped_expired"] += res["skipped_expired"]
            overall_result["uncertain_dates"] += res.get("uncertain_dates", 0)
            if res.get("error"):
                overall_result["errors"].append({
                    "source_id": source.id,
                    "publisher": source.publisher_name,
                    "error": res["error"],
                })

        # Record outcome in JobLog
        log_entry = JobLog(
            job_name="news_collection",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status="SUCCESS" if not overall_result["errors"] else "PARTIAL",
            error_message=f"{len(overall_result['errors'])} errors out of {len(sources)} sources" if overall_result["errors"] else None,
        )
        db.add(log_entry)
        db.commit()

    except Exception as exc:
        logger.error("News collection pipeline failed: %s", exc, exc_info=True)
        db.rollback()
        overall_result["errors"].append({"pipeline_error": str(exc)})
    finally:
        if close_db_when_done:
            db.close()

    logger.info(
        "News collection finished: %d new articles, %d duplicates skipped, %d expired skipped, %d errors.",
        overall_result["new_articles"],
        overall_result["skipped_duplicates"],
        overall_result["skipped_expired"],
        len(overall_result["errors"]),
    )
    return overall_result
