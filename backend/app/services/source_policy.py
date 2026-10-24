"""Small helpers for the structured source-use notes stored with RSS sources."""
import json
from typing import Any


def get_source_policy(article) -> dict[str, Any]:
    source = getattr(article, "source", None)
    raw_policy = getattr(source, "content_restrictions", None) if source else None
    if not raw_policy:
        return {}
    try:
        parsed = json.loads(raw_policy)
    except (TypeError, ValueError):
        return {"notes": raw_policy}
    return parsed if isinstance(parsed, dict) else {"notes": raw_policy}


def missing_required_attribution(article, caption: str | None) -> bool:
    if not get_source_policy(article).get("attribution_required"):
        return False
    source = getattr(article, "source", None)
    publisher = (getattr(source, "publisher_name", None) or "").strip()
    original_url = (getattr(article, "original_url", None) or "").strip()
    text = caption or ""
    return not publisher or publisher.casefold() not in text.casefold() or not original_url or original_url not in text
