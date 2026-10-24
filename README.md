# PoliBrief V1

**Private Political News Aggregation & Facebook Post Management System**

A locally hosted, single-administrator application that automatically collects political news from RSS feeds, classifies articles, generates branded 1080x1080 social media images with Pillow, and publishes approved posts to Facebook via the official Meta Graph API.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration Guide](#configuration-guide)
5. [Launch and Shutdown](#launch-and-shutdown)
6. [Running Tests](#running-tests)
7. [User Guide](#user-guide)
8. [Meta Facebook Integration](#meta-facebook-integration)
9. [Project Structure](#project-structure)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

PoliBrief is a **modular monolith** with a clear data flow:

    RSS Feeds / Permitted APIs
            |
      News Collector (feedparser + httpx)
            |
      Data Cleaning & Normalization (UTC dates, URL sanitization)
            |
      Political Classifier (rule-based, weighted keywords)
            |
      Duplicate Detector (RapidFuzz, URL fingerprints)
            |
      SQLite Database  <--- 30-Day Rolling Retention ---> Storage Cleanup
            |
      Private Admin Dashboard (React + Vite)
            |
      Post Studio (Pillow 1080x1080 image + caption generator)
            |
      Draft Review & Approval Workflow
            |
      Facebook Publishing (Meta Graph API v21.0) OR Manual Export

**Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, APScheduler
**Frontend:** React, Vite, Tailwind CSS
**Image Engine:** Pillow (3 templates: Modern, Breaking News, Minimal Editorial)
**Publishing:** Meta Graph API v21.0 with offline manual export fallback

---

## Prerequisites

| Requirement | Minimum version | Check command |
|---|---|---|
| Python | 3.11+ | python --version |
| Node.js | 20.19+ or 22.12+ | node --version |
| npm | 9+ | npm --version |
| Git | Any | git --version |

All other dependencies install into the project virtual environment.

---

## Quick Start

### 1. Create the virtual environment

```powershell
python -m venv backend\venv
backend\venv\Scripts\pip install -r backend\requirements.txt
```

### 2. Install frontend dependencies

```powershell
npm install --prefix frontend
```

### 3. Configure environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a strong SECRET_KEY:

```
SECRET_KEY=
```

Set a private value of at least 32 characters. You can generate one yourself with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Keep the same value across restarts; changing it invalidates existing login sessions. PoliBrief will not generate or replace this key automatically.

### 4. Launch PoliBrief

```powershell
.\scripts\start.ps1
```

The script starts both backend (port 8000) and frontend (port 5173) and opens your browser.

### 5. First login

On first launch you will be prompted to create the administrator account. Use a password of at least 12 characters.

---

## Configuration Guide

All configuration lives in `.env`. See `.env.example` for all available variables.

### Core settings

| Variable | Default | Description |
|---|---|---|
| SECRET_KEY | (required) | Stable private value of at least 32 characters used for JWT signing |
| APP_ENV | development | Set to production to hide /api/docs |
| APP_HOST | 127.0.0.1 | Localhost-only binding |
| APP_PORT | 8000 | Backend port |
| FRONTEND_URL | http://localhost:5173 | CORS allow-list entry |

### News Collection and Retention

| Variable | Default | Description |
|---|---|---|
| COLLECTION_INTERVAL_MINUTES | 30 | RSS fetch frequency |
| NEWS_RETENTION_DAYS | 30 | Articles expire after this many days |
| FINGERPRINT_RETENTION_DAYS | 90 | Duplicate fingerprints kept 90 days |
| PUBLICATION_HISTORY_RETENTION_DAYS | 90 | Local publication records and completed drafts kept for 90 days |
| LOG_RETENTION_DAYS | 30 | Job logs purged after 30 days |

Retention runs shortly after startup and daily. Unresolved drafts are retained regardless of age and reported for administrator review. Completed drafts and local publication history become eligible for deletion after 90 days, after expired publication records are removed. Local cleanup never deletes Facebook posts. Articles without a verified publication date are quarantined with status `DATE_REVIEW`; review them in News Feed using the status filter. Clearing the review flag does not make the publication date verified.

### Meta / Facebook (optional)

| Variable | Description |
|---|---|
| META_APP_ID | Meta App ID from developers.facebook.com |
| META_APP_SECRET | Meta App Secret |
| FACEBOOK_PAGE_ID | Numeric ID of the Facebook Page you administer |
| FACEBOOK_PAGE_ACCESS_TOKEN | Page Access Token with pages_manage_posts permission |
| META_API_VERSION | v21.0 |

PoliBrief works fully without Facebook credentials. Only direct API publishing requires them.

---

## Launch and Shutdown

### Start

```powershell
.\scripts\start.ps1
```

### Stop

Press Ctrl+C in the PowerShell window running start.ps1. Both processes are terminated cleanly.

You can also use **Settings -> Exit Application** in the dashboard.

> Closing the browser tab does NOT stop PoliBrief. Always use Ctrl+C or the Exit button.

### Manual development start

```powershell
# Terminal 1 - Backend
backend\venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 - Frontend
npm run dev --prefix frontend
```

---

## Running Tests

```powershell
# All backend tests
backend\venv\Scripts\python -m pytest backend\tests\ -v

# Single phase
backend\venv\Scripts\python -m pytest backend\tests\test_phase5.py -v

# With coverage
backend\venv\Scripts\python -m pytest backend\tests\ --cov=backend\app --cov-report=term-missing
```

### Test results (verified 2026-10-24)

| Phase | Tests | Status |
|---|---|---|
| Phase 1 - Auth & Foundation | 36 | 36 passed |
| Phase 2 - News Collection and RSS safety | 21 | 21 passed |
| Phase 3 - Intelligence and retention | 18 | 18 passed |
| Phase 4 - Post Studio and drafts | 21 | 21 passed |
| Phase 5 - Meta publishing | 10 | 10 passed |
| Stage 1 security configuration | 1 | 1 passed |
| Stage 2 runtime shutdown | 4 | 4 passed |
| **Total** | **111** | **111 passed** |

Phase 5 tests use mocked Meta Graph API responses. No real Facebook posts are created during automated testing.

---

## User Guide

### Dashboard

Live KPIs: active articles, collected today, drafts, approved, published, active sources, storage usage, scheduler status. Stat cards are clickable and navigate to the relevant section.

### News Feed

Browse collected articles. Filter by category, publisher, publication date, or keyword. The Date review queue exposes quarantined items; clearing a review flag returns an item to the active feed while retaining its unverified date label. Create Post is available for active articles.

### Post Studio

1. An article is pre-loaded from News Feed and synchronized with the URL so the selection can be restored after navigation.
2. Choose a template: Modern, Breaking News, or Minimal Editorial.
3. The preview is generated by Pillow as you edit; long headlines are measured against the available image area.
4. Review the auto-generated Facebook caption.
5. Edit headline or caption.
6. Click Save Draft to add to the editorial queue.

### Drafts (Editorial Review)

Shows all drafts. Workflow: DRAFT -> READY_FOR_REVIEW -> APPROVED -> PUBLISHED.

- Approve a draft before publishing.
- Publish to Facebook requires APPROVED status and configured Meta credentials.
- Manual Export: download image, copy caption, post manually, then use Mark as Published.

### Published Posts

Audit table of all published posts with date, Facebook post ID, post link, and publishing method.

### News Sources

Add, edit, enable/disable, or delete RSS sources. Use Seed Defaults to add NPR, PBS, and BBC. Use Test Feed to validate a URL. Use Refresh to trigger an immediate fetch.

### Settings

Collection interval and retention policy status, storage breakdown, manual cleanup, job logs, Facebook connection status, and Exit Application. Environment configuration is managed in `.env`; Settings displays policy state rather than editing those values.

---

## Meta Facebook Integration

### Required permissions

Your Meta App needs:
- pages_manage_posts
- pages_read_engagement

### Generating a Page Access Token

1. Go to Meta for Developers -> Graph API Explorer.
2. Select your Page from the dropdown.
3. Add pages_manage_posts and pages_read_engagement.
4. Generate and exchange for a long-lived token (Access Token Debugger).
5. Set FACEBOOK_PAGE_ACCESS_TOKEN in .env.

### Checking the connection

Navigate to Settings in PoliBrief - the Facebook Integration card shows connection status.

### Manual export fallback

Without Meta credentials, use the Drafts page to:
1. Download Image (1080x1080 PNG)
2. Copy Caption
3. Open Facebook Page
4. After manual posting, click Mark as Published and paste the post URL.

---

## Project Structure

```
PoliBrief/
+-- backend/
|   +-- app/
|   |   +-- api/               # FastAPI routers
|   |   +-- auth/              # Argon2id, JWT, session
|   |   +-- core/              # Settings, logging
|   |   +-- database/          # SQLAlchemy session
|   |   +-- jobs/              # APScheduler
|   |   +-- models/            # ORM models (7 tables)
|   |   +-- schemas/           # Pydantic schemas
|   |   +-- services/
|   |       +-- captions/      # Caption generator
|   |       +-- classifier/    # Political classifier
|   |       +-- cleanup/       # 30-day retention
|   |       +-- collector/     # RSS ingestion
|   |       +-- deduplication/ # Near-duplicate detection
|   |       +-- graphics/      # Pillow image generator
|   |       +-- publishing/    # Meta Graph API client
|   +-- tests/                 # automated backend tests
|   +-- requirements.txt
+-- frontend/
|   +-- src/
|       +-- hooks/             # useAuth
|       +-- layouts/           # AppLayout sidebar
|       +-- pages/             # 9 pages
|       +-- services/          # api.js Axios client
+-- storage/
|   +-- database/              # polibrief.db
|   +-- generated/             # Pillow PNG output
|   +-- templates/             # Font assets
|   +-- logs/                  # Backend and job logs
+-- scripts/
|   +-- start.ps1              # Windows launcher
+-- .env.example
+-- .gitignore
+-- README.md
+-- pytest.ini
```

---

## Troubleshooting

### "Virtual environment not found"

```powershell
python -m venv backend\venv
backend\venv\Scripts\pip install -r backend\requirements.txt
```

### "Module not found" errors

Run all commands from the project root (the PoliBrief folder), not from inside backend/.

### Backend starts but frontend shows CORS errors

Ensure FRONTEND_URL=http://localhost:5173 is in .env and the Vite dev server is running on port 5173.

### RSS feeds not collecting

- Check internet connectivity.
- Use Test Feed in News Sources to validate the URL.
- Check storage/logs/backend.log for errors.

### Facebook publishing returns 403

Your Page Access Token has expired or lacks pages_manage_posts. Re-generate in the Meta Graph API Explorer.

### "Database is locked"

SQLite WAL mode is enabled. Stop PoliBrief completely and restart. Ensure no other process has the database open.

### Frontend build fails

```powershell
npm install --prefix frontend
npm run build --prefix frontend
```

---

*PoliBrief V1 - Private Political News & Facebook Post Management System*
*Localhost-only - No cloud services required - Administrator-approved publishing only*
