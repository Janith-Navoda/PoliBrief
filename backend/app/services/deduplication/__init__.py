"""
PoliBrief Backend — Deduplication Package
"""
from backend.app.services.deduplication.matcher import (
    find_near_duplicate,
    find_related_stories,
    normalize_headline,
    SAME_PUBLISHER_DUPLICATE_THRESHOLD,
    CROSS_PUBLISHER_SIMILARITY_THRESHOLD,
)

__all__ = [
    "find_near_duplicate",
    "find_related_stories",
    "normalize_headline",
    "SAME_PUBLISHER_DUPLICATE_THRESHOLD",
    "CROSS_PUBLISHER_SIMILARITY_THRESHOLD",
]
