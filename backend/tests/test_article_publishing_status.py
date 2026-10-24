"""Regression coverage for effective article publication state and duplicate guards."""
import json
from datetime import datetime, timedelta, timezone

from backend.app.models import Article, NewsSource, PostDraft, PublishedPost
from backend.app.services.publishing.article_status import get_article_publishing_statuses


def create_article(db, suffix="one"):
    source = NewsSource(publisher_name="Status Test", rss_url=f"https://status-{suffix}.test/rss")
    db.add(source)
    db.flush()
    article = Article(
        source_id=source.id,
        headline="Status test article",
        original_url=f"https://status-{suffix}.test/story",
        category="Politics",
    )
    db.add(article)
    db.flush()
    return article


def create_draft(db, article, status, updated_at=None):
    draft = PostDraft(
        article_id=article.id,
        caption="Status test caption",
        template_id="modern",
        status=status,
        created_at=updated_at or datetime.now(timezone.utc),
        updated_at=updated_at or datetime.now(timezone.utc),
    )
    db.add(draft)
    db.flush()
    return draft


def test_article_status_uses_latest_draft_and_handles_multiple_history(db):
    article = create_article(db)
    create_draft(db, article, "FAILED", datetime.now(timezone.utc) - timedelta(hours=1))
    newest = create_draft(db, article, "APPROVED")
    db.commit()

    state = get_article_publishing_statuses(db, [article.id])[article.id]
    assert state["publishing_status"] == "APPROVED"
    assert state["publishing_draft_id"] == newest.id
    assert state["publication_record_id"] is None


def test_meta_publication_takes_precedence_over_failed_or_unresolved_drafts(db):
    article = create_article(db)
    failed = create_draft(db, article, "FAILED")
    create_draft(db, article, "PUBLISHING")
    db.add(PublishedPost(
        draft_id=failed.id,
        platform="facebook",
        platform_post_id="page_post_123",
        status="PUBLISHED",
        audit_metadata=json.dumps({"id": "page_post_123"}),
    ))
    db.commit()

    state = get_article_publishing_statuses(db, [article.id])[article.id]
    assert state["publishing_status"] == "PUBLISHED"
    assert state["publication_url"] == "https://facebook.com/page_post_123"


def test_manual_publication_is_distinct_and_only_trusted_facebook_urls_are_linked(db):
    article = create_article(db)
    draft = create_draft(db, article, "PUBLISHED")
    db.add(PublishedPost(
        draft_id=draft.id,
        platform="facebook_manual",
        platform_post_id="https://attacker.example/post",
        status="PUBLISHED",
    ))
    db.commit()

    state = get_article_publishing_statuses(db, [article.id])[article.id]
    assert state["publishing_status"] == "MANUALLY_RECORDED"
    assert state["publication_url"] is None
    assert state["publication_record_id"] is not None


def test_failed_or_uncertain_attempts_are_not_reported_as_published(db):
    failed_article = create_article(db, "failed")
    create_draft(db, failed_article, "FAILED")
    unresolved_article = create_article(db, "pending")
    pending = create_draft(db, unresolved_article, "PUBLISHING")
    # A record with a failure status does not prove publication.
    db.add(PublishedPost(draft_id=pending.id, platform="facebook", status="FAILED"))
    db.commit()

    states = get_article_publishing_statuses(db, [failed_article.id, unresolved_article.id])
    assert states[failed_article.id]["publishing_status"] == "FAILED"
    assert states[unresolved_article.id]["publishing_status"] == "PUBLISHING"


def test_list_articles_exposes_same_status_fields_for_dashboard_and_feed(client, db):
    client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
    client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})
    article = create_article(db)
    draft = create_draft(db, article, "READY_FOR_REVIEW")
    db.commit()

    response = client.get("/api/articles?page_size=10")
    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["id"] == article.id)
    assert item["publishing_status"] == "READY_FOR_REVIEW"
    assert item["publishing_draft_id"] == draft.id


def test_standard_draft_creation_is_blocked_after_manual_publication_or_unresolved_attempt(client, db):
    client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
    client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})
    published_articles = []
    for platform in ("facebook", "facebook_manual"):
        published_article = create_article(db, platform)
        published_draft = create_draft(db, published_article, "PUBLISHED")
        db.add(PublishedPost(
            draft_id=published_draft.id,
            platform=platform,
            platform_post_id=f"{platform}_post_1",
            status="PUBLISHED",
        ))
        published_articles.append(published_article)
    unresolved_article = create_article(db, "unresolved")
    create_draft(db, unresolved_article, "PUBLISHING")
    db.commit()

    for article in (*published_articles, unresolved_article):
        response = client.post("/api/drafts", json={"article_id": article.id})
        assert response.status_code == 409


def test_api_publish_of_second_draft_is_blocked_before_meta_request(client, db, monkeypatch):
    client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
    client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})
    article = create_article(db, "api-guard")
    existing = create_draft(db, article, "PUBLISHING")
    approved = create_draft(db, article, "APPROVED")
    db.commit()
    from unittest.mock import AsyncMock
    publish_mock = AsyncMock()
    monkeypatch.setattr("backend.app.services.publishing.meta.MetaClient.publish_photo_post", publish_mock)
    monkeypatch.setattr("backend.app.services.publishing.meta.MetaClient.is_configured", True)

    response = client.post(f"/api/publishing/{approved.id}")
    assert response.status_code == 409
    publish_mock.assert_not_awaited()
    assert db.query(PostDraft).filter_by(id=existing.id).one().status == "PUBLISHING"
