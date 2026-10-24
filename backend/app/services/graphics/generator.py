"""
PoliBrief Backend — Social Media News Image Generator (Pillow)
Generates high-resolution, branded 1080x1080 PNG cards for Facebook news posts.
Implements 3 distinct template variants:
  1. 'modern'  — Modern General News (navy card, gold accents, sleek layout)
  2. 'breaking' — Breaking News (high-contrast crimson/gold alert banner)
  3. 'minimal' — Minimal Editorial (refined editorial serif/sans layout)
"""
import logging
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1080

# PoliBrief Brand Palette
COLOR_NAVY_DARK = (3, 7, 18)       # #030712 - ultra-deep background
COLOR_NAVY_CARD = (15, 23, 42)     # #0F172A - slate/navy card
COLOR_NAVY_SURFACE = (30, 41, 59)  # #1E293B - inner panels
COLOR_GOLD = (212, 175, 55)        # #D4AF37 - metallic gold
COLOR_GOLD_LIGHT = (245, 158, 11)  # #F59E0B - warm amber highlight
COLOR_CRIMSON = (220, 38, 38)      # #DC2626 - breaking news red
COLOR_WHITE = (248, 250, 252)      # #F8FAFC - crisp headline text
COLOR_OFFWHITE = (226, 232, 240)   # #E2E8F0 - secondary text
COLOR_MUTED = (148, 163, 184)      # #94A3B8 - metadata text
COLOR_BORDER = (51, 65, 85)        # #334155 - subtle card outline


def _load_font(font_name: str, size: int) -> ImageFont.ImageFont:
    """Safely load a TrueType font from Windows system fonts or fall back to default."""
    candidate_paths = [
        Path(f"C:/Windows/Fonts/{font_name}.ttf"),
        Path(f"C:/Windows/Fonts/{font_name.lower()}.ttf"),
        Path(f"C:/Windows/Fonts/segoeui.ttf"),
        Path(f"C:/Windows/Fonts/arial.ttf"),
        Path(f"C:/Windows/Fonts/calibri.ttf"),
    ]
    for p in candidate_paths:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap text to a maximum character width without breaking words."""
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False, max_lines=6)
    return lines or [text]


def _fit_headline(draw: ImageDraw.ImageDraw, headline: str, font_name: str,
                  preferred_size: int, max_width: int, max_height: int):
    """Wrap using actual font metrics and shrink until every headline line fits."""
    words = (headline or "Untitled story").split()
    for size in range(preferred_size, 11, -1):
        font = _load_font(font_name, size)
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # Keep even unusually long unbroken strings visible by splitting them.
            fragment = ""
            for char in word:
                if fragment and draw.textbbox((0, 0), fragment + char, font=font)[2] > max_width:
                    lines.append(fragment)
                    fragment = char
                else:
                    fragment += char
            current = fragment
        if current:
            lines.append(current)
        spacing = max(size + 5, int(size * 1.28))
        if lines and len(lines) * spacing <= max_height:
            return font, lines, spacing
    return font, lines, spacing


def _draw_fitted_headline(draw: ImageDraw.ImageDraw, headline: str, font_name: str,
                          preferred_size: int, box: tuple[int, int, int, int], fill):
    left, top, right, bottom = box
    font, lines, spacing = _fit_headline(
        draw, headline, font_name, preferred_size, right - left, bottom - top,
    )
    total_height = len(lines) * spacing
    y = top + max(0, (bottom - top - total_height) // 2)
    for line in lines:
        draw.text((left, y), line, font=font, fill=fill)
        y += spacing


def draw_rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width=1):
    """Draw a smooth rounded rectangle."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def render_modern_template(
    headline: str,
    publisher: str,
    category: str,
    date_str: str,
) -> Image.Image:
    """
    Template 1: Modern General News
    Deep navy gradient canvas, subtle grid/border, gold category pill, prominent wrapped headline.
    """
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_NAVY_DARK)
    draw = ImageDraw.Draw(img)

    # Outer decorative margin frame
    draw_rounded_rectangle(draw, (40, 40, 1040, 1040), radius=28, fill=COLOR_NAVY_CARD, outline=COLOR_BORDER, width=2)

    # Top brand bar
    font_brand = _load_font("segoeuib", 26)
    font_brand_sub = _load_font("segoeui", 16)
    draw.text((80, 80), "POLIBRIEF", font=font_brand, fill=COLOR_GOLD)
    draw.text((80, 114), "POLITICAL NEWS BRIEFING", font=font_brand_sub, fill=COLOR_MUTED)

    # Category Chip
    font_chip = _load_font("segoeuib", 18)
    cat_text = category.upper()
    cat_bbox = font_chip.getbbox(cat_text) if hasattr(font_chip, "getbbox") else (0, 0, 140, 20)
    chip_w = (cat_bbox[2] - cat_bbox[0]) + 32
    draw_rounded_rectangle(draw, (1040 - chip_w - 40, 82, 1040 - 40, 122), radius=12, fill=COLOR_NAVY_SURFACE, outline=COLOR_GOLD, width=1)
    draw.text((1040 - chip_w - 24, 91), cat_text, font=font_chip, fill=COLOR_GOLD)

    # Decorative accent line
    draw.line((80, 160, 1000, 160), fill=COLOR_BORDER, width=1)
    draw.line((80, 160, 240, 160), fill=COLOR_GOLD, width=3)

    # Headline text is fitted to the actual available pixel area.
    h_len = len(headline)
    if h_len < 70:
        font_size = 54
    elif h_len < 130:
        font_size = 44
    else:
        font_size = 38
    _draw_fitted_headline(draw, headline, "segoeuib", font_size, (80, 190, 1000, 865), COLOR_WHITE)

    # Bottom Metadata Panel
    draw_rounded_rectangle(draw, (80, 890, 1000, 990), radius=16, fill=COLOR_NAVY_SURFACE, outline=COLOR_BORDER, width=1)

    # Gold left accent bar on footer
    draw_rounded_rectangle(draw, (80, 890, 88, 990), radius=4, fill=COLOR_GOLD)

    font_pub = _load_font("segoeuib", 24)
    font_meta = _load_font("segoeui", 18)

    draw.text((115, 912), f"SOURCE: {publisher.upper()}", font=font_pub, fill=COLOR_OFFWHITE)
    draw.text((115, 948), f"PUBLISHED: {date_str} • POLIBRIEF.LOCAL", font=font_meta, fill=COLOR_MUTED)

    return img.convert("RGB")


