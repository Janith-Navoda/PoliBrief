"""
PoliBrief Phase 3 — Automated Tests
Tests: Political news classifier, RapidFuzz near-duplicate matching,
30-day retention enforcement, draft safeguards, storage stats, and cleanup endpoints.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.core.config import settings
from backend.app.models import Article, DuplicateFingerprint, JobLog, NewsSource, PostDraft, PublishedPost
from backend.app.services.classifier.rules import classify_article
from backend.app.services.cleanup.retention import (
    clean_orphaned_images,
    purge_expired_articles,
    purge_expired_fingerprints,
    purge_expired_job_logs,
    run_cleanup,
)
from backend.app.services.deduplication.matcher import (
    find_near_duplicate,
    find_related_stories,
    normalize_headline,
)


# ─── 1. Classifier Tests ───────────────────────────────────────────────────────

class TestClassifier:
    def test_parliament_classification(self):
        cat, score = classify_article("Senate Approves Bipartisan Legislative Reform Bill")
        assert cat == "Parliament"
        assert score >= 2.5

    def test_elections_classification(self):
        cat, score = classify_article("Voters Turn Out in Record Numbers for Key Midterm Election")
        assert cat == "Elections"
        assert score >= 2.5

    def test_international_politics_classification(self):
        cat, score = classify_article("NATO Allies and Foreign Ministers Sign Historic Mutual Defense Treaty")
        assert cat == "International Politics"
        assert score >= 2.5

    def test_economy_policy_classification(self):
        cat, score = classify_article("Federal Reserve Weighs Interest Rates Amid Fiscal Budget Negotiations")
        assert cat == "Economy and Policy"
        assert score >= 2.5

    def test_government_policy_classification(self):
        cat, score = classify_article("President Issues Executive Order on Federal Regulatory Oversight")
        assert cat == "Government and Policy"
        assert score >= 2.5

    def test_political_analysis_classification(self):
        cat, score = classify_article("Analysis: Partisanship and Polarization Deepen Across Coalitions")
        assert cat == "Political Analysis"
        assert score >= 2.5

    def test_non_political_yields_review(self):
        cat, score = classify_article("Local Bakery Celebrates 50th Anniversary with Blueberry Scones")
        assert cat == "Other / Needs Review"
        assert score < 2.5


# ─── 2. Deduplication Tests ───────────────────────────────────────────────────

class TestDeduplication:
    def test_normalize_headline(self):
        h = "  Breaking: Senate Votes 65-35 on 'Historic' Bill!  "
        norm = normalize_headline(h)
        assert norm == "breaking senate votes 6535 on historic bill"

    def test_find_near_duplicate_same_publisher(self, db):
        now = datetime.now(timezone.utc)
        source = NewsSource(publisher_name="Capitol Times", rss_url="https://capitol.test/rss")
        db.add(source)
        db.commit()

        # Existing article
        art = Article(
            source_id=source.id,
            headline="Senate Passes Major Infrastructure Spending Package",
            original_url="https://capitol.test/1",
            canonical_url="https://capitol.test/1",
            published_at=now - timedelta(hours=2),
            collected_at=now,
            status="ACTIVE",
        )
        db.add(art)
        db.commit()

        # Minor headline revision from the same publisher
        candidate = "Senate Passes Infrastructure Spending Package in Bipartisan Vote"
        match = find_near_duplicate(candidate, source.id, db, published_at=now)
        assert match is not None
        matched_article, score = match
        assert matched_article.id == art.id
        assert score >= 85.0

    def test_cross_publisher_related_stories(self, db):
        now = datetime.now(timezone.utc)
        s1 = NewsSource(publisher_name="Herald", rss_url="https://herald.test/rss")
        s2 = NewsSource(publisher_name="Tribune", rss_url="https://tribune.test/rss")
        db.add_all([s1, s2])
        db.commit()

        a1 = Article(
            source_id=s1.id,
            headline="Supreme Court Rules on Environmental Protection Agency Authority",
            original_url="https://herald.test/1",
            canonical_url="https://herald.test/1",
            published_at=now - timedelta(hours=1),
            collected_at=now,
            status="ACTIVE",
        )
        a2 = Article(
            source_id=s2.id,
            headline="Supreme Court Restricts Environmental Protection Agency Authority in Major Ruling",
            original_url="https://tribune.test/1",
            canonical_url="https://tribune.test/1",
            published_at=now - timedelta(hours=1),
            collected_at=now,
            status="ACTIVE",
        )
        db.add_all([a1, a2])
        db.commit()

        related = find_related_stories(a1.headline, a1.id, db)
        assert len(related) >= 1
        assert related[0]["article_id"] == a2.id
        assert related[0]["publisher_name"] == "Tribune"


# ─── 3. Retention & Safeguard Tests ───────────────────────────────────────────

class TestRetention:
    def test_purge_expired_articles_without_drafts(self, db):
        now = datetime.now(timezone.utc)
        source = NewsSource(publisher_name="Olds", rss_url="https://old.test/rss")
        db.add(source)
        db.commit()

        # Expired article (published 35 days ago)
        expired_article = Article(
            source_id=source.id,
            headline="Historic Treaty Signed 35 Days Ago",
            original_url="https://old.test/expired",
            canonical_url="https://old.test/expired",
            published_at=now - timedelta(days=35),
            expires_at=now - timedelta(days=5),
            collected_at=now - timedelta(days=35),
            status="ACTIVE",
        )
        # Fresh article (published 2 days ago)
        fresh_article = Article(
            source_id=source.id,
            headline="Fresh News from Yesterday",
            original_url="https://old.test/fresh",
            canonical_url="https://old.test/fresh",
            published_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=28),
            collected_at=now - timedelta(days=2),
            status="ACTIVE",
        )
        db.add_all([expired_article, fresh_article])
        db.commit()

        deleted = purge_expired_articles(db, now)
        assert deleted == 1

        remaining = db.query(Article).all()
        assert len(remaining) == 1
        assert remaining[0].id == fresh_article.id

    def test_critical_safeguard_draft_protects_expired_article(self, db):
        """CRITICAL: If an article is older than 30 days but has an active editorial draft, DO NOT DELETE IT."""
        now = datetime.now(timezone.utc)
        source = NewsSource(publisher_name="Drafty", rss_url="https://drafty.test/rss")
        db.add(source)
        db.commit()

        expired_article = Article(
            source_id=source.id,
            headline="Important Investigation Still in Draft Review",
            original_url="https://drafty.test/investigation",
            canonical_url="https://drafty.test/investigation",
            published_at=now - timedelta(days=40),
            expires_at=now - timedelta(days=10),
            collected_at=now - timedelta(days=40),
            status="ACTIVE",
        )
        db.add(expired_article)
        db.commit()

        # Create active PostDraft referencing this expired article
        draft = PostDraft(
            article_id=expired_article.id,
            headline_override="Investigative Exclusive",
            caption="Draft caption pending editorial approval",
            status="DRAFT",
        )
        db.add(draft)
        db.commit()

        # Retention cleanup must protect this article
        deleted = purge_expired_articles(db, now)
        assert deleted == 0

        # Article remains in database
        persisted = db.query(Article).filter(Article.id == expired_article.id).first()
        assert persisted is not None

    def test_purge_expired_fingerprints(self, db):
        now = datetime.now(timezone.utc)
        fp_expired = DuplicateFingerprint(
            fingerprint="old_fingerprint_hash_95_days",
            first_seen_at=now - timedelta(days=95),
            expires_at=now - timedelta(days=5),
        )
        fp_active = DuplicateFingerprint(
            fingerprint="active_fingerprint_hash_10_days",
            first_seen_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=80),
        )
        db.add_all([fp_expired, fp_active])
        db.commit()

        deleted = purge_expired_fingerprints(db, now)
        assert deleted == 1

        remaining = db.query(DuplicateFingerprint).all()
        assert len(remaining) == 1
        assert remaining[0].fingerprint == "active_fingerprint_hash_10_days"

    def test_purge_expired_job_logs(self, db):
        now = datetime.now(timezone.utc)
        old_log = JobLog(
            job_name="news_collection",
            started_at=now - timedelta(days=32),
            finished_at=now - timedelta(days=32),
            status="SUCCESS",
        )
        new_log = JobLog(
            job_name="news_collection",
            started_at=now - timedelta(days=5),
            finished_at=now - timedelta(days=5),
            status="SUCCESS",
        )
        db.add_all([old_log, new_log])
        db.commit()

        deleted = purge_expired_job_logs(db, now)
        assert deleted == 1
        assert db.query(JobLog).count() == 1

    def test_cleanup_expires_local_history_but_preserves_active_and_unresolved_work(self, db, tmp_path, monkeypatch):
        now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        image_dir = tmp_path / "generated"
        image_dir.mkdir()
        monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(image_dir))

        source = NewsSource(publisher_name="Lifecycle", rss_url="https://lifecycle.test/rss")
        db.add(source)
        db.commit()

        def article(slug):
            item = Article(
                source_id=source.id,
                headline=f"Lifecycle article {slug}",
                original_url=f"https://lifecycle.test/{slug}",
                canonical_url=f"https://lifecycle.test/{slug}",
                published_at=now - timedelta(days=140),
                collected_at=now - timedelta(days=140),
                expires_at=now - timedelta(days=110),
                status="ACTIVE",
            )
            db.add(item)
            db.flush()
            return item

        completed_article = article("completed")
        active_article = article("active")
        unresolved_article = article("unresolved")
        safe_article = article("recent-publication")

        def image(name):
            path = image_dir / name
            path.write_bytes(b"test image")
            old = (now - timedelta(hours=3)).timestamp()
            os.utime(path, (old, old))
            return str(path)

        completed_image = image("completed.png")
        active_image = image("active.png")
        unresolved_image = image("unresolved.png")
        orphan_image = image("orphan.png")

        completed_draft = PostDraft(
            article_id=completed_article.id, status="PUBLISHED",
            updated_at=now - timedelta(days=100), image_path=completed_image,
        )
        active_draft = PostDraft(
            article_id=active_article.id, status="APPROVED",
            updated_at=now - timedelta(days=100), image_path=active_image,
        )
        unresolved_draft = PostDraft(
            article_id=unresolved_article.id, status="PUBLISHING",
            updated_at=now - timedelta(days=100), image_path=unresolved_image,
        )
        recent_draft = PostDraft(
            article_id=safe_article.id, status="PUBLISHED",
            updated_at=now - timedelta(days=20), image_path=None,
        )
        db.add_all([completed_draft, active_draft, unresolved_draft, recent_draft])
        db.flush()
        db.add_all([
            PublishedPost(
                draft_id=completed_draft.id, platform="facebook", published_at=now - timedelta(days=100),
                platform_post_id="local-old-record", status="PUBLISHED",
            ),
            PublishedPost(
                draft_id=recent_draft.id, platform="facebook_manual", published_at=now - timedelta(days=20),
                platform_post_id="local-recent-record", status="PUBLISHED",
            ),
        ])
        db.commit()

        result = run_cleanup(db=db, now=now)

        assert result["publications_deleted"] == 1
        assert result["completed_drafts_deleted"] == 1
        assert result["drafts_flagged_for_review"] == 2
        assert result["articles_deleted"] == 1
        assert result["images_deleted"] == 2
        assert db.query(PublishedPost).filter_by(platform_post_id="local-recent-record").count() == 1
        assert db.query(PostDraft).filter(PostDraft.id == active_draft.id).one().status == "APPROVED"
        assert db.query(PostDraft).filter(PostDraft.id == unresolved_draft.id).one().status == "PUBLISHING"
        assert db.query(Article).filter(Article.id == active_article.id).one()
        assert db.query(Article).filter(Article.id == unresolved_article.id).one()
        assert db.query(Article).filter(Article.id == completed_article.id).count() == 0
        assert Path(active_image).exists()
        assert Path(unresolved_image).exists()
        assert not Path(completed_image).exists()
        assert not Path(orphan_image).exists()
        review_log = db.query(JobLog).filter_by(job_name="draft_retention_review").one()
        assert str(active_draft.id) in review_log.error_message
        assert str(unresolved_draft.id) in review_log.error_message


# ─── 4. System API & Storage Endpoints Tests ──────────────────────────────────

class TestSystemStorageAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def test_trigger_cleanup_endpoint(self, client):
        self._login(client)
        resp = client.post("/api/system/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "articles_deleted" in data["result"]
        assert "fingerprints_deleted" in data["result"]

    def test_storage_stats_endpoint(self, client):
        self._login(client)
        resp = client.get("/api/system/storage-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["retention_policy_days"] == 30
        assert data["fingerprint_retention_days"] == 90
        assert data["publication_history_retention_days"] == 90
        assert data["log_retention_days"] == 30
        assert "database_size_mb" in data
        assert "total_managed_mb" in data

    def test_job_logs_endpoint(self, client, db):
        self._login(client)
        now = datetime.now(timezone.utc)
        log = JobLog(
            job_name="retention_cleanup",
            started_at=now,
            finished_at=now,
            status="SUCCESS",
        )
        db.add(log)
        db.commit()

        resp = client.get("/api/system/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["job_name"] == "retention_cleanup"
