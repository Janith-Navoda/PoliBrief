"""
PoliBrief Backend — FastAPI Application Entry Point
"""
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.app.core.config import settings
from backend.app.core.logging_config import setup_logging
from backend.app.database.session import init_db

# Initialise logging immediately
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup → yield → shutdown."""
    logger.info("=" * 60)
    logger.info("PoliBrief V1 — Starting up")
    logger.info("=" * 60)

    # Ensure storage directories exist
    for directory in [
        settings.storage_base,
        settings.generated_images_dir,
        settings.templates_dir,
        settings.logs_dir,
        settings.db_path.parent,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    # Initialise database
    init_db()
    logger.info("Database initialised at: %s", settings.db_path)

    # Start the scheduler (Phase 2+)
    from backend.app.jobs.scheduler import start_scheduler
    start_scheduler()

    logger.info("PoliBrief V1 ready — http://%s:%s", settings.APP_HOST, settings.APP_PORT)

    try:
        yield  # ──── Application is running ────
    finally:
        logger.info("PoliBrief V1 — Shutting down")
        from backend.app.jobs.scheduler import stop_scheduler
        stop_scheduler()
        from backend.app.database import session as session_module
        session_module.engine.dispose()
        logger.info("PoliBrief V1 — Shutdown complete")


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="PoliBrief API",
    description="Private political news aggregation and Facebook post management system.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

# Restrict to localhost only (testclient is allowed for automated tests)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", settings.APP_HOST, "testclient", "testserver"],
)

# CORS — allow only the Vite dev server and local production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

from backend.app.api.auth import router as auth_router
from backend.app.api.system import router as system_router

app.include_router(auth_router, prefix="/api")
app.include_router(system_router, prefix="/api")

from backend.app.api.sources import router as sources_router
from backend.app.api.articles import router as articles_router

app.include_router(sources_router, prefix="/api")
app.include_router(articles_router, prefix="/api")

from backend.app.api.drafts import router as drafts_router

app.include_router(drafts_router, prefix="/api")

from backend.app.api.publishing import router as publishing_router

app.include_router(publishing_router, prefix="/api")


@app.get("/api")
def api_root():
    return {"name": "PoliBrief API", "version": "1.0.0", "status": "running"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}
