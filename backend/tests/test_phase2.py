"""
PoliBrief Phase 2 — Automated Tests
Tests: RSS parsing, URL sanitization, date normalization, source CRUD,
collection pipeline, duplicate avoidance, and article search/filter API endpoints.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import event

from backend.app.auth.service import create_admin
from backend.app.models import Article, DuplicateFingerprint, NewsSource
from backend.app.services.collector.rss import (
    clean_html_summary,
    compute_fingerprint,
    is_safe_feed_url,
    parse_entry_datetime,
    sanitize_url,
)
from backend.app.services.collector.runner import run_collection

# Sample RSS XML fixture
SAMPLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>National Political News</title>
    <link>https://example.com/news</link>
    <description>Daily politics reporting</description>
    <item>
      <title>Senate Passes Bipartisan Electoral Reform Bill</title>
      <link>https://example.com/senate-electoral-bill?utm_source=twitter&amp;fbclid=12345</link>
      <description>&lt;p&gt;Lawmakers voted 65-35 on &amp;quot;historic&amp;quot; legislation.&lt;/p&gt;</description>
      <pubDate>Fri, 24 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Supreme Court Hears Arguments on State Regulatory Powers</title>
      <link>https://example.com/scotus-regulatory-case</link>
      <description>Justices questioned state and federal jurisdictional boundaries.</description>
      <pubDate>Fri, 24 Oct 2026 14:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


# ─── 1. Unit Tests: Normalization and Utilities ────────────────────────────────

class TestCollectorUtilities:
    def test_sanitize_url_strips_tracking_parameters(self):
        raw = "https://example.com/article?utm_source=fb&id=42&utm_medium=cpc&fbclid=abc#header"
        clean = sanitize_url(raw)
        assert "utm_source" not in clean
        assert "fbclid" not in clean
        assert "id=42" in clean
        assert "#header" not in clean

    def test_sanitize_url_handles_clean_urls(self):
        raw = "https://news.example.com/2026/senate-hearing"
        assert sanitize_url(raw) == "https://news.example.com/2026/senate-hearing"

    def test_compute_fingerprint_deterministic(self):
        f1 = compute_fingerprint("https://example.com/article-1", "Headline")
        f2 = compute_fingerprint("https://example.com/article-1", "Headline")
        f3 = compute_fingerprint("https://example.com/article-2", "Headline")
        assert f1 == f2
        assert f1 != f3
        assert len(f1) == 64

    def test_clean_html_summary(self):
        raw = "<p>The president announced <strong>new policy</strong> &amp; guidelines.</p><script>alert(1)</script>"
        cleaned = clean_html_summary(raw)
        assert cleaned == "The president announced new policy & guidelines."

    def test_parse_entry_datetime(self):
        entry = {"published_parsed": (2026, 10, 24, 15, 30, 0, 4, 297, 0)}
        dt = parse_entry_datetime(entry)
        assert dt.year == 2026
        assert dt.month == 10
        assert dt.day == 24
        assert dt.tzinfo == timezone.utc

    def test_parse_missing_or_malformed_datetime_stays_unknown(self):
        assert parse_entry_datetime({}) is None
        assert parse_entry_datetime({"published": "not a real date"}) is None
        assert parse_entry_datetime({"published": "2026-10-24T12:00:00"}) is None

    def test_is_safe_feed_url(self):
        assert is_safe_feed_url("https://feeds.npr.org/politics/rss.xml") is True
        assert is_safe_feed_url("http://example.com/rss") is True
        assert is_safe_feed_url("ftp://example.com/rss") is False
        assert is_safe_feed_url("file:///etc/passwd") is False
        assert is_safe_feed_url("not-a-url") is False
        assert is_safe_feed_url("http://127.0.0.1/rss") is False
        assert is_safe_feed_url("http://169.254.169.254/latest/meta-data") is False
        assert is_safe_feed_url("http://localhost.localdomain/rss") is False
        assert is_safe_feed_url("http://user:pass@example.com/rss") is False


# ─── 2. Integration Tests: News Source Management API ─────────────────────────

class TestSourcesAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def test_create_and_list_source(self, client):
        self._login(client)
        resp = client.post("/api/sources", json={
            "publisher_name": "Test Tribune",
            "rss_url": "https://tribune.example.com/rss",
            "website_url": "https://tribune.example.com",
            "language": "en",
            "enabled": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["publisher_name"] == "Test Tribune"
        assert data["id"] is not None

        list_resp = client.get("/api/sources")
        assert list_resp.status_code == 200
        sources = list_resp.json()
        assert len(sources) == 1
        assert sources[0]["publisher_name"] == "Test Tribune"

    def test_create_duplicate_rss_url_fails(self, client):
        self._login(client)
        client.post("/api/sources", json={
            "publisher_name": "Source One",
            "rss_url": "https://shared.example.com/rss",
        })
        resp = client.post("/api/sources", json={
            "publisher_name": "Source Two",
            "rss_url": "https://shared.example.com/rss",
        })
        assert resp.status_code == 409

    def test_private_rss_targets_are_rejected_on_create_and_update(self, client):
        self._login(client)
        rejected = client.post("/api/sources", json={
            "publisher_name": "Local Target",
            "rss_url": "http://127.0.0.1:8000/rss",
        })
        assert rejected.status_code == 422

        created = client.post("/api/sources", json={
            "publisher_name": "Public Target",
            "rss_url": "https://public.example.com/rss",
        })
        source_id = created.json()["id"]
        update = client.put(f"/api/sources/{source_id}", json={"rss_url": "http://192.168.1.1/rss"})
        assert update.status_code == 422
        assert client.get(f"/api/sources/{source_id}").json()["rss_url"] == "https://public.example.com/rss"

    def test_update_source(self, client):
        self._login(client)
        post_resp = client.post("/api/sources", json={
            "publisher_name": "Old Name",
            "rss_url": "https://old.example.com/rss",
        })
        source_id = post_resp.json()["id"]

        patch_resp = client.put(f"/api/sources/{source_id}", json={
            "publisher_name": "Updated Name",
            "enabled": False,
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["publisher_name"] == "Updated Name"
        assert patch_resp.json()["enabled"] is False

    def test_delete_source(self, client):
        self._login(client)
        post_resp = client.post("/api/sources", json={
            "publisher_name": "To Delete",
            "rss_url": "https://delete.example.com/rss",
        })
        source_id = post_resp.json()["id"]

        del_resp = client.delete(f"/api/sources/{source_id}")
        assert del_resp.status_code == 200

        get_resp = client.get(f"/api/sources/{source_id}")
        assert get_resp.status_code == 404

    def test_seed_default_sources(self, client):
        self._login(client)
        resp = client.post("/api/sources/seed-defaults")
        assert resp.status_code == 200
        seeded = resp.json()
        assert len(seeded) >= 3

        # Calling again should not create duplicates
        resp2 = client.post("/api/sources/seed-defaults")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 0


# ─── 3. Pipeline Ingestion & Deduplication Tests ──────────────────────────────

class TestCollectionPipeline:
    @staticmethod
    def _source(db, publisher="Mock Feed"):
        source = NewsSource(
            publisher_name=publisher,
            rss_url="https://feed.example.test/rss",
            enabled=True,
            status="PENDING",
        )
        db.add(source)
        db.commit()
        return source

    @staticmethod
    def _feed(*entries):
        from types import SimpleNamespace
        return SimpleNamespace(entries=list(entries))

    def test_duplicate_canonical_urls_in_one_batch_are_staged_once(self, db):
        from backend.app.services.collector import runner

        source = self._source(db)
        feed = self._feed(
            {"title": "First copy", "link": "https://feed.example.test/story?utm_source=one"},
            {"title": "Second copy", "link": "https://feed.example.test/story?utm_medium=two"},
        )
        with patch.object(runner, "fetch_feed_data", new=AsyncMock(return_value=feed)):
            result = run_collection(db=db, source_id=source.id)

        assert result["new_articles"] == 1
        assert result["skipped_duplicates"] == 1
        assert db.query(Article).count() == 1
        assert db.query(DuplicateFingerprint).count() == 1

    def test_duplicate_fingerprints_in_one_batch_are_staged_once(self, db, monkeypatch):
        from backend.app.services.collector import runner

        source = self._source(db)
        feed = self._feed(
            {"title": "First story", "link": "https://feed.example.test/one"},
            {"title": "Second story", "link": "https://feed.example.test/two"},
        )
        monkeypatch.setattr(runner, "compute_fingerprint", lambda *_args: "same-fingerprint")
        with patch.object(runner, "fetch_feed_data", new=AsyncMock(return_value=feed)):
            result = run_collection(db=db, source_id=source.id)

        assert result["new_articles"] == 1
        assert result["skipped_duplicates"] == 1
        assert db.query(Article).count() == 1
        assert db.query(DuplicateFingerprint).count() == 1

    def test_integrity_error_rolls_back_batch_and_persists_check_time(self, db):
        from backend.app.services.collector import runner

        source = self._source(db)
        previous_success = datetime(2026, 1, 2, tzinfo=timezone.utc)
        source.last_success = previous_success
        db.commit()
        feed = self._feed({"title": "Rollback story", "link": "https://feed.example.test/rollback"})
        injected = {"done": False}

        def inject_conflict(session, _flush_context, _instances):
            if injected["done"]:
                return
            injected["done"] = True
            expiry = datetime.now(timezone.utc) + timedelta(days=90)
            session.add_all([
                DuplicateFingerprint(fingerprint="forced-conflict", expires_at=expiry),
                DuplicateFingerprint(fingerprint="forced-conflict", expires_at=expiry),
            ])

        event.listen(db, "before_flush", inject_conflict)
        try:
            with patch.object(runner, "fetch_feed_data", new=AsyncMock(return_value=feed)):
                result = run_collection(db=db, source_id=source.id)
        finally:
            event.remove(db, "before_flush", inject_conflict)

        refreshed = db.query(NewsSource).filter_by(id=source.id).one()
        assert result["new_articles"] == 0
        assert result["errors"]
        assert "IntegrityError" in result["errors"][0]["error"]
        assert db.query(Article).count() == 0
        assert db.query(DuplicateFingerprint).count() == 0
        assert refreshed.last_checked is not None
        assert refreshed.last_success.replace(tzinfo=timezone.utc) == previous_success
        assert refreshed.status == "ERROR"

    def test_successful_zero_new_articles_updates_both_timestamps(self, db):
        from backend.app.services.collector import runner

        source = self._source(db)
        article = Article(
            source_id=source.id,
            headline="Already collected",
            original_url="https://feed.example.test/existing",
            canonical_url="https://feed.example.test/existing",
            fingerprint=compute_fingerprint("https://feed.example.test/existing", "Already collected"),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        db.add(article)
        db.commit()
        feed = self._feed({"title": "Already collected", "link": "https://feed.example.test/existing"})
        with patch.object(runner, "fetch_feed_data", new=AsyncMock(return_value=feed)):
            result = run_collection(db=db, source_id=source.id)

        refreshed = db.query(NewsSource).filter_by(id=source.id).one()
        assert result["new_articles"] == 0
        assert result["errors"] == []
        assert refreshed.status == "ACTIVE"
        assert refreshed.last_checked is not None
        assert refreshed.last_success is not None

    def test_collect_from_mock_rss(self, db):
        import feedparser

        # Create source in db
        source = NewsSource(
            publisher_name="Example Politics",
            rss_url="https://example.com/feed.xml",
            enabled=True,
            status="PENDING",
        )
        db.add(source)
        db.commit()

        # Run collection
        with patch(
            "backend.app.services.collector.runner.fetch_feed_data",
            new=AsyncMock(return_value=feedparser.parse(SAMPLE_RSS_XML)),
        ):
            result = run_collection(db=db, source_id=source.id)
        assert result["new_articles"] == 2
        assert result["skipped_duplicates"] == 0

        # Verify articles persisted in database
        articles = db.query(Article).all()
        assert len(articles) == 2
        headlines = [a.headline for a in articles]
        assert "Senate Passes Bipartisan Electoral Reform Bill" in headlines
        assert "Supreme Court Hears Arguments on State Regulatory Powers" in headlines

        # Verify tracking param was stripped from canonical URL
        reform_article = db.query(Article).filter(Article.headline.like("%Senate%")).first()
        assert "utm_source" not in reform_article.canonical_url
        assert "fbclid" not in reform_article.canonical_url

        # Verify 30-day expiration is populated
        assert reform_article.expires_at is not None
        assert (reform_article.expires_at - reform_article.published_at).days == 30

        # Verify duplicate fingerprints were created
        fps = db.query(DuplicateFingerprint).all()
        assert len(fps) == 2

        # Run collection a second time with identical feed — must detect duplicates!
        with patch(
            "backend.app.services.collector.runner.fetch_feed_data",
            new=AsyncMock(return_value=feedparser.parse(SAMPLE_RSS_XML)),
        ):
            result2 = run_collection(db=db, source_id=source.id)
        assert result2["new_articles"] == 0
        assert result2["skipped_duplicates"] == 2

        # Articles count in DB should still be 2
        assert db.query(Article).count() == 2

    def test_entries_without_verified_dates_are_quarantined(self, db):
        import feedparser

        source = NewsSource(
            publisher_name="Undated Feed",
            rss_url="https://undated.example.com/rss",
            enabled=True,
        )
        db.add(source)
        db.commit()
        xml = b"""<rss version='2.0'><channel><title>Feed</title><item>
        <title>Policy story with no verified date</title><link>https://undated.example.com/story</link>
        </item></channel></rss>"""

        with patch("backend.app.services.collector.runner.fetch_feed_data", new=AsyncMock(return_value=feedparser.parse(xml))):
            result = run_collection(db=db, source_id=source.id)

        article = db.query(Article).filter_by(canonical_url="https://undated.example.com/story").one()
        assert result["uncertain_dates"] == 1
        assert article.published_at is None
        assert article.status == "DATE_REVIEW"
        assert article.expires_at is not None
        assert article.expires_at > article.collected_at

    @pytest.mark.asyncio
    async def test_feed_redirect_to_private_address_is_rejected(self):
        from contextlib import asynccontextmanager
        from unittest.mock import Mock
        from backend.app.services.collector.rss import fetch_feed_data

        redirect = Mock()
        redirect.is_redirect = True
        redirect.headers = {"location": "http://127.0.0.1/private"}
        calls = []
        @asynccontextmanager
        async def mocked_stream(*_args, **_kwargs):
            calls.append(True)
            yield redirect

        with patch("httpx.AsyncClient.stream", new=mocked_stream):
            with pytest.raises(ValueError, match="redirect target"):
                await fetch_feed_data("https://public.example.com/feed")
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_feed_response_size_is_bounded(self, monkeypatch):
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        from backend.app.services.collector import rss

        class Response:
            status_code = 200
            is_redirect = False
            headers = {}

            def raise_for_status(self):
                return None

            async def aiter_bytes(self):
                yield b"x" * (rss.MAX_FEED_BYTES + 1)

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None

            @asynccontextmanager
            async def stream(self, *_args, **_kwargs):
                yield Response()

        class Transport:
            def __init__(self, **_kwargs):
                self._pool = SimpleNamespace(_network_backend=None)

        monkeypatch.setattr(rss.httpx, "AsyncHTTPTransport", Transport)
        monkeypatch.setattr(rss.httpx, "AsyncClient", lambda **_kwargs: Client())

        with pytest.raises(ValueError, match="8 MiB size limit"):
            await rss.fetch_feed_data("https://public.example.com/feed")

    @pytest.mark.asyncio
    async def test_temporary_server_error_retries_within_bound(self, monkeypatch):
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        from backend.app.services.collector import rss

        class Response:
            is_redirect = False
            headers = {}

            def __init__(self, status_code): self.status_code = status_code
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise rss.httpx.HTTPStatusError("server error", request=Mock(), response=Mock())

            async def aiter_bytes(self):
                yield SAMPLE_RSS_XML

        class Client:
            def __init__(self): self.calls = 0
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None

            @asynccontextmanager
            async def stream(self, *_args, **_kwargs):
                self.calls += 1
                yield Response(503 if self.calls == 1 else 200)

        class Transport:
            def __init__(self, **_kwargs):
                self._pool = SimpleNamespace(_network_backend=None)

        client = Client()
        monkeypatch.setattr(rss.httpx, "AsyncHTTPTransport", Transport)
        monkeypatch.setattr(rss.httpx, "AsyncClient", lambda **_kwargs: client)
        monkeypatch.setattr(rss.asyncio, "sleep", AsyncMock())

        feed = await rss.fetch_feed_data("https://public.example.com/feed")
        assert len(feed.entries) == 2
        assert client.calls == 2

    @pytest.mark.asyncio
    async def test_feed_dns_is_pinned_to_validated_public_address(self, monkeypatch):
        import socket
        from unittest.mock import AsyncMock
        from backend.app.services.collector import rss

        backend = rss.PublicOnlyNetworkBackend()
        connect = AsyncMock(return_value=object())
        monkeypatch.setattr(backend._backend, "connect_tcp", connect)
        monkeypatch.setattr(
            rss.socket,
            "getaddrinfo",
            lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", args[1]))],
        )
        await backend.connect_tcp("feed.example", 443)
        assert connect.await_args.args[0] == "93.184.216.34"

        monkeypatch.setattr(
            rss.socket,
            "getaddrinfo",
            lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", args[1]))],
        )
        with pytest.raises(rss.PublicOnlyNetworkBackend()._httpcore.ConnectError):
            await backend.connect_tcp("feed.example", 443)
        assert connect.await_count == 1


# ─── 4. Articles API & Search/Filter Tests ────────────────────────────────────

class TestArticlesAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def test_list_and_search_articles(self, client, db):
        self._login(client)

        source = NewsSource(publisher_name="Capitol Post", rss_url="https://capitol.test/rss")
        db.add(source)
        db.commit()

        now = datetime.now(timezone.utc)
        a1 = Article(
            source_id=source.id,
            headline="Budget Agreement Reached in Congress",
            description="Leaders agreed on a fiscal spending cap.",
            original_url="https://capitol.test/budget",
            canonical_url="https://capitol.test/budget",
            category="Economy and Policy",
            published_at=now - timedelta(hours=2),
            collected_at=now,
            status="ACTIVE",
        )
        a2 = Article(
            source_id=source.id,
            headline="Supreme Court Decision on Free Speech",
            description="First amendment ruling announced today.",
            original_url="https://capitol.test/scotus",
            canonical_url="https://capitol.test/scotus",
            category="Government and Policy",
            published_at=now - timedelta(hours=1),
            collected_at=now,
            status="ACTIVE",
        )
        db.add_all([a1, a2])
        db.commit()

        # List all
        resp = client.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Search keyword
        search_resp = client.get("/api/articles?q=Budget")
        assert search_resp.status_code == 200
        assert search_resp.json()["total"] == 1
        assert search_resp.json()["items"][0]["headline"] == "Budget Agreement Reached in Congress"

        # Filter by category
        cat_resp = client.get("/api/articles?category=Government and Policy")
        assert cat_resp.status_code == 200
        assert cat_resp.json()["total"] == 1
        assert cat_resp.json()["items"][0]["category"] == "Government and Policy"

    def test_patch_article_category(self, client, db):
        self._login(client)
        source = NewsSource(publisher_name="Wire", rss_url="https://wire.test/rss")
        db.add(source)
        db.commit()

        article = Article(
            source_id=source.id,
            headline="Election Turnout High",
            original_url="https://wire.test/1",
            canonical_url="https://wire.test/1",
            category="Other / Needs Review",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        db.add(article)
        db.commit()

        # Update category
        patch_resp = client.patch(f"/api/articles/{article.id}", json={"category": "Elections"})
        assert patch_resp.status_code == 200
        assert patch_resp.json()["category"] == "Elections"
