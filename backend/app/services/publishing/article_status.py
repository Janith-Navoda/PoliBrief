"""Resolve the effective editorial/publication state for article cards."""
import re
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from backend.app.models import PostDraft, PublishedPost


_DRAFT_STATUSES = {"DRAFT", "READY_FOR_REVIEW", "APPROVED", "PUBLISHING", "FAILED"}


def _facebook_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname in {
            "facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch",
        }:
            return value
        return None
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,256}", value):
        return f"https://facebook.com/{value}"
    return None


def get_article_publishing_statuses(db: Session, article_ids: list[int]) -> dict[int, dict]:
    """Load publication and draft state in two bounded queries for a page of articles."""
    if not article_ids:
        return {}

    drafts = (
        db.query(PostDraft)
        .filter(PostDraft.article_id.in_(article_ids))
        .order_by(PostDraft.updated_at.desc(), PostDraft.id.desc())
        .all()
    )
    draft_ids = [draft.id for draft in drafts]
    publications = (
        db.query(PublishedPost)
        .filter(
            PublishedPost.draft_id.in_(draft_ids),
            PublishedPost.status == "PUBLISHED",
        )
        .order_by(PublishedPost.published_at.desc(), PublishedPost.id.desc())
        .all()
    ) if draft_ids else []

    drafts_by_article: dict[int, list[PostDraft]] = {}
    for draft in drafts:
        drafts_by_article.setdefault(draft.article_id, []).append(draft)
    draft_by_id = {draft.id: draft for draft in drafts}
    publications_by_article: dict[int, list[PublishedPost]] = {}
    for publication in publications:
        draft = draft_by_id.get(publication.draft_id)
        if draft:
            publications_by_article.setdefault(draft.article_id, []).append(publication)

    result = {}
    for article_id in article_ids:
        article_publications = publications_by_article.get(article_id, [])
        meta_publications = [p for p in article_publications if p.platform.lower() == "facebook"]
        manual_publications = [p for p in article_publications if p.platform.lower() == "facebook_manual"]
        if meta_publications:
            publication = meta_publications[0]
            status = "PUBLISHED"
        elif manual_publications:
            publication = manual_publications[0]
            status = "MANUALLY_RECORDED"
        else:
            publication = None
            article_drafts = drafts_by_article.get(article_id, [])
            publishing_drafts = [d for d in article_drafts if d.status == "PUBLISHING"]
            eligible_drafts = [d for d in article_drafts if d.status in _DRAFT_STATUSES]
            if publishing_drafts:
                draft = publishing_drafts[0]
                status = "PUBLISHING"
            elif eligible_drafts:
                draft = eligible_drafts[0]
                status = draft.status
            else:
                # A terminal PUBLISHED draft without an audit row is inconsistent; block
                # standard creation as unresolved instead of presenting a false success.
                orphaned_published = [d for d in article_drafts if d.status == "PUBLISHED"]
                draft = orphaned_published[0] if orphaned_published else None
                status = "PUBLISHING" if draft else "NONE"
        if publication:
            draft_id = publication.draft_id
            publication_id = publication.id
            publication_url = _facebook_url(publication.platform_post_id)
        else:
            draft_id = draft.id if draft else None
            publication_id = None
            publication_url = None
        result[article_id] = {
            "publishing_status": status,
            "publishing_draft_id": draft_id,
            "publication_record_id": publication_id,
            "publication_url": publication_url,
        }
    return result


def article_has_confirmed_or_unresolved_publication(
    db: Session, article_id: int, exclude_draft_id: int | None = None,
) -> bool:
    """Guard API publication/draft creation against article-level duplicates."""
    confirmed = (
        db.query(PublishedPost.id)
        .join(PostDraft, PostDraft.id == PublishedPost.draft_id)
        .filter(
            PostDraft.article_id == article_id,
            PublishedPost.status == "PUBLISHED",
            PublishedPost.platform.in_(("facebook", "facebook_manual")),
        )
        .first()
    )
    unresolved_query = db.query(PostDraft.id).filter(
        PostDraft.article_id == article_id,
        PostDraft.status.in_(("PUBLISHING", "PUBLISHED")),
    )
    if exclude_draft_id is not None:
        unresolved_query = unresolved_query.filter(PostDraft.id != exclude_draft_id)
    unresolved = unresolved_query.first()
    return bool(confirmed or unresolved)
