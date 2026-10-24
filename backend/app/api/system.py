"""
PoliBrief Backend — System / Health API Router
"""
import platform
import shutil
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models import Administrator, Article, NewsSource, PostDraft, PublishedPost

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    """Public health check."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/scheduler-status")
def scheduler_status(_: Administrator = Depends(get_current_admin)):
    """Return the actual in-process scheduler state and next scheduled runs."""
    from backend.app.jobs.scheduler import get_scheduler_status
    return get_scheduler_status()


@router.get("/dashboard-stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: Administrator = Depends(get_current_admin),
):
    """Aggregated statistics for the dashboard overview."""
    from datetime import date, timedelta

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_active = db.query(Article).filter(Article.status == "ACTIVE").count()
    collected_today = (
        db.query(Article)
        .filter(Article.collected_at >= today_start, Article.status == "ACTIVE")
        .count()
    )
    draft_count = db.query(PostDraft).filter(PostDraft.status.in_(["DRAFT", "READY_FOR_REVIEW"])).count()
    approved_count = db.query(PostDraft).filter(PostDraft.status == "APPROVED").count()
    published_count = db.query(PublishedPost).count()
    active_sources = db.query(NewsSource).filter(NewsSource.enabled == True).count()

    # Last successful fetch across all sources
    last_fetch = (
        db.query(NewsSource.last_success)
        .filter(NewsSource.last_success.isnot(None))
        .order_by(NewsSource.last_success.desc())
        .first()
    )
    last_fetch_time = last_fetch[0].isoformat() if last_fetch and last_fetch[0] else None

    # Storage usage
    storage_path = settings.storage_base
    total, used, free = shutil.disk_usage(storage_path) if storage_path.exists() else (0, 0, 0)

    return {
        "total_active_articles": total_active,
        "articles_collected_today": collected_today,
        "draft_posts": draft_count,
        "approved_posts": approved_count,
        "published_posts": published_count,
        "active_sources": active_sources,
        "last_successful_fetch": last_fetch_time,
        "storage_used_mb": round(used / 1024 / 1024, 2),
        "storage_free_mb": round(free / 1024 / 1024, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/cleanup")
def trigger_cleanup(
    db: Session = Depends(get_db),
    _: Administrator = Depends(get_current_admin),
):
    """Trigger manual 30-day rolling retention cleanup and disk page reclamation."""
    from backend.app.services.cleanup.retention import run_cleanup
    result = run_cleanup(db=db)
    return {
        "detail": "Retention cleanup completed successfully.",
        "result": result,
    }


@router.get("/storage-stats")
def storage_stats(
    db: Session = Depends(get_db),
    _: Administrator = Depends(get_current_admin),
):
    """Detailed breakdown of local storage files and expiring article counts."""
    import os

    def get_dir_size(path):
        total = 0
        if path.exists():
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        return total

    db_size = settings.db_path.stat().st_size if settings.db_path.exists() else 0
    images_size = get_dir_size(settings.generated_images_dir)
    logs_size = get_dir_size(settings.logs_dir)
    templates_size = get_dir_size(settings.templates_dir)

    now = datetime.now(timezone.utc)
    expiring_soon_count = (
        db.query(Article)
        .filter(Article.expires_at <= now + timedelta(days=3), Article.status == "ACTIVE")
        .count()
    )

    return {
        "database_size_bytes": db_size,
        "database_size_mb": round(db_size / (1024 * 1024), 2),
        "generated_images_size_bytes": images_size,
        "generated_images_size_mb": round(images_size / (1024 * 1024), 2),
        "logs_size_bytes": logs_size,
        "logs_size_mb": round(logs_size / (1024 * 1024), 2),
        "templates_size_bytes": templates_size,
        "total_managed_mb": round((db_size + images_size + logs_size + templates_size) / (1024 * 1024), 2),
        "retention_policy_days": settings.NEWS_RETENTION_DAYS,
        "fingerprint_retention_days": settings.FINGERPRINT_RETENTION_DAYS,
        "publication_history_retention_days": settings.PUBLICATION_HISTORY_RETENTION_DAYS,
        "log_retention_days": settings.LOG_RETENTION_DAYS,
        "articles_expiring_within_72h": expiring_soon_count,
    }


@router.get("/logs")
def get_job_logs(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: Administrator = Depends(get_current_admin),
):
    """Get recent operational scheduler execution logs."""
    from backend.app.models import JobLog
    logs = (
        db.query(JobLog)
        .order_by(JobLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "job_name": l.job_name,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "finished_at": l.finished_at.isoformat() if l.finished_at else None,
            "status": l.status,
            "error_message": l.error_message,
        }
        for l in logs
    ]


@router.post("/shutdown")
def request_shutdown(_: Administrator = Depends(get_current_admin)):
    """Signal the application to shut down gracefully."""
    import signal
    from threading import Timer

    # Uvicorn handles SIGINT by setting should_exit, allowing its lifespan
    # shutdown path to drain the scheduler and dispose the database engine.
    # Delay slightly so this HTTP response can be returned to the caller first.
    shutdown_signal = Timer(0.5, signal.raise_signal, args=(signal.SIGINT,))
    shutdown_signal.daemon = True
    shutdown_signal.start()
    return {"detail": "Shutdown signal sent."}
