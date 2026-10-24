# PoliBrief V1 — Project Status

**Last Updated:** 2026-10-24
**Overall Status:** Stages 1–3 corrections complete — 111/111 isolated backend tests pass; frontend production build succeeds. No live Meta integration test or screenshot review was performed.

---

## Phase Summary

| Phase | Status | Tests | Evidence |
|---|---|---|---|
| Phase 1 — Foundation, Auth, Lifecycle | COMPLETE | 36/36 pass | backend/tests/test_phase1.py |
| Phase 2 — News Sources & RSS Collection | COMPLETE | 21/21 pass | backend/tests/test_phase2.py |
| Phase 3 — Classification, Deduplication, Retention | COMPLETE | 18/18 pass | backend/tests/test_phase3.py |
| Phase 4 — Pillow Post Studio, Captions, Drafts | COMPLETE | 21/21 pass | backend/tests/test_phase4.py |
| Phase 5 — Meta Graph API Publishing | COMPLETE | 10/10 pass | backend/tests/test_phase5.py |
| Stage 1 — Security and publishing corrections | COMPLETE | 1/1 pass | backend/tests/test_stage1_security.py |
| Stage 2 — Storage and runtime corrections | COMPLETE | 4/4 pass | backend/tests/test_stage2_runtime.py |
| Stage 3 — UI, functionality and quality corrections | COMPLETE | 8 added tests; 111 total pass | frontend build; backend/tests |
| Phase 6 — Integration, Polish, Documentation | COMPLETE | build clean | README.md, PROJECT_STATUS.md |

---

## Implemented Features

### Phase 1 — Foundation
- SQLite schema: Administrator, NewsSource, Article, PostDraft, PublishedPost, DuplicateFingerprint, JobLog, ApplicationSetting
- Argon2id password hashing, signed JWT in HTTP-only cookies (pb_access_token)
- Login rate limiting (5 attempts per 15 minutes per IP)
- SQLite WAL mode and PRAGMA foreign_keys=ON
- System endpoints: /api/system/health, /api/system/dashboard-stats, /api/system/shutdown
- Windows launcher: scripts/start.ps1 (starts both processes, Ctrl+C to stop both)
- Files: backend/app/models/__init__.py, backend/app/auth/service.py, backend/app/api/auth.py, backend/app/database/session.py, backend/app/api/system.py, scripts/start.ps1

### Phase 2 — News Collection
- RSS parser with feedparser + httpx, bounded streaming/retries, tracking parameter stripper, UTC date normalization, DNS-pinned SSRF protection and redirect validation
- Sources API CRUD with live feed URL testing and default political source seeding (NPR, PBS, BBC)
- Articles API with pagination, keyword search, category, publication-date, and status filters
- APScheduler news collection every 30 minutes
- Files: backend/app/services/collector/rss.py, backend/app/api/sources.py, backend/app/api/articles.py, backend/app/schemas/source.py, backend/app/schemas/article.py, frontend/src/pages/SourcesPage.jsx, frontend/src/pages/NewsFeedPage.jsx

### Phase 3 — Intelligence & Retention
- Rule-based weighted political classifier (7 categories) in backend/app/services/classifier/rules.py
- RapidFuzz near-duplicate matching: 85% same-source, 70% cross-publisher in backend/app/services/deduplication/matcher.py
- 30-day article retention with draft safeguards; 90-day fingerprint and publication-history retention; 90-day completed-draft lifecycle; stale nonterminal draft review flags; 30-day log purge; safe orphaned-image cleanup; SQLite PRAGMA maintenance in backend/app/services/cleanup/retention.py
- Frontend: SettingsPage.jsx with storage stats, retention trigger, scheduler logs, exit modal