def render_breaking_template(
    headline: str,
    publisher: str,
    category: str,
    date_str: str,
) -> Image.Image:
    """
    Template 2: Breaking News
    High-contrast emergency crimson banner, prominent alert badge, bold urgent styling.
    """
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_NAVY_DARK)
    draw = ImageDraw.Draw(img)

    # Outer border
    draw_rounded_rectangle(draw, (30, 30, 1050, 1050), radius=24, fill=COLOR_NAVY_CARD, outline=COLOR_CRIMSON, width=3)

    # Top Breaking Alert Header Block
    draw_rounded_rectangle(draw, (50, 50, 1030, 160), radius=16, fill=COLOR_CRIMSON)
    font_alert = _load_font("segoeuib", 38)
    font_alert_sub = _load_font("segoeuib", 18)
    draw.text((80, 72), "⚡ BREAKING REPORT", font=font_alert, fill=COLOR_WHITE)
    draw.text((80, 120), f"POLIBRIEF SPECIAL COVERAGE • {category.upper()}", font=font_alert_sub, fill=(254, 226, 226))

    # Headline
    h_len = len(headline)
    font_size = 50 if h_len < 80 else (42 if h_len < 140 else 36)
    _draw_fitted_headline(draw, headline, "segoeuib", font_size, (80, 180, 1000, 885), COLOR_WHITE)

    # Bottom citation badge
    draw_rounded_rectangle(draw, (80, 900, 1000, 990), radius=14, fill=COLOR_NAVY_SURFACE, outline=COLOR_CRIMSON, width=1)
    font_meta = _load_font("segoeuib", 22)
    font_date = _load_font("segoeui", 18)
    draw.text((110, 920), f"SOURCE: {publisher.upper()}", font=font_meta, fill=COLOR_GOLD)
    draw.text((110, 952), f"FILED: {date_str} • POLIBRIEF SUMMARY", font=font_date, fill=COLOR_MUTED)

    return img.convert("RGB")


def render_minimal_template(
    headline: str,
    publisher: str,
    category: str,
    date_str: str,
) -> Image.Image:
    """
    Template 3: Minimal Editorial
    Refined editorial quote-style design, elegant thin borders, clean typography.
    """
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (11, 19, 43))
    draw = ImageDraw.Draw(img)

    # Thin classic inner double border
    draw.rectangle((50, 50, 1030, 1030), outline=(71, 85, 105), width=1)
    draw.rectangle((60, 60, 1020, 1020), outline=COLOR_GOLD, width=1)

    # Top masthead
    font_masthead = _load_font("georgiab", 28)
    font_sub = _load_font("georgia", 16)
    draw.text((100, 95), "POLIBRIEF DISPATCH", font=font_masthead, fill=COLOR_WHITE)
    draw.text((100, 132), f"SECTION: {category.upper()} — ISSUE SUMMARY", font=font_sub, fill=COLOR_GOLD)

    # Quotation mark symbol
    font_quote = _load_font("georgia", 120)
    draw.text((95, 175), "“", font=font_quote, fill=(51, 65, 85))

    # Headline
    h_len = len(headline)
    font_size = 46 if h_len < 90 else (38 if h_len < 150 else 32)
    _draw_fitted_headline(draw, headline, "georgia", font_size, (100, 275, 980, 870), COLOR_OFFWHITE)

    # Bottom Editorial Citation
    draw.line((100, 890, 980, 890), fill=COLOR_GOLD, width=1)
    font_cite = _load_font("georgiab", 22)
    font_date = _load_font("georgia", 18)
    draw.text((100, 915), f"REPORTED BY {publisher.upper()}", font=font_cite, fill=COLOR_GOLD)
    draw.text((100, 950), f"Documented on {date_str} • PoliBrief Editorial Archive", font=font_date, fill=COLOR_MUTED)

    return img.convert("RGB")


