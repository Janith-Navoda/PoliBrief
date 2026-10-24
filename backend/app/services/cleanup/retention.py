"""
PoliBrief Backend — 30-Day Rolling News Retention & Storage Cleanup Service
Enforces the mandatory 30-day retention lifecycle:
  - Deletes expired news articles while safeguarding active editorial drafts.
  - Deletes expired duplicate fingerprints (90 days).
  - Prunes operational job logs older than 30 days.
  - Safely cleans orphaned temporary/generated images.
  - Reclaims SQLite database pages.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models import Article, DuplicateFingerprint, JobLog, PostDraft, PublishedPost

logger = logging.getLogger(__name__)


def purge_expired_articles(db: Session, now: datetime) -> int:
    """
    Delete articles whose publication age exceeds the 30-day retention limit,
    UNLESS the article is linked to an active editorial draft or published post.
    """
    cutoff = now - timedelta(days=settings.NEWS_RETENTION_DAYS)

    # Every remaining draft reference protects its source article. Completed
    # drafts are removed only by their own 90-day lifecycle below.
    protected_article_ids = {
        row[0] for row in db.query(PostDraft.article_id).distinct().all() if row[0] is not None
    }

    # Query expired articles
    expired_query = db.query(Article).filter(
        (Article.expires_at <= now) | (Article.published_at < cutoff)
    )

    if protected_article_ids:
        expired_query = expired_query.filter(~Article.id.in_(protected_article_ids))

    expired_articles = expired_query.all()
    count = len(expired_articles)

    if count > 0:
        for article in expired_articles:
            db.delete(article)
        db.commit()
        logger.info("[Retention] Purged %d expired articles older than 30 days.", count)

    return count


def purge_expired_publications(db: Session, now: datetime) -> int:
    """Keep minimal local publication history for 90 days; never call Meta."""
    cutoff = now - timedelta(days=settings.PUBLICATION_HISTORY_RETENTION_DAYS)
    expired = db.query(PublishedPost).filter(PublishedPost.published_at < cutoff).all()
    count = len(expired)
    for record in expired:
        db.delete(record)
    if count:
        db.commit()
        logger.info("[Retention] Purged %d local publication records older than 90 days.", count)
    return count


def purge_completed_drafts(db: Session, now: datetime) -> int:
    """Remove only old terminal drafts after their publication history expires."""
    cutoff = now - timedelta(days=settings.PUBLICATION_HISTORY_RETENTION_DAYS)
    completed = db.query(PostDraft).filter(
        PostDraft.status.in_(("PUBLISHED", "CANCELLED")),
        PostDraft.updated_at < cutoff,
        ~PostDraft.publications.any(),
    ).all()
    count = len(completed)
    for draft in completed:
        db.delete(draft)
    if count:
        db.commit()
        logger.info("[Retention] Purged %d completed drafts older than 90 days.", count)
    return count


def flag_stale_drafts_for_review(db: Session, now: datetime) -> int:
    """Log IDs of stale nonterminal drafts for admin review without changing or deleting them."""
    cutoff = now - timedelta(days=settings.PUBLICATION_HISTORY_RETENTION_DAYS)
    unresolved_statuses = ("DRAFT", "READY_FOR_REVIEW", "APPROVED", "FAILED", "PUBLISHING")
    draft_ids = [row[0] for row in db.query(PostDraft.id).filter(
        PostDraft.status.in_(unresolved_statuses),
        PostDraft.updated_at < cutoff,
    ).order_by(PostDraft.id).all()]
    if draft_ids:
        db.add(JobLog(
            job_name="draft_retention_review",
            started_at=now,
            finished_at=now,
            status="REVIEW_REQUIRED",
            error_message="Stale drafts preserved for administrator review; IDs: " + ", ".join(map(str, draft_ids)),
        ))
        db.commit()
    return len(draft_ids)


def purge_expired_fingerprints(db: Session, now: datetime) -> int:
    """Delete duplicate fingerprints that have passed their 90-day retention window."""
    expired_fps = db.query(DuplicateFingerprint).filter(DuplicateFingerprint.expires_at <= now).all()
    count = len(expired_fps)
    if count > 0:
        for fp in expired_fps:
            db.delete(fp)
        db.commit()
        logger.info("[Retention] Purged %d duplicate fingerprints older than 90 days.", count)
    return count


def purge_expired_job_logs(db: Session, now: datetime) -> int:
    """Retain operational job logs for 30 days; prune older entries."""
    cutoff = now - timedelta(days=settings.LOG_RETENTION_DAYS)
    old_logs = db.query(JobLog).filter(JobLog.started_at < cutoff).all()
    count = len(old_logs)
    if count > 0:
        for log_entry in old_logs:
            db.delete(log_entry)
        db.commit()
        logger.info("[Retention] Purged %d operational job logs older than 30 days.", count)
    return count


def clean_orphaned_images(db: Session, now: datetime) -> int:
    """
    Scan generated images directory and remove image files that:
      1. Are NOT referenced by any PostDraft in the database, AND
      2. Were created more than 2 hours ago (prevent race condition with in-progress post creation).
    """
    images_dir = settings.generated_images_dir
    if not images_dir.exists():
        return 0

    # Existing draft references, including protected or not-yet-expired terminal
    # drafts, keep their images. Expired completed records are purged first.
    active_paths = {
        str(Path(row[0]).resolve()) for row in db.query(PostDraft.image_path).all() if row[0]
    }

    deleted_count = 0
    age_threshold = now - timedelta(hours=2)

    try:
        for entry in os.scandir(images_dir):
            if entry.is_file() and entry.name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                entry_path = str(Path(entry.path).resolve())
                if entry_path not in active_paths:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
                    if mtime < age_threshold:
                        try:
                            os.remove(entry.path)
                            deleted_count += 1
                        except OSError as e:
                            logger.warning("[Retention] Could not remove orphaned file %s: %s", entry.path, e)
    except Exception as exc:
        logger.warning("[Retention] Error scanning image directory: %s", exc)

    if deleted_count > 0:
        logger.info("[Retention] Cleaned up %d orphaned generated image files.", deleted_count)
    return deleted_count


def reclaim_sqlite_storage(db: Session) -> None:
    """Run SQLite incremental vacuum / optimize pragmas safely."""
    try:
        db.execute(text("PRAGMA optimize"))
        db.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
        db.commit()
    except Exception as exc:
        logger.debug("[Retention] Pragmas maintenance note: %s", exc)


def run_cleanup(db: Optional[Session] = None, now: Optional[datetime] = None) -> dict:
    """
    Execute the full 30-day retention and storage cleanup cycle.
    Idempotent and safe to run multiple times per day.
    """
    started_at = now or datetime.now(timezone.utc)
    close_db_when_done = False

    if db is None:
        db = SessionLocal()
        close_db_when_done = True

    result = {
        "started_at": started_at.isoformat(),
        "articles_deleted": 0,
        "images_deleted": 0,
        "fingerprints_deleted": 0,
        "publications_deleted": 0,
        "completed_drafts_deleted": 0,
        "drafts_flagged_for_review": 0,
        "logs_deleted": 0,
        "errors": [],
    }

    try:
        result["publications_deleted"] = purge_expired_publications(db, started_at)
        result["completed_drafts_deleted"] = purge_completed_drafts(db, started_at)
        result["articles_deleted"] = purge_expired_articles(db, started_at)
        result["fingerprints_deleted"] = purge_expired_fingerprints(db, started_at)
        result["logs_deleted"] = purge_expired_job_logs(db, started_at)
        result["drafts_flagged_for_review"] = flag_stale_drafts_for_review(db, started_at)
        result["images_deleted"] = clean_orphaned_images(db, started_at)
        reclaim_sqlite_storage(db)

        # Record cleanup in job_logs
        log_entry = JobLog(
            job_name="retention_cleanup",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status="SUCCESS",
            error_message=None,
        )
        db.add(log_entry)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error("[Retention] Cleanup pipeline encountered an error: %s", exc, exc_info=True)
        result["errors"].append(str(exc))
        try:
            err_log = JobLog(
                job_name="retention_cleanup",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status="FAILED",
                error_message=str(exc)[:500],
            )
            db.add(err_log)
            db.commit()
        except Exception:
            pass
    finally:
        if close_db_when_done:
            db.close()

    finished_at = datetime.now(timezone.utc)
    duration = (finished_at - started_at).total_seconds()
    logger.info(
        "[Retention] Complete in %.2fs: %d articles, %d fingerprints, %d logs, %d images purged.",
        duration,
        result["articles_deleted"],
        result["fingerprints_deleted"],
        result["logs_deleted"],
        result["images_deleted"],
    )
    return result
