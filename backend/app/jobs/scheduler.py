"""
PoliBrief Backend — In-Process APScheduler Scheduler
Phase 1: scaffold with cleanup and collection job stubs.
Phase 2+ will fill in real collection logic.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": ThreadPoolExecutor(max_workers=4)}
        job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 60}
        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )
    return _scheduler


def start_scheduler() -> None:
    sched = _get_scheduler()
    if sched.running:
        return

    from datetime import timedelta

    # ── Startup cleanup (runs once after 5 seconds) ──
    sched.add_job(
        _run_cleanup,
        trigger="date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=5),
        id="startup_cleanup",
        name="Startup Cleanup",
        replace_existing=True,
    )

    # ── Daily cleanup ──
    sched.add_job(
        _run_cleanup,
        trigger="interval",
        hours=24,
        id="daily_cleanup",
        name="Daily Cleanup",
        replace_existing=True,
    )

    # ── News collection every 30 minutes ──
    sched.add_job(
        _run_collection,
        trigger="interval",
        minutes=settings.COLLECTION_INTERVAL_MINUTES,
        id="news_collection",
        name="News Collection",
        replace_existing=True,
    )

    # ── Immediate collection on startup (after 10 seconds) ──
    sched.add_job(
        _run_collection,
        trigger="date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=10),
        id="startup_collection",
        name="Startup Collection",
        replace_existing=True,
    )

    sched.start()
    logger.info("Scheduler started. Collection every %d min.", settings.COLLECTION_INTERVAL_MINUTES)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        # Stop scheduling new work, then wait for bounded HTTP/DB jobs to finish
        # before the application disposes its database connections.
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped.")
    _scheduler = None


# ─── Job implementations (stubs — filled in Phase 2/3) ───────────────────────

def _run_cleanup() -> None:
    """Stub: expanded in Phase 3 with full retention logic."""
    logger.info("[Scheduler] Running retention cleanup…")
    try:
        from backend.app.services.cleanup.retention import run_cleanup
        run_cleanup()
    except Exception as exc:
        logger.error("[Scheduler] Cleanup error: %s", exc, exc_info=True)


def _run_collection() -> None:
    """Stub: expanded in Phase 2 with real RSS collection."""
    logger.info("[Scheduler] Running news collection…")
    try:
        from backend.app.services.collector.runner import run_collection
        run_collection()
    except ImportError:
        logger.debug("[Scheduler] Collector not yet implemented — skipping.")
    except Exception as exc:
        logger.error("[Scheduler] Collection error: %s", exc, exc_info=True)


def get_scheduler_status() -> dict:
    sched = _get_scheduler()
    jobs = []
    if sched.running:
        for job in sched.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            })
    return {"running": sched.running, "jobs": jobs}