### Phase 4 — Post Studio
- Pillow 1080x1080 PNG generator: 3 templates (modern, breaking, minimal) with pixel-measured headline wrapping and dynamic font fitting in backend/app/services/graphics/generator.py
- Facebook caption generator in backend/app/services/captions/generator.py
- Post Drafts API with full state machine (DRAFT/READY_FOR_REVIEW/APPROVED/PUBLISHING/PUBLISHED/FAILED/CANCELLED) in backend/app/api/drafts.py
- Frontend: PostStudioPage.jsx (two-column editor with Facebook mockup), DraftsPage.jsx (approval grid + manual export modal)

### Phase 5 — Meta Graph API Publishing
- Meta Graph API v21.0 client with page validation and multipart photo publishing in backend/app/services/publishing/meta.py
- Publishing API enforcing approved-only publishing, duplicate prevention (409 Conflict), and audit logging in backend/app/api/publishing.py
- Frontend: PublishedPostsPage.jsx with Meta status indicator, audit table, and Facebook post links

### Phase 6 — Integration & Documentation
- DashboardPage.jsx: clickable stat cards (navigate to relevant page), Quick Workflows action bar, full onNavigate integration
- README.md: complete user and developer documentation
- PROJECT_STATUS.md: this file

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, Uvicorn |
| ORM / DB | SQLAlchemy 2.0, SQLite (WAL mode) |
| Auth | Argon2id (argon2-cffi), python-jose JWT |
| RSS Ingestion | feedparser 6.0, httpx 0.28 |
| Classification | Rule-based weighted Python, RapidFuzz 3.10 |
| Image Generation | Pillow 11.0 |
| Scheduling | APScheduler 3.10 |
| Frontend | React 18, Vite 8, Vanilla CSS |
| Icons | lucide-react |
| HTTP Client | Axios (frontend), httpx (backend) |
| Testing | pytest 8.3, pytest-asyncio |

---

## Commands

### Launch application

```powershell
.\scripts\start.ps1
```

### Manual launch (development)

```powershell
# Backend (Terminal 1)
backend\venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (Terminal 2)
npm run dev --prefix frontend
```

### Run all tests

```powershell
backend\venv\Scripts\python -m pytest backend\tests\ -v
```

### Build frontend (production)

```powershell
npm run build --prefix frontend
```

---

## Known Issues

1. python-jose uses `datetime.utcnow()` internally (deprecation warning in Python 3.12). No functional impact.
2. Starlette TestClient BlockingPortal deprecation warning from anyio. No functional impact.
3. Meta Graph API integration requires live credentials for full end-to-end testing. All automated tests use mocked responses; no live publishing verification was performed.
4. Stale nonterminal drafts are flagged in operational logs, which follow the 30-day log retention policy. Draft records and their article/image references remain protected until an administrator resolves them.

## Stage 2 Manual Verification

These production-facing checks are documented for the administrator and were not run during isolated development.

- Review quarantined missing-date entries in News Feed’s Date review queue; clearing the flag leaves their date visibly unverified.
- Trigger Settings → Manual Cleanup against a disposable copy of the database and confirm old completed drafts and publication records age out while active or unresolved drafts remain.
- Exit PoliBrief using the Settings exit control and Ctrl+C launcher path; confirm the backend logs its lifespan shutdown and no launcher-owned Node.js or Python process remains.
- Test RSS sources with a public feed and with a redirect to localhost/private space; the latter should fail without making a request to the private destination.

## Stage 3 — UI, Functionality and Quality Corrections