def render_universal_custom_template(
    headline: str,
    headline_color: str = "#FFFFFF",
    hashtag_color: str = "#FFFFFF",
) -> Image.Image:
    """Render a lower-left news card over the saved universal background."""
    from backend.app.services.graphics.custom_template import (
        UniversalTemplateUnavailable,
        universal_template_path,
    )

    path = universal_template_path()
    if not path.is_file():
        raise UniversalTemplateUnavailable("No Universal Custom Template background has been uploaded.")

    with Image.open(path) as source:
        background = source.convert("RGBA")
    try:
        color = tuple(int(headline_color[index:index + 2], 16) for index in (1, 3, 5))
    except (TypeError, ValueError, IndexError):
        color = (255, 255, 255)
    luminance = (0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]) / 255
    light_text = luminance > 0.55
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # A graduated contrast veil gives arbitrary artwork a calm, readable text zone.
    overlay_color = (0, 0, 0) if light_text else (255, 255, 255)
    for y in range(500, 960):
        progress = (y - 500) / (960 - 500)
        alpha = int((progress ** 1.6) * (205 if light_text else 220))
        overlay_draw.line((0, y, 1079, y), fill=(*overlay_color, alpha))
    image = Image.alpha_composite(background, overlay)
    draw = ImageDraw.Draw(image)
    headline_font, lines, spacing = _fit_headline(
        draw, headline or "Untitled story", "segoeuib", 66, 850, 260,
    )
    total_height = len(lines) * spacing
    if total_height > 260 or any(draw.textbbox((0, 0), line, font=headline_font)[2] > 850 for line in lines):
        raise ValueError("Headline is too long to fit safely on the Universal Custom Template.")
    y = 885 - total_height
    stroke = (0, 0, 0, 235) if light_text else (255, 255, 255, 225)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=headline_font, stroke_width=2)
        draw.text(
            (76 - bbox[0], y), line, font=headline_font, fill=color,
            stroke_width=2, stroke_fill=stroke,
        )
        y += spacing

    # Keep only the small bottom-right brand; contrasting outline preserves visibility
    # without adding a footer panel or metadata strip.
    try:
        brand_rgb = tuple(int(hashtag_color[index:index + 2], 16) for index in (1, 3, 5))
    except (TypeError, ValueError, IndexError):
        brand_rgb = (255, 255, 255)
    hashtag_luminance = (0.2126 * brand_rgb[0] + 0.7152 * brand_rgb[1] + 0.0722 * brand_rgb[2]) / 255
    brand_stroke = (0, 0, 0, 235) if hashtag_luminance > 0.55 else (255, 255, 255, 230)
    brand_text = "#PoliBrief"
    brand_font = _load_font("segoeuib", 26)
    brand_anchor = (1010, 1035)
    draw.text(
        brand_anchor, brand_text, font=brand_font, fill=brand_rgb,
        anchor="rs", stroke_width=2, stroke_fill=brand_stroke,
    )
    return image.convert("RGB")


def generate_post_image(
    headline: str,
    publisher_name: str,
    category: str = "Government and Policy",
    published_at: Optional[datetime] = None,
    template_id: str = "modern",
    output_filename: Optional[str] = None,
) -> Path:
    """
    Main generator interface.
    Renders chosen template and saves high-resolution PNG to settings.generated_images_dir.
    Returns: Path to saved PNG file.
    """
    settings.generated_images_dir.mkdir(parents=True, exist_ok=True)

    # Date string formatting
    date_str = published_at.strftime("%B %d, %Y") if published_at else "DATE UNVERIFIED"

    # Select template renderer
    from backend.app.services.graphics.custom_template import (
        hashtag_color_from_template_id,
        headline_color_from_template_id,
        template_kind,
    )

    t_id = template_kind(template_id)
    if t_id == "breaking":
        img = render_breaking_template(headline, publisher_name, category, date_str)
    elif t_id == "minimal":
        img = render_minimal_template(headline, publisher_name, category, date_str)
    elif t_id == "universal_custom":
        img = render_universal_custom_template(
            headline,
            headline_color=headline_color_from_template_id(template_id),
            hashtag_color=hashtag_color_from_template_id(template_id),
        )
    else:
        img = render_modern_template(headline, publisher_name, category, date_str)

    # Filename creation
    if not output_filename:
        import uuid
        output_filename = f"post_{uuid.uuid4().hex[:12]}.png"
    elif not output_filename.endswith(".png"):
        output_filename = f"{output_filename}.png"

    dest_path = settings.generated_images_dir / output_filename
    img.save(dest_path, format="PNG", optimize=True)
    logger.info("Generated %s social graphic at: %s", t_id, dest_path)
    return dest_path
