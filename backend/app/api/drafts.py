"""
PoliBrief Backend — Post Drafts & Studio API Router
Endpoints for generating social news images, editing drafts, approval workflows,
image downloads, and manual publication exports.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_admin
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models import Administrator, Article, PostDraft, PublishedPost
from backend.app.schemas.draft import (
    DraftArticleSummary,
    DraftCreate,
    DraftOut,
    DraftUpdate,
    PreviewResponse,
)
from backend.app.services.captions.generator import generate_facebook_caption
from backend.app.services.graphics.generator import generate_post_image
from backend.app.services.graphics.custom_template import (
    MAX_CUSTOM_TEMPLATE_BYTES,
    CustomTemplateValidationError,
    UniversalTemplateUnavailable,
    headline_color_from_template_id,
    hashtag_color_from_template_id,
    remove_universal_template,
    save_universal_template,
    stored_template_id,
    template_kind,
    universal_template_info,
    universal_template_path,
)
from backend.app.services.source_policy import missing_required_attribution
from backend.app.services.publishing.article_status import article_has_confirmed_or_unresolved_publication

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _format_draft_out(draft: PostDraft) -> DraftOut:
    """Format PostDraft ORM object to DraftOut Pydantic schema with article metadata."""
    out = DraftOut.model_validate(draft)
    out.image_url = f"/api/drafts/{draft.id}/image" if draft.image_path else None
    out.template_id = template_kind(draft.template_id)
    out.headline_color = headline_color_from_template_id(draft.template_id)
    out.hashtag_color = hashtag_color_from_template_id(draft.template_id)
    if draft.article:
        out.article = DraftArticleSummary(
            id=draft.article.id,
            headline=draft.article.headline,
            original_url=draft.article.original_url,
            category=draft.article.category,
            publisher_name=draft.article.source.publisher_name if draft.article.source else "Unknown",
            published_at=draft.article.published_at,
        )
    return out


class PreviewRequest(BaseModel):
    article_id: int
    headline_override: Optional[str] = Field(default=None, max_length=512)
    template_id: str = "modern"
    headline_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    hashtag_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")


def _require_universal_template(template_id: str) -> None:
    if template_kind(template_id) == "universal_custom" and not universal_template_path().is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No Universal Custom Template background is uploaded. Upload one in Post Studio first.",
        )


@router.get("/templates/universal-custom")
def get_universal_template(
    admin: Administrator = Depends(get_current_admin),
):
    """Return the active custom background's availability and authenticated preview URL."""
    return universal_template_info()


@router.post("/templates/universal-custom/upload")
async def upload_universal_template(
    file: UploadFile = File(...),
    admin: Administrator = Depends(get_current_admin),
):
    """Validate and atomically replace the single persistent universal background."""
    image_bytes = await file.read(MAX_CUSTOM_TEMPLATE_BYTES + 1)
    if len(image_bytes) > MAX_CUSTOM_TEMPLATE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image must be 10 MB or smaller.")
    try:
        template = save_universal_template(image_bytes)
    except CustomTemplateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"detail": "Universal Custom Template background saved.", "template": template}


@router.delete("/templates/universal-custom")
def delete_universal_template(
    admin: Administrator = Depends(get_current_admin),
):
    """Remove only the active source background; generated images remain untouched."""
    removed = remove_universal_template()
    return {
        "detail": "Universal Custom Template background removed." if removed else "No custom background was uploaded.",
        **universal_template_info(),
    }


@router.get("/templates/universal-custom/image")
def get_universal_template_image(
    admin: Administrator = Depends(get_current_admin),
):
    """Serve the private managed background to the authenticated Post Studio."""
    path = universal_template_path()
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No custom template background is uploaded.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=0, must-revalidate"})


