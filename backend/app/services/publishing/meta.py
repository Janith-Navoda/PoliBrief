"""
PoliBrief Backend — Meta Graph API Client
Implements official Meta Graph API v21.0 integration for Facebook Page publishing.
Handles photo uploading, caption posting, connection validation, error handling,
and rate limit awareness.
"""
import json
import logging
from typing import Any, Optional
from pathlib import Path

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com"


class PublishOutcomeUnknown(RuntimeError):
    """The request may have reached Meta, but its result was not received safely."""


class MetaPublishRejected(RuntimeError):
    """Meta returned a definitive rejection response for a publish request."""

    def __init__(self, error_code: Any = None):
        self.error_code = error_code
        super().__init__(f"Meta rejected the publish request (code: {error_code}).")


class MetaClient:
    """Client for Meta Graph API v21.0 page operations."""

    def __init__(
        self,
        page_id: Optional[str] = None,
        page_token: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        self.page_id = page_id or settings.FACEBOOK_PAGE_ID
        self.page_token = page_token or settings.FACEBOOK_PAGE_ACCESS_TOKEN
        self.api_version = api_version or settings.META_API_VERSION or "v21.0"

    @property
    def is_configured(self) -> bool:
        """Check if essential credentials are set."""
        return bool(self.page_id and self.page_token)

    def get_base_url(self) -> str:
        return f"{GRAPH_API_BASE}/{self.api_version}"

    async def validate_connection(self) -> dict[str, Any]:
        """
        Validate Page ID and Page Access Token against Meta Graph API.
        Returns Page metadata if valid, or structured error details.
        """
        if not self.is_configured:
            return {
                "configured": False,
                "valid": False,
                "message": "Facebook Page ID or Page Access Token is not configured in .env",
            }

        url = f"{self.get_base_url()}/{self.page_id}"
        params = {"fields": "id,name,link,is_published,category"}
        headers = {"Authorization": f"Bearer {self.page_token}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                data = resp.json()

                if resp.status_code == 200:
                    return {
                        "configured": True,
                        "valid": True,
                        "page_id": data.get("id"),
                        "page_name": data.get("name"),
                        "page_link": data.get("link"),
                        "category": data.get("category"),
                        "is_published": data.get("is_published", True),
                        "message": f"Successfully connected to Facebook Page: {data.get('name')}",
                    }

                error_info = data.get("error", {})
                error_code = error_info.get("code")
                return {
                    "configured": True,
                    "valid": False,
                    "error_code": error_code,
                    "message": f"Meta Graph API rejected the connection check (code: {error_code}).",
                }
        except Exception as exc:
            logger.warning("Meta connection validation failed (%s).", type(exc).__name__)
            return {
                "configured": True,
                "valid": False,
                "message": "Meta connection validation failed due to a network or response error.",
            }

    async def publish_photo_post(
        self,
        image_path: str,
        caption: str,
    ) -> dict[str, Any]:
        """
        Upload and publish an image with caption to the configured Facebook Page.
        POST /{page_id}/photos with multipart/form-data.
        """
        if not self.is_configured:
            raise ValueError("Facebook Page ID or Page Access Token is missing.")

        img_file = Path(image_path)
        if not img_file.exists():
            raise FileNotFoundError(f"Generated image file not found: {image_path}")

        url = f"{self.get_base_url()}/{self.page_id}/photos"
        data = {
            "caption": caption,
            "published": "true",
        }
        headers = {"Authorization": f"Bearer {self.page_token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(img_file, "rb") as f:
                files = {"source": (img_file.name, f, "image/png")}
                try:
                    response = await client.post(url, data=data, files=files, headers=headers)
                except httpx.RequestError as exc:
                    raise PublishOutcomeUnknown(
                        "Meta's response was not received; check the Page before attempting another publish."
                    ) from exc

            try:
                res_data = response.json()
            except (ValueError, json.JSONDecodeError) as exc:
                raise PublishOutcomeUnknown(
                    "Meta returned an unreadable response; check the Page before attempting another publish."
                ) from exc
            if response.status_code == 200 and not res_data.get("error"):
                photo_id = res_data.get("id")
                post_id = res_data.get("post_id") or photo_id
                logger.info("Successfully published photo post to Facebook Page %s (ID: %s)", self.page_id, post_id)
                return {
                    "success": True,
                    "photo_id": photo_id,
                    "post_id": post_id,
                    "fb_url": f"https://facebook.com/{post_id}",
                    "raw_response": res_data,
                }

            error = res_data.get("error", {})
            err_code = error.get("code")
            if response.status_code >= 500:
                raise PublishOutcomeUnknown(
                    "Meta returned a server error; check the Page before attempting another publish."
                )
            logger.error("Meta Graph API photo upload rejected (code: %s).", err_code)
            raise MetaPublishRejected(err_code)
