"""
PoliBrief Backend — Facebook / Meta Graph API Publishing Router
Endpoints for verifying Page connection credentials, publishing approved drafts,
and viewing publication history.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.database.session import get_db
from backend.app.models import Administrator, JobLog, PostDraft, PublishedPost
from backend.app.services.source_policy import missing_required_attribution
from backend.app.schemas.publishing import (
    MetaStatusOut,
    PublishResolution,
    PublishResultOut,
    PublishedPostOut,
)
from backend.app.services.publishing.meta import MetaClient, MetaPublishRejected
from backend.app.services.publishing.article_status import article_has_confirmed_or_unresolved_publication

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/status", response_model=MetaStatusOut)
async def get_meta_status(
    admin: Administrator = Depends(get_current_admin),
):
    """Inspect Meta Facebook credentials and validate Page access token."""
    client = MetaClient()
    res = await client.validate_connection()
    return MetaStatusOut(
        configured=res.get("configured", False),
        valid=res.get("valid", False),
        page_id=res.get("page_id"),
        page_name=res.get("page_name"),
        page_link=res.get("page_link"),
        category=res.get("category"),
        message=res.get("message", "Status checked"),
    )


@router.post("/{draft_id}", response_model=PublishResultOut)
async def publish_draft_to_facebook(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """
    Publish an approved post draft to the connected Facebook Page via Meta Graph API v21.0.
    Enforces that the draft MUST have status == 'APPROVED'.
    """
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    # Recorded success or a previous request with uncertain outcome must never be retried here.
    existing_publication = db.query(PublishedPost).filter(PublishedPost.draft_id == draft.id).first()
    if existing_publication or draft.status in {"PUBLISHED", "PUBLISHING"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This draft is already published or has a publish request with an unresolved outcome. "
                "Reconcile it before another attempt."
            ),
        )

    if draft.article and article_has_confirmed_or_unresolved_publication(
        db, draft.article_id, exclude_draft_id=draft.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another draft for this article is already published or has an unresolved publishing outcome.",
        )

    # Mandatory rule: Administrator approval required
    if draft.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish draft with status '{draft.status}'. Only APPROVED drafts can be published.",
        )

    if draft.article and missing_required_attribution(draft.article, draft.caption):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source attribution is required before API publishing.",
        )

    if not draft.image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft does not have a rendered image graphic.",
        )

    from pathlib import Path
    if not Path(draft.image_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft image is missing from storage.",
        )

    client = MetaClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook Page ID or Page Access Token is not configured. Use manual export instead.",
        )

    now = datetime.now(timezone.utc)
    # An atomic compare-and-set claims the draft before the network call. This is durable
    # across workers/restarts and makes a concurrent request lose before reaching Meta.
    claimed = db.query(PostDraft).filter(
        PostDraft.id == draft.id,
        PostDraft.status == "APPROVED",
    ).update(
        {PostDraft.status: "PUBLISHING", PostDraft.updated_at: now},
        synchronize_session=False,
    )
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft state changed; reload and try again.")
    if draft.article and article_has_confirmed_or_unresolved_publication(
        db, draft.article_id, exclude_draft_id=draft.id,
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another draft for this article has an unresolved publishing outcome. No Facebook request was sent.",
        )
    db.commit()

    try:
        publish_res = await client.publish_photo_post(
            image_path=draft.image_path,
            caption=draft.caption or "",
        )

        post_id = publish_res.get("post_id")
        fb_url = publish_res.get("fb_url")

    except MetaPublishRejected as exc:
        db.rollback()
        db.query(PostDraft).filter(
            PostDraft.id == draft.id,
            PostDraft.status == "PUBLISHING",
        ).update(
            {PostDraft.status: "FAILED", PostDraft.updated_at: datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        db.commit()
        logger.error("Facebook publishing rejected for draft #%d (code: %s).", draft.id, exc.error_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Meta rejected the publish request. Review the draft before approving a retry.",
        )
    except Exception as exc:
        # Keep PUBLISHING persisted: the request may have reached Meta even if no response
        # or local result was safely recorded. Only the explicit reconciliation route unlocks it.
        db.rollback()
        logger.warning("Facebook publish outcome unresolved for draft #%d (%s).", draft.id, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "draft_id": draft.id,
                "status": "PUBLISHING",
                "detail": "The publish outcome is uncertain. Check the Page and reconcile this draft before retrying.",
                "resolution_endpoint": f"/api/publishing/{draft.id}/resolve",
            },
        )

    # A successful Meta response is not enough to enable a retry if local persistence fails.
    try:
        draft.status = "PUBLISHED"
        draft.updated_at = datetime.now(timezone.utc)
        pub_record = PublishedPost(
            draft_id=draft.id,
            platform="facebook",
            platform_post_id=post_id,
            published_at=draft.updated_at,
            status="PUBLISHED",
            audit_metadata=json.dumps(publish_res.get("raw_response", {})),
        )
        db.add(pub_record)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Facebook succeeded but local result could not be recorded for draft #%d (%s).", draft.id, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "draft_id": draft.id,
                "status": "PUBLISHING",
                "detail": "Meta may have published this post, but the local result was not recorded. Reconcile before retrying.",
                "resolution_endpoint": f"/api/publishing/{draft.id}/resolve",
            },
        )

    logger.info("Draft #%d published successfully to Facebook (Post ID: %s)", draft.id, post_id)
    return PublishResultOut(
        success=True,
        draft_id=draft.id,
        platform="facebook",
        platform_post_id=post_id,
        fb_url=fb_url,
        published_at=draft.updated_at,
        message="Successfully published post to Facebook Page!",
    )


@router.post("/{draft_id}/resolve")
def resolve_uncertain_publish(
    draft_id: int,
    payload: PublishResolution,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Require an administrator to check the Page before resolving a pending publish attempt."""
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    if draft.status != "PUBLISHING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft has no unresolved publish attempt.")

    now = datetime.now(timezone.utc)
    if payload.outcome == "CONFIRMED_PUBLISHED":
        if db.query(PublishedPost).filter(PublishedPost.draft_id == draft.id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A publication record already exists.")
        next_status = "PUBLISHED"
    else:
        next_status = "APPROVED"

    resolved = db.query(PostDraft).filter(
        PostDraft.id == draft.id,
        PostDraft.status == "PUBLISHING",
    ).update(
        {PostDraft.status: next_status, PostDraft.updated_at: now},
        synchronize_session=False,
    )
    if resolved != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft state changed; reload and reconcile again.")

    if payload.outcome == "CONFIRMED_PUBLISHED":
        db.add(PublishedPost(
            draft_id=draft.id,
            platform="facebook",
            platform_post_id=payload.platform_post_id.strip(),
            published_at=now,
            status="PUBLISHED",
            audit_metadata=json.dumps({"resolution": "administrator_confirmed_published"}),
        ))
    else:
        db.add(JobLog(
            job_name="facebook_publish_resolution",
            started_at=now,
            finished_at=now,
            status="CONFIRMED_NOT_PUBLISHED",
            error_message=f"Administrator confirmed no Page post exists for draft #{draft.id}.",
        ))

    db.commit()
    draft.status = next_status
    draft.updated_at = now
    db.refresh(draft)
    return {"draft_id": draft.id, "status": draft.status, "detail": "Publish outcome reconciled by administrator."}


@router.get("/history", response_model=list[PublishedPostOut])
def get_publication_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Retrieve publication history and audit logs."""
    posts = (
        db.query(PublishedPost)
        .order_by(PublishedPost.published_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for p in posts:
        headline = None
        publisher = None
        category = None
        caption = None
        image_url = None

        if p.draft:
            caption = p.draft.caption
            image_url = f"/api/drafts/{p.draft.id}/image" if p.draft.image_path else None
            if p.draft.article:
                headline = p.draft.headline_override or p.draft.article.headline
                category = p.draft.article.category
                publisher = p.draft.article.source.publisher_name if p.draft.article.source else "News Source"

        fb_link = None
        if p.platform_post_id:
            if p.platform_post_id.startswith("http"):
                fb_link = p.platform_post_id
            else:
                fb_link = f"https://facebook.com/{p.platform_post_id}"

        results.append(PublishedPostOut(
            id=p.id,
            draft_id=p.draft_id,
            platform=p.platform,
            platform_post_id=p.platform_post_id,
            published_at=p.published_at,
            status=p.status,
            headline=headline,
            publisher_name=publisher,
            category=category,
            caption=caption,
            image_url=image_url,
            fb_link=fb_link,
        ))

    return results