@router.get("", response_model=list[DraftOut])
def list_drafts(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: Optional[int] = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """List editorial drafts, optionally filtered by status (DRAFT, APPROVED, PUBLISHED)."""
    query = db.query(PostDraft).order_by(PostDraft.updated_at.desc())
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(PostDraft.status == status_filter.upper())
    if limit is not None:
        query = query.limit(limit)
    drafts = query.all()
    return [_format_draft_out(d) for d in drafts]


@router.post("", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: DraftCreate,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """
    Create a new Post Draft from an article.
    Automatically generates the 1080x1080 Pillow news graphic and draft caption.
    """
    article = db.query(Article).filter(Article.id == payload.article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")

    if article_has_confirmed_or_unresolved_publication(db, article.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This article has a confirmed publication or unresolved publishing outcome. Review its existing draft or publication record.",
        )

    publisher_name = article.source.publisher_name if article.source else "News Source"
    headline = payload.headline_override.strip() if payload.headline_override else article.headline

    # Auto-generate caption if not provided
    caption = payload.caption
    if not caption or not caption.strip():
        caption = generate_facebook_caption(
            headline=headline,
            publisher_name=publisher_name,
            original_url=article.original_url,
            description=article.description,
            category=article.category,
        )
    if missing_required_attribution(article, caption):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This source requires its publisher name and original link in the caption.",
        )

    effective_template_id = stored_template_id(payload.template_id, payload.headline_color, payload.hashtag_color)
    _require_universal_template(effective_template_id)

    # Render Pillow News Image Card
    image_filename = f"draft_{uuid.uuid4().hex[:12]}.png"
    try:
        img_path = generate_post_image(
            headline=headline,
            publisher_name=publisher_name,
            category=article.category,
            published_at=article.published_at,
            template_id=effective_template_id,
            output_filename=image_filename,
        )
    except UniversalTemplateUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    draft = PostDraft(
        article_id=article.id,
        headline_override=payload.headline_override.strip() if payload.headline_override else None,
        caption=caption,
        template_id=effective_template_id,
        image_path=str(img_path),
        status="DRAFT",
        created_at=now,
        updated_at=now,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return _format_draft_out(draft)


@router.post("/preview", response_model=PreviewResponse)
def generate_live_preview(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Generate a live preview of the image card and caption without saving a draft record."""
    article = db.query(Article).filter(Article.id == payload.article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")

    publisher_name = article.source.publisher_name if article.source else "News Source"
    headline = payload.headline_override.strip() if payload.headline_override else article.headline

    caption = generate_facebook_caption(
        headline=headline,
        publisher_name=publisher_name,
        original_url=article.original_url,
        description=article.description,
        category=article.category,
    )

    effective_template_id = stored_template_id(payload.template_id, payload.headline_color, payload.hashtag_color)
    _require_universal_template(effective_template_id)

    preview_filename = f"preview_{uuid.uuid4().hex[:10]}.png"
    try:
        generate_post_image(
            headline=headline,
            publisher_name=publisher_name,
            category=article.category,
            published_at=article.published_at,
            template_id=effective_template_id,
            output_filename=preview_filename,
        )
    except UniversalTemplateUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return PreviewResponse(
        image_url=f"/api/drafts/preview-file/{preview_filename}",
        caption=caption,
        headline=headline,
        template_id=template_kind(effective_template_id),
    )


@router.get("/preview-file/{filename}")
def get_preview_image(
    filename: str,
    admin: Administrator = Depends(get_current_admin),
):
    """Serve a preview image file."""
    safe_name = os.path.basename(filename)
    path = settings.generated_images_dir / safe_name
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return FileResponse(path, media_type="image/png")


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Retrieve draft details by ID."""
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    return _format_draft_out(draft)


@router.put("/{draft_id}", response_model=DraftOut)
def update_draft(
    draft_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """
    Update post draft content.
    If headline_override or template_id is updated, the social graphic is automatically regenerated.
    """
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    original_status = draft.status
    if draft.status in {"PUBLISHING", "PUBLISHED", "CANCELLED"} and any(
        value is not None for value in (
            payload.headline_override, payload.caption, payload.template_id,
            payload.headline_color, payload.hashtag_color,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft content cannot be edited while it is '{draft.status}'.",
        )

    requested_template_id = payload.template_id or draft.template_id or "modern"
    if template_kind(requested_template_id) == "universal_custom":
        selected_color = payload.headline_color or headline_color_from_template_id(draft.template_id)
        selected_hashtag_color = payload.hashtag_color or hashtag_color_from_template_id(draft.template_id)
        if payload.headline_color is not None or payload.hashtag_color is not None or payload.template_id is not None:
            requested_template_id = stored_template_id(requested_template_id, selected_color, selected_hashtag_color)
        else:
            requested_template_id = draft.template_id

    content_changed = (
        (payload.headline_override is not None and payload.headline_override.strip() != (draft.headline_override or ""))
        or (payload.caption is not None and payload.caption != draft.caption)
        or requested_template_id != draft.template_id
    )

    proposed_caption = payload.caption if payload.caption is not None else draft.caption
    if draft.article and missing_required_attribution(draft.article, proposed_caption):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This source requires its publisher name and original link in the caption.",
        )

    requested_regeneration = (
        (payload.headline_override is not None and payload.headline_override != draft.headline_override)
        or requested_template_id != draft.template_id
    )
    if requested_regeneration:
        _require_universal_template(requested_template_id)

    regenerate_needed = False

    if payload.headline_override is not None and payload.headline_override != draft.headline_override:
        draft.headline_override = payload.headline_override.strip() if payload.headline_override else None
        regenerate_needed = True

    if requested_template_id != draft.template_id:
        draft.template_id = requested_template_id
        regenerate_needed = True

    if payload.caption is not None:
        draft.caption = payload.caption

    if payload.status is not None:
        allowed_transitions = {
            "DRAFT": {"READY_FOR_REVIEW", "CANCELLED"},
            "READY_FOR_REVIEW": {"DRAFT", "CANCELLED"},
            "APPROVED": {"DRAFT", "CANCELLED"},
            "FAILED": {"CANCELLED"},
        }
        target_status = payload.status.strip().upper()
        if target_status != draft.status and target_status not in allowed_transitions.get(draft.status, set()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Draft cannot transition from '{draft.status}' to '{target_status}'. "
                    "Use the approval or publishing action for those transitions."
                ),
            )
        draft.status = target_status

    # Approval applies to the exact content reviewed. Any subsequent content edit
    # invalidates that approval and requires the explicit approve action again.
    if original_status == "APPROVED" and content_changed:
        draft.status = "DRAFT"
        draft.approved_at = None
    elif original_status == "APPROVED" and draft.status != "APPROVED":
        draft.approved_at = None

    now = datetime.now(timezone.utc)
    draft.updated_at = now

    if regenerate_needed and draft.article:
        headline = draft.headline_override or draft.article.headline
        publisher_name = draft.article.source.publisher_name if draft.article.source else "News Source"
        new_filename = f"draft_{uuid.uuid4().hex[:12]}.png"
        try:
            img_path = generate_post_image(
                headline=headline,
                publisher_name=publisher_name,
                category=draft.article.category,
                published_at=draft.article.published_at,
                template_id=draft.template_id or "modern",
                output_filename=new_filename,
            )
        except UniversalTemplateUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        # Safely remove previous image if it exists
        if draft.image_path and os.path.exists(draft.image_path):
            try:
                os.remove(draft.image_path)
            except OSError:
                pass
        draft.image_path = str(img_path)

    db.commit()
    db.refresh(draft)
    return _format_draft_out(draft)


@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Approve post draft for publishing."""
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    if draft.status not in {"DRAFT", "READY_FOR_REVIEW", "FAILED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft cannot be approved from status '{draft.status}'.",
        )

    if draft.article and missing_required_attribution(draft.article, draft.caption):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add the required publisher attribution and original link before approval.",
        )

    now = datetime.now(timezone.utc)
    draft.status = "APPROVED"
    draft.approved_at = now
    draft.updated_at = now
    db.commit()
    db.refresh(draft)
    return _format_draft_out(draft)


@router.get("/{draft_id}/image")
def get_draft_image(
    draft_id: int,
    download: bool = Query(False),
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Serve or download the generated PNG card for this draft."""
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft or not draft.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found for this draft.")

    path = Path(draft.image_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file missing from storage.")

    filename = f"polibrief_post_{draft.id}.png" if download else path.name
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if download else None
    return FileResponse(path, media_type="image/png", headers=headers)


@router.post("/{draft_id}/mark-published", response_model=DraftOut)
def mark_published(
    draft_id: int,
    platform_post_id: Optional[str] = Query(None, description="Optional external Facebook Post URL or ID"),
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """
    Mark an approved draft as manually published (for offline/manual export workflows).
    Creates an audit record in published_posts.
    """
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    if draft.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft cannot be marked as manually published from status '{draft.status}'.",
        )

    if draft.article and article_has_confirmed_or_unresolved_publication(
        db, draft.article_id, exclude_draft_id=draft.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another draft for this article is already published or has an unresolved publishing outcome.",
        )

    if draft.article and missing_required_attribution(draft.article, draft.caption):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add the required publisher attribution and original link before recording publication.",
        )

    existing_publication = db.query(PublishedPost).filter(
        PublishedPost.draft_id == draft.id
    ).first()
    if existing_publication:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A publication record already exists for this draft.",
        )

    now = datetime.now(timezone.utc)
    claimed = db.query(PostDraft).filter(
        PostDraft.id == draft.id,
        PostDraft.status == "APPROVED",
    ).update(
        {PostDraft.status: "PUBLISHED", PostDraft.updated_at: now},
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
            detail="Another draft for this article has an unresolved publishing outcome.",
        )

    pub = PublishedPost(
        draft_id=draft.id,
        platform="facebook_manual",
        platform_post_id=platform_post_id,
        published_at=now,
        status="PUBLISHED",
        audit_metadata='{"method": "manual_export", "administrator_confirmed": true}',
    )
    db.add(pub)
    db.commit()
    draft.status = "PUBLISHED"
    draft.updated_at = now
    db.refresh(draft)
    return _format_draft_out(draft)


@router.delete("/{draft_id}", status_code=status.HTTP_200_OK)
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: Administrator = Depends(get_current_admin),
):
    """Delete a post draft and clean up its associated image file."""
    draft = db.query(PostDraft).filter(PostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    if draft.status == "PUBLISHING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft cannot be deleted while a Facebook publishing outcome is unresolved.",
        )

    has_publication = db.query(PublishedPost.id).filter(
        PublishedPost.draft_id == draft.id
    ).first() is not None
    if draft.status == "PUBLISHED" or has_publication:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft has retained publication history and cannot be deleted. View the publication record instead.",
        )

    image_path = draft.image_path
    db.delete(draft)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.info("Draft #%d deletion blocked by retained database references.", draft_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft is referenced by retained records and cannot be deleted.",
        ) from exc

    # Only unlink after the database confirms deletion. If unlinking fails, the
    # normal orphan-image retention pass can safely retry later.
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError as exc:
            logger.warning("Draft #%d was deleted but its image cleanup failed (%s).", draft_id, type(exc).__name__)
    return {"detail": "Draft deleted successfully."}