- Corrected Post Studio’s desktop grid to use fractional columns that account for the grid gap and added minimum-width guards.
- Replaced state-only navigation with URL-backed routing so article selection restores across navigation; the selected article remains available in the Studio selector.
- Connected scheduler status to the authenticated API and applied actual running/stopped/unavailable states in the shell and Dashboard.
- Dashboard now requests only four drafts and treats partial data failures as visible load errors with retry.
- Added publication-date filtering and a DATE_REVIEW queue. Clearing the review flag keeps the article explicitly marked as date-unverified.
- Pillow now wraps headlines by measured pixel width and dynamically fits the complete headline to the template area. Unknown dates render as “DATE UNVERIFIED”.
- Removed unsupported “verified” and “non-partisan” graphic claims; Studio shows source usage notes and related coverage from other publishers.
- Added keyboard-operable template and Dashboard controls, visible keyboard focus, password-toggle tab access, and dialog semantics.
- Added retryable load/preview feedback to the editorial pages. Updated README and retention text to match implemented behavior.
- Removed the unreferenced Vite starter entry, stylesheet, images, SVGs, and TypeScript-only build dependency; frontend build now uses Vite directly.

### Stage 3 Validation

- Full isolated backend suite: 111 passed.
- Frontend production build: passed using local dependencies.
- Visual screenshot review and live Meta publishing were not performed.
- No database migration or production cleanup was run; all tests use in-memory SQLite and temporary image folders.

---

## External Integrations Requiring Manual Verification

- **Live RSS feeds:** Requires internet. Test via News Sources -> Test Feed.
- **Meta Graph API publishing:** Requires FACEBOOK_PAGE_ACCESS_TOKEN in .env with pages_manage_posts permission.
- **Facebook Page connection:** Requires configured Meta App and valid Page credentials.

---

## Architecture Decisions

1. **StaticPool for tests:** In-memory SQLite requires StaticPool to share the same connection across fixtures.
2. **Rate limiter reset in tests:** _login_attempts dict cleared in conftest.py fixture teardown to prevent 429 false failures.
3. **APScheduler timedelta:** Use timedelta(seconds=N) not replace(second=...) to avoid ValueError when current second >= 55.
4. **Duplicate publish check order:** Check existing PublishedPost BEFORE checking APPROVED status to return 409 not 400.
5. **Draft protects expired article:** Retention engine skips deletion of articles linked to active PostDraft records.
6. **Inline SVG Facebook icon:** lucide-react does not export Facebook icon; use inline SVG.

---

## HANDOVER TO NEXT AI ASSISTANT

**Status when handed over:** Stages 1–3 corrections complete; 111 isolated backend tests pass. Frontend production build succeeds. Production-facing and screenshot checks remain listed above.

**What is done:**
- The five implementation phases and Stages 1–3 corrections are complete and tested.
- Phase 6 documentation is complete (README.md, PROJECT_STATUS.md).
- DashboardPage.jsx has been enhanced with clickable stat cards and Quick Workflows navigation.
- The previous session introduced a JSX parse error (orphaned closing tags) in DashboardPage.jsx at lines 220-222 which has been fixed.

**What requires manual setup before first real use:**
1. Copy .env.example to .env and set SECRET_KEY.
2. Run: python -m venv backend\venv && backend\venv\Scripts\pip install -r backend\requirements.txt
3. Run: npm install --prefix frontend
4. Configure FACEBOOK_PAGE_ACCESS_TOKEN if Meta publishing is needed.

**Key files:**
- backend/app/main.py — FastAPI app entry point, router registration
- backend/app/models/__init__.py — All SQLAlchemy models
- backend/app/core/config.py — All settings (pydantic-settings, reads .env)
- backend/app/jobs/scheduler.py — APScheduler setup
- backend/app/services/publishing/meta.py — Meta Graph API client
- backend/app/api/publishing.py — Publishing API with approval enforcement
- frontend/src/App.jsx — React router and page registry
- frontend/src/services/api.js — All Axios API calls
- scripts/start.ps1 — Windows launcher

**Do NOT:**
- Recreate or overwrite working backend modules.
- Change the database schema without an Alembic migration.
- Expose credentials in any file.
- Modify the Meta API client to bypass approval checks.

**Next possible tasks (V2 scope):**
- Alembic migration system for schema changes
- scikit-learn or local LLM classifier upgrade
- Multiple social media platform support
- Playwright end-to-end browser tests
- 1200x630 landscape image template
