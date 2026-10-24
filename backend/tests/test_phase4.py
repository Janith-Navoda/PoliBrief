"""
PoliBrief Phase 4 — Automated Tests
Tests: Pillow 1080x1080 graphic generator (modern, breaking, minimal templates),
Facebook caption drafting, Post Drafts CRUD, approval workflow, and manual publishing.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import settings
from backend.app.models import Article, NewsSource, PostDraft, PublishedPost
from backend.app.services.captions.generator import generate_facebook_caption
from backend.app.services.graphics.generator import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    generate_post_image,
    _fit_headline,
    wrap_text,
)


# ─── 1. Pillow Graphics Generator Tests ────────────────────────────────────────

class TestPillowGraphics:
    def test_wrap_text(self):
        text = "Senate Reaches Bipartisan Compromise on Comprehensive Energy and Climate Legislation"
        lines = wrap_text(text, max_chars=30)
        assert len(lines) >= 2
        for line in lines:
            assert len(line) <= 35

    def test_render_modern_template_creates_1080x1080_png(self, tmp_path):
        out_path = generate_post_image(
            headline="Supreme Court Hears Crucial Case on Regulatory Agency Powers",
            publisher_name="Reuters",
            category="Government and Policy",
            template_id="modern",
            output_filename="test_modern.png",
        )
        assert out_path.exists()
        with Image.open(out_path) as im:
            assert im.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
            assert im.format == "PNG"

    def test_render_breaking_template(self):
        out_path = generate_post_image(
            headline="Breaking: Major Election Bill Passes Following Midnight Floor Vote",
            publisher_name="AP News",
            category="Elections",
            template_id="breaking",
            output_filename="test_breaking.png",
        )
        assert out_path.exists()
        with Image.open(out_path) as im:
            assert im.size == (1080, 1080)

    def test_render_minimal_template_with_long_headline(self):
        long_h = "International Trade Representatives Conclude Landmark Multi-Nation Economic Agreement Addressing Global Semiconductor Supply Chains and Tariffs"
        out_path = generate_post_image(
            headline=long_h,
            publisher_name="Financial Times",
            category="Economy and Policy",
            template_id="minimal",
            output_filename="test_minimal_long.png",
        )
        assert out_path.exists()
        with Image.open(out_path) as im:
            assert im.size == (1080, 1080)

    def test_long_headline_fits_pixel_box_without_dropping_words(self):
        from PIL import Image, ImageDraw

        headline = (
            "International trade representatives conclude a landmark multi nation agreement "
            "addressing semiconductor supply chains, tariffs, manufacturing investment, "
            "and cross border economic cooperation after several days of negotiations"
        )
        draw = ImageDraw.Draw(Image.new("RGB", (1080, 1080)))
        font, lines, spacing = _fit_headline(draw, headline, "segoeuib", 54, 920, 675)

        assert " ".join(lines).casefold() == headline.casefold()
        assert all(draw.textbbox((0, 0), line, font=font)[2] <= 920 for line in lines)
        assert len(lines) * spacing <= 675

    def test_missing_publication_date_is_not_rendered_as_today(self, monkeypatch):
        from PIL import Image
        from backend.app.services.graphics import generator

        rendered_dates = []
        monkeypatch.setattr(generator, "render_modern_template", lambda _h, _p, _c, date: (
            rendered_dates.append(date) or Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT))
        ))
        generate_post_image("A story", "Test Publisher", published_at=None, output_filename="unknown-date.png")
        assert rendered_dates == ["DATE UNVERIFIED"]


# ─── 2. Facebook Caption Generator Tests ──────────────────────────────────────

class TestCaptions:
    def test_generate_facebook_caption(self):
        caption = generate_facebook_caption(
            headline="Senate Confirms New Federal Judges",
            publisher_name="The Hill",
            original_url="https://thehill.com/judges-vote",
            description="The upper chamber confirmed three appellate judges in a bipartisan vote on Thursday afternoon.",
            category="Parliament",
        )
        assert "Senate Confirms New Federal Judges" in caption
        assert "Source: The Hill" in caption
        assert "https://thehill.com/judges-vote" in caption
        assert "#Parliament" in caption
        assert "#Politics" in caption

    def test_caption_handles_empty_description(self):
        caption = generate_facebook_caption(
            headline="President Delivers State Address",
            publisher_name="PBS NewsHour",
            original_url="https://pbs.org/address",
            description="",
            category="Government and Policy",
        )
        assert "President Delivers State Address" in caption
        assert "Source: PBS NewsHour" in caption
        assert "#Government" in caption


# ─── 3. Post Drafts API & Workflow Integration Tests ──────────────────────────

class TestDraftsAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def _create_sample_article(self, db):
        source = NewsSource(publisher_name="Politico", rss_url="https://politico.test/rss")
        db.add(source)
        db.commit()

        article = Article(
            source_id=source.id,
            headline="Congressional Leaders Announce Fiscal Year Budget Deal",
            description="Negotiators worked through the weekend to reach a bipartisan agreement.",
            original_url="https://politico.test/deal",
            canonical_url="https://politico.test/deal",
            category="Economy and Policy",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        db.add(article)
        db.commit()
        return article

    def test_create_draft_renders_image_and_caption(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)

        resp = client.post("/api/drafts", json={
            "article_id": article.id,
            "headline_override": "Budget Deal Reached in Congress",
            "template_id": "modern",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["status"] == "DRAFT"
        assert data["headline_override"] == "Budget Deal Reached in Congress"
        assert "Congressional Leaders" in data["caption"] or "Budget Deal" in data["caption"]
        assert data["image_url"] is not None

        # Verify image file was physically created in storage
        draft_in_db = db.query(PostDraft).filter(PostDraft.id == data["id"]).first()
        assert os.path.exists(draft_in_db.image_path)

    def test_preview_endpoint(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)

        resp = client.post("/api/drafts/preview", json={
            "article_id": article.id,
            "headline_override": "Live Preview Headline",
            "template_id": "breaking",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "preview-file" in data["image_url"]
        assert "Live Preview Headline" in data["caption"]

    def test_draft_list_limit_is_honored_and_optional(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        for _ in range(3):
            response = client.post("/api/drafts", json={"article_id": article.id})
            assert response.status_code == 201

        assert len(client.get("/api/drafts?limit=1").json()) == 1
        assert len(client.get("/api/drafts").json()) == 3

    def test_related_coverage_returns_other_publishers(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        other_source = NewsSource(publisher_name="Associated Press", rss_url="https://ap.test/rss")
        db.add(other_source)
        db.commit()
        related = Article(
            source_id=other_source.id,
            headline="Congressional Leaders Announce Fiscal Year Budget Deal",
            original_url="https://ap.test/budget",
            canonical_url="https://ap.test/budget",
            category="Economy and Policy",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        same_publisher = Article(
            source_id=article.source_id,
            headline="Congressional Leaders Announce Fiscal Year Budget Deal",
            original_url="https://politico.test/budget-update",
            canonical_url="https://politico.test/budget-update",
            category="Economy and Policy",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            status="ACTIVE",
        )
        db.add_all([related, same_publisher])
        db.commit()

        response = client.get(f"/api/articles/{article.id}/related")
        assert response.status_code == 200
        result_ids = {item["article_id"] for item in response.json()}
        assert related.id in result_ids
        assert same_publisher.id not in result_ids

    def test_draft_creation_enforces_required_source_attribution(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        article.source.content_restrictions = '{"attribution_required": true}'
        db.commit()

        rejected = client.post("/api/drafts", json={
            "article_id": article.id,
            "caption": "A caption without attribution",
        })
        assert rejected.status_code == 422

        accepted = client.post("/api/drafts", json={
            "article_id": article.id,
            "caption": f"Source: {article.source.publisher_name} {article.original_url}",
        })
        assert accepted.status_code == 201

    def test_update_draft_and_approve(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)

        # Create draft
        create_resp = client.post("/api/drafts", json={
            "article_id": article.id,
            "template_id": "modern",
        })
        draft_id = create_resp.json()["id"]

        # Update caption and headline
        update_resp = client.put(f"/api/drafts/{draft_id}", json={
            "headline_override": "Updated Custom Headline",
            "caption": "Custom edited caption for social media.",
            "template_id": "minimal",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["headline_override"] == "Updated Custom Headline"
        assert update_resp.json()["caption"] == "Custom edited caption for social media."

        # Approve draft
        approve_resp = client.post(f"/api/drafts/{draft_id}/approve")
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "APPROVED"
        assert approve_resp.json()["approved_at"] is not None

    def test_mark_published_creates_audit_record(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)

        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        client.post(f"/api/drafts/{draft_id}/approve")

        pub_resp = client.post(f"/api/drafts/{draft_id}/mark-published?platform_post_id=fb_123456789")
        assert pub_resp.status_code == 200
        assert pub_resp.json()["status"] == "PUBLISHED"

        # Check published_posts table
        pub_record = db.query(PublishedPost).filter(PublishedPost.draft_id == draft_id).first()
        assert pub_record is not None
        assert pub_record.platform == "facebook_manual"
        assert pub_record.platform_post_id == "fb_123456789"
        assert '"administrator_confirmed": true' in pub_record.audit_metadata

        duplicate_resp = client.post(
            f"/api/drafts/{draft_id}/mark-published?platform_post_id=fb_123456789"
        )
        assert duplicate_resp.status_code == 409

    def test_manual_publishing_requires_approval(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]

        response = client.post(f"/api/drafts/{draft_id}/mark-published")
        assert response.status_code == 409
        assert db.query(PublishedPost).filter(PublishedPost.draft_id == draft_id).first() is None

    def test_generic_update_cannot_approve_draft(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]

        response = client.put(f"/api/drafts/{draft_id}", json={"status": "APPROVED"})
        assert response.status_code == 409
        assert db.query(PostDraft).filter(PostDraft.id == draft_id).first().status == "DRAFT"

    def test_editing_approved_content_revokes_approval(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        assert client.post(f"/api/drafts/{draft_id}/approve").status_code == 200

        response = client.put(f"/api/drafts/{draft_id}", json={"caption": "Edited after review"})
        assert response.status_code == 200
        draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
        assert draft.status == "DRAFT"
        assert draft.approved_at is None

    def test_draft_images_require_authentication(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        preview_resp = client.post("/api/drafts/preview", json={"article_id": article.id})
        preview_path = preview_resp.json()["image_url"]

        client.post("/api/auth/logout")
        assert client.get(f"/api/drafts/{draft_id}/image").status_code == 401
        assert client.get(preview_path).status_code == 401

    def test_delete_draft_removes_image_file(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)

        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        img_path = create_resp.json()["image_path"]

        del_resp = client.delete(f"/api/drafts/{draft_id}")
        assert del_resp.status_code == 200
        assert not os.path.exists(img_path)

    def test_delete_database_failure_preserves_draft_image(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        image_path = create_resp.json()["image_path"]

        db.execute(text("""
            CREATE TRIGGER reject_draft_delete BEFORE DELETE ON post_drafts
            BEGIN SELECT RAISE(ABORT, 'isolated delete failure'); END
        """))
        db.commit()
        response = client.delete(f"/api/drafts/{draft_id}")

        assert response.status_code == 409
        assert os.path.exists(image_path)
        assert db.query(PostDraft).filter(PostDraft.id == draft_id).one()

    def test_published_draft_delete_preserves_publication_and_image(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        image_path = create_resp.json()["image_path"]
        assert client.post(f"/api/drafts/{draft_id}/approve").status_code == 200
        assert client.post(
            f"/api/drafts/{draft_id}/mark-published?platform_post_id=manual_test_post"
        ).status_code == 200

        response = client.delete(f"/api/drafts/{draft_id}")

        assert response.status_code == 409
        assert "retained publication history" in response.json()["detail"]
        assert db.query(PostDraft).filter_by(id=draft_id).one().status == "PUBLISHED"
        publication = db.query(PublishedPost).filter_by(draft_id=draft_id).one()
        assert publication.platform_post_id == "manual_test_post"
        assert os.path.exists(image_path)

    def test_publication_foreign_key_restricts_direct_draft_delete(self, db):
        source = NewsSource(publisher_name="Audit Feed", rss_url="https://audit.test/rss")
        db.add(source)
        db.flush()
        article = Article(
            source_id=source.id,
            headline="Retained publication",
            original_url="https://audit.test/story",
            canonical_url="https://audit.test/story",
            status="ACTIVE",
        )
        db.add(article)
        db.flush()
        draft = PostDraft(article_id=article.id, status="PUBLISHED")
        db.add(draft)
        db.flush()
        db.add(PublishedPost(draft_id=draft.id, platform="facebook", platform_post_id="audit-post"))
        db.commit()

        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            db.delete(draft)
            db.flush()
        db.rollback()

        assert db.query(PostDraft).filter_by(id=draft.id).one().status == "PUBLISHED"
        assert db.query(PublishedPost).filter_by(platform_post_id="audit-post").one()

    def test_unresolved_publishing_draft_cannot_be_deleted(self, client, db):
        self._login(client)
        article = self._create_sample_article(db)
        create_resp = client.post("/api/drafts", json={"article_id": article.id})
        draft_id = create_resp.json()["id"]
        image_path = create_resp.json()["image_path"]
        db.query(PostDraft).filter_by(id=draft_id).update({PostDraft.status: "PUBLISHING"})
        db.commit()

        response = client.delete(f"/api/drafts/{draft_id}")

        assert response.status_code == 409
        assert db.query(PostDraft).filter_by(id=draft_id).one().status == "PUBLISHING"
        assert os.path.exists(image_path)
