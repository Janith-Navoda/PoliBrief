"""
PoliBrief Backend — SQLAlchemy ORM Models
All tables in one file for Phase 1; will split as the project grows.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from backend.app.database.session import Base


def _utcnow():
    return datetime.now(timezone.utc)


# ─── Administrators ───────────────────────────────────────────────────────────

class Administrator(Base):
    __tablename__ = "administrators"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)


# ─── News Sources ─────────────────────────────────────────────────────────────

class NewsSource(Base):
    __tablename__ = "news_sources"

    id = Column(Integer, primary_key=True, index=True)
    publisher_name = Column(String(128), nullable=False)
    rss_url = Column(String(512), nullable=False, unique=True)
    website_url = Column(String(512), nullable=True)
    language = Column(String(10), default="en", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    last_checked = Column(DateTime(timezone=True), nullable=True)
    last_success = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="PENDING", nullable=False)
    error_message = Column(Text, nullable=True)
    content_restrictions = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    articles = relationship("Article", back_populates="source", passive_deletes=True)


# ─── Articles ─────────────────────────────────────────────────────────────────

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer,
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    headline = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    original_url = Column(String(1024), nullable=False)
    canonical_url = Column(String(1024), nullable=True)
    category = Column(String(64), default="Other / Needs Review", nullable=False)
    classification_score = Column(Float, default=0.0, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    fingerprint = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="ACTIVE", nullable=False, index=True)

    source = relationship("NewsSource", back_populates="articles")
    drafts = relationship("PostDraft", back_populates="article", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_article_canonical_url"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_status_expires", "status", "expires_at"),
    )


# ─── Post Drafts ──────────────────────────────────────────────────────────────

class PostDraft(Base):
    __tablename__ = "post_drafts"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    headline_override = Column(String(512), nullable=True)
    caption = Column(Text, nullable=True)
    template_id = Column(String(64), nullable=True)
    image_path = Column(String(512), nullable=True)
    status = Column(String(32), default="DRAFT", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    article = relationship("Article", back_populates="drafts")
    publications = relationship("PublishedPost", back_populates="draft", passive_deletes=True)


# ─── Published Posts ──────────────────────────────────────────────────────────

class PublishedPost(Base):
    __tablename__ = "published_posts"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(
        Integer,
        ForeignKey("post_drafts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    platform = Column(String(32), default="facebook", nullable=False)
    platform_post_id = Column(String(256), nullable=True)
    published_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    status = Column(String(32), default="PUBLISHED", nullable=False)
    audit_metadata = Column(Text, nullable=True)  # minimal JSON audit trail

    draft = relationship("PostDraft", back_populates="publications")


# ─── Duplicate Fingerprints ───────────────────────────────────────────────────

class DuplicateFingerprint(Base):
    __tablename__ = "duplicate_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


# ─── Job Logs ─────────────────────────────────────────────────────────────────

class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(128), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="RUNNING", nullable=False)
    error_message = Column(Text, nullable=True)

    __table_args__ = (Index("ix_job_logs_started_at", "started_at"),)


# ─── Application Settings ─────────────────────────────────────────────────────

class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)
