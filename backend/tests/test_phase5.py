"""
PoliBrief Phase 5 — Automated Tests
Tests: Meta Graph API client, token/page connection validation,
approved-only publishing enforcement, duplicate prevention, and publication history.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models import Article, NewsSource, PostDraft, PublishedPost
from backend.app.services.publishing.meta import MetaClient, MetaPublishRejected, PublishOutcomeUnknown


# ─── 1. MetaClient Unit Tests with Mocks ───────────────────────────────────────

class TestMetaClient:
    @pytest.mark.asyncio
    async def test_validate_connection_unconfigured(self):
        client = MetaClient(page_id="", page_token="")
        res = await client.validate_connection()
        assert res["configured"] is False
        assert res["valid"] is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_validate_connection_success(self, mock_get):
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "123456789",
            "name": "PoliBrief Official Page",
            "category": "Media/News Company",
            "is_published": True,
        }
        mock_get.return_value = mock_resp

        client = MetaClient(page_id="123456789", page_token="mock_valid_token")
        res = await client.validate_connection()
        assert res["configured"] is True
        assert res["valid"] is True
        assert res["page_name"] == "PoliBrief Official Page"
        kwargs = mock_get.await_args.kwargs
        assert "access_token" not in kwargs["params"]
        assert kwargs["headers"]["Authorization"] == "Bearer mock_valid_token"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_publish_sends_token_outside_url_and_form(self, mock_post, tmp_path):
        from unittest.mock import MagicMock

        image_path = tmp_path / "post.png"
        image_path.write_bytes(b"isolated-test-image")
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "photo-test", "post_id": "page-post-test"}
        mock_post.return_value = response

        client = MetaClient(page_id="test-page", page_token="mock_publish_token")
        await client.publish_photo_post(str(image_path), "test caption")

        args, kwargs = mock_post.await_args
        assert "access_token" not in args[0]
        assert "access_token" not in kwargs["data"]
        assert kwargs["headers"]["Authorization"] == "Bearer mock_publish_token"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_validate_connection_invalid_token(self, mock_get):
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "Error validating access token: Session has expired",
                "type": "OAuthException",
                "code": 190,
            }
        }
        mock_get.return_value = mock_resp

        client = MetaClient(page_id="123456789", page_token="expired_token")
        res = await client.validate_connection()
        assert res["configured"] is True
        assert res["valid"] is False
        assert res["error_code"] == 190
        assert "code: 190" in res["message"]


# ─── 2. Publishing API Integration Tests ──────────────────────────────────────

class TestPublishingAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def _create_sample_draft(self, client, db, status="DRAFT"):
        source = NewsSource(publisher_name="Wire", rss_url="https://wire.test/rss")
        db.add(source)
        db.commit()

        article = Article(
            source_id=source.id,
            headline="Supreme Court Decision on Campaign Finance",
            original_url="https://wire.test/scotus",
            canonical_url="https://wire.test/scotus",
            category="Elections",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        db.add(article)
        db.commit()

        # Create draft via API
        resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = resp.json()["id"]

        if status == "APPROVED":
            client.post(f"/api/drafts/{draft_id}/approve")

        return draft_id

    def test_get_meta_status(self, client):
        self._login(client)
        resp = client.get("/api/publishing/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "valid" in data

    def test_cannot_publish_unapproved_draft(self, client, db):
        """CRITICAL: Drafts with status 'DRAFT' must be rejected with 400."""
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="DRAFT")

        resp = client.post(f"/api/publishing/{draft_id}")
        assert resp.status_code == 400
        assert "Only APPROVED drafts can be published" in resp.json()["detail"]

    @patch("backend.app.services.publishing.meta.MetaClient.is_configured", False)
    def test_approved_draft_without_meta_configuration_is_not_claimed(self, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")

        response = client.post(f"/api/publishing/{draft_id}")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
        assert db.query(PostDraft).filter_by(id=draft_id).one().status == "APPROVED"
        assert db.query(PublishedPost).filter_by(draft_id=draft_id).count() == 0

    @patch("backend.app.services.publishing.meta.MetaClient.publish_photo_post")
    @patch("backend.app.services.publishing.meta.MetaClient.is_configured", True)
    def test_publish_approved_draft_success(self, mock_publish, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")

        # Mock successful Meta publish response
        mock_publish.return_value = {
            "success": True,
            "photo_id": "photo_987654321",
            "post_id": "page_post_987654321",
            "fb_url": "https://facebook.com/page_post_987654321",
            "raw_response": {"id": "photo_987654321", "post_id": "page_post_987654321"},
        }

        resp = client.post(f"/api/publishing/{draft_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["platform_post_id"] == "page_post_987654321"

        # Verify draft status is now PUBLISHED
        draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
        assert draft.status == "PUBLISHED"

        # Verify published_posts record created
        pub = db.query(PublishedPost).filter(PublishedPost.draft_id == draft_id).first()
        assert pub is not None
        assert pub.platform == "facebook"
        assert pub.platform_post_id == "page_post_987654321"

    @patch("backend.app.services.publishing.meta.MetaClient.publish_photo_post")
    @patch("backend.app.services.publishing.meta.MetaClient.is_configured", True)
    def test_duplicate_publishing_prevented(self, mock_publish, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")

        mock_publish.return_value = {
            "success": True,
            "post_id": "first_post_id",
            "fb_url": "https://facebook.com/first_post_id",
        }

        # First publish: succeeds
        client.post(f"/api/publishing/{draft_id}")

        # Second publish: must be rejected with 409
        resp2 = client.post(f"/api/publishing/{draft_id}")
        assert resp2.status_code == 409
        assert "already published" in resp2.json()["detail"]

    @patch("backend.app.services.publishing.meta.MetaClient.publish_photo_post", new_callable=AsyncMock)
    @patch("backend.app.services.publishing.meta.MetaClient.is_configured", True)
    def test_definitive_meta_rejection_does_not_create_publication(self, mock_publish, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")
        mock_publish.side_effect = MetaPublishRejected(error_code=10)

        response = client.post(f"/api/publishing/{draft_id}")

        assert response.status_code == 502
        assert db.query(PostDraft).filter_by(id=draft_id).one().status == "FAILED"
        assert db.query(PublishedPost).filter_by(draft_id=draft_id).count() == 0

    @patch("backend.app.services.publishing.meta.MetaClient.publish_photo_post", new_callable=AsyncMock)
    @patch("backend.app.services.publishing.meta.MetaClient.is_configured", True)
    def test_uncertain_publish_cannot_retry_until_admin_reconciles(self, mock_publish, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")
        mock_publish.side_effect = PublishOutcomeUnknown("test-only uncertain result")

        first = client.post(f"/api/publishing/{draft_id}")
        assert first.status_code == 202
        assert first.json()["status"] == "PUBLISHING"
        assert db.query(PostDraft).filter(PostDraft.id == draft_id).first().status == "PUBLISHING"

        retry = client.post(f"/api/publishing/{draft_id}")
        assert retry.status_code == 409
        mock_publish.assert_awaited_once()

        resolution = client.post(
            f"/api/publishing/{draft_id}/resolve",
            json={"outcome": "CONFIRMED_NOT_PUBLISHED"},
        )
        assert resolution.status_code == 200
        assert resolution.json()["status"] == "APPROVED"

        mock_publish.side_effect = None
        mock_publish.return_value = {
            "success": True,
            "post_id": "reconciled-post-id",
            "fb_url": "https://facebook.com/reconciled-post-id",
            "raw_response": {"post_id": "reconciled-post-id"},
        }
        second_attempt = client.post(f"/api/publishing/{draft_id}")
        assert second_attempt.status_code == 200
        assert mock_publish.await_count == 2

    def test_publication_history_endpoint(self, client, db):
        self._login(client)
        draft_id = self._create_sample_draft(client, db, status="APPROVED")
        client.post(f"/api/drafts/{draft_id}/mark-published?platform_post_id=manual_post_100")

        resp = client.get("/api/publishing/history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert history[0]["platform_post_id"] == "manual_post_100"
        assert history[0]["headline"] == "Supreme Court Decision on Campaign Finance"
