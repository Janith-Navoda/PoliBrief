"""Persistent single-background storage for the Universal Custom Template."""
import io
import os
import re
import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps

from backend.app.core.config import settings

MAX_CUSTOM_TEMPLATE_BYTES = 10 * 1024 * 1024
MAX_CUSTOM_TEMPLATE_PIXELS = 25_000_000
UNIVERSAL_TEMPLATE_FILENAME = "universal_custom.png"
UNIVERSAL_TEMPLATE_ID = "universal_custom"
DEFAULT_HEADLINE_COLOR = "#FFFFFF"
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CustomTemplateValidationError(ValueError):
    """The uploaded file is not a supported square background image."""


class UniversalTemplateUnavailable(FileNotFoundError):
    """No active universal background is available for rendering."""


def template_kind(template_id: str | None) -> str:
    return (template_id or "modern").split("|", 1)[0].lower()


def headline_color_from_template_id(template_id: str | None) -> str:
    parts = (template_id or "").split("|")
    if len(parts) >= 2 and _HEX_COLOR_RE.fullmatch(parts[1]):
        return parts[1].upper()
    return DEFAULT_HEADLINE_COLOR


def hashtag_color_from_template_id(template_id: str | None) -> str:
    parts = (template_id or "").split("|")
    if len(parts) == 3 and _HEX_COLOR_RE.fullmatch(parts[2]):
        return parts[2].upper()
    return DEFAULT_HEADLINE_COLOR


def stored_template_id(
    template_id: str,
    headline_color: str | None = None,
    hashtag_color: str | None = None,
) -> str:
    if template_kind(template_id) != UNIVERSAL_TEMPLATE_ID:
        return template_kind(template_id)
    color = headline_color or headline_color_from_template_id(template_id)
    if not _HEX_COLOR_RE.fullmatch(color):
        raise CustomTemplateValidationError("Choose a valid six-digit headline color.")
    brand_color = hashtag_color or hashtag_color_from_template_id(template_id)
    if not _HEX_COLOR_RE.fullmatch(brand_color):
        raise CustomTemplateValidationError("Choose a valid six-digit hashtag color.")
    return f"{UNIVERSAL_TEMPLATE_ID}|{color.upper()}|{brand_color.upper()}"


def universal_template_path() -> Path:
    return settings.templates_dir / UNIVERSAL_TEMPLATE_FILENAME


def universal_template_info() -> dict:
    path = universal_template_path()
    if not path.is_file():
        return {"exists": False, "image_url": None, "width": None, "height": None}
    stat = path.stat()
    return {
        "exists": True,
        "image_url": f"/api/drafts/templates/universal-custom/image?v={stat.st_mtime_ns}",
        "width": 1080,
        "height": 1080,
        "updated_at": stat.st_mtime,
    }


def _validate_and_normalize(image_bytes: bytes) -> Image.Image:
    if not image_bytes:
        raise CustomTemplateValidationError("Choose a PNG or JPG image to upload.")
    if len(image_bytes) > MAX_CUSTOM_TEMPLATE_BYTES:
        raise CustomTemplateValidationError("Image must be 10 MB or smaller.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as source:
                if source.format not in {"PNG", "JPEG"}:
                    raise CustomTemplateValidationError("Only PNG and JPG/JPEG images are supported.")
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > MAX_CUSTOM_TEMPLATE_PIXELS:
                    raise CustomTemplateValidationError("Image dimensions exceed the supported limit.")
                if width != height:
                    raise CustomTemplateValidationError("Use a square image; non-square images are not cropped automatically.")
                if getattr(source, "n_frames", 1) != 1:
                    raise CustomTemplateValidationError("Animated images are not supported.")
                source.verify()

            with Image.open(io.BytesIO(image_bytes)) as source:
                normalized = ImageOps.exif_transpose(source).convert("RGBA")
                background = Image.new("RGBA", normalized.size, (255, 255, 255, 255))
                background.alpha_composite(normalized)
                rgb = background.convert("RGB")
                return rgb.resize((1080, 1080), Image.Resampling.LANCZOS)
    except CustomTemplateValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise CustomTemplateValidationError("Image dimensions exceed the safe processing limit.") from exc
    except Exception as exc:
        raise CustomTemplateValidationError("The uploaded file is not a valid PNG or JPG image.") from exc


def save_universal_template(image_bytes: bytes) -> dict:
    """Validate first, then atomically replace the active managed background."""
    normalized = _validate_and_normalize(image_bytes)
    destination = universal_template_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".universal-custom-{uuid.uuid4().hex}.tmp")
    try:
        normalized.save(staging, format="PNG", optimize=True)
        with staging.open("r+b") as staged_file:
            staged_file.flush()
            os.fsync(staged_file.fileno())
        os.replace(staging, destination)
    finally:
        normalized.close()
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
    return universal_template_info()


def remove_universal_template() -> bool:
    path = universal_template_path()
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
