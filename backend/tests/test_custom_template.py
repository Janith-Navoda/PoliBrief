"""Isolated tests for persistent Universal Custom Template storage and rendering."""
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image, ImageDraw

from backend.app.core.config import settings
from backend.app.services.graphics import generator
from backend.app.services.graphics.custom_template import (
    CustomTemplateValidationError,
    remove_universal_template,
    save_universal_template,
    universal_template_info,
    universal_template_path,
)


def make_image_bytes(color, fmt="PNG", size=(1080, 1080)):
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format=fmt)
    return output.getvalue()


def use_temp_template_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TEMPLATES_PATH", str(tmp_path / "managed-templates"))


class TestUniversalTemplateStorage:
    def test_valid_png_and_jpeg_are_saved_as_one_persistent_template(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)

        first = save_universal_template(make_image_bytes((180, 20, 20), "PNG"))
        path = universal_template_path()
        first_bytes = path.read_bytes()
        assert first["exists"] is True
        assert first["width"] == first["height"] == 1080
        assert Image.open(path).format == "PNG"

        replacement = save_universal_template(make_image_bytes((20, 40, 190), "JPEG"))
        # Re-reading through a fresh service call simulates process restart persistence.
        assert universal_template_info()["exists"] is True
        assert replacement["image_url"] == universal_template_info()["image_url"]
        assert path.read_bytes() != first_bytes
        with Image.open(path) as saved:
            assert saved.getpixel((20, 20))[2] > saved.getpixel((20, 20))[0]

    def test_rejects_corrupt_non_square_and_unsupported_images_without_replacing_active_file(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        save_universal_template(make_image_bytes((20, 120, 40)))
        path = universal_template_path()
        original = path.read_bytes()

        invalid_inputs = [
            b"not an image",
            make_image_bytes((20, 20, 20), size=(500, 300)),
            make_image_bytes((20, 20, 20), "BMP"),
        ]
        for invalid in invalid_inputs:
            try:
                save_universal_template(invalid)
            except CustomTemplateValidationError:
                pass
            else:
                raise AssertionError("invalid image should have been rejected")
            assert path.read_bytes() == original

    def test_removal_only_removes_active_background(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        save_universal_template(make_image_bytes((60, 70, 80)))
        path = universal_template_path()

        assert remove_universal_template() is True
        assert not path.exists()
        assert remove_universal_template() is False

    def test_custom_background_is_outside_generated_image_retention_directory(self, monkeypatch, tmp_path, db):
        use_temp_template_storage(monkeypatch, tmp_path)
        image = save_universal_template(make_image_bytes((60, 70, 80)))
        template_path = universal_template_path()
        assert settings.generated_images_dir not in template_path.parents

        from backend.app.services.cleanup.retention import clean_orphaned_images
        clean_orphaned_images(db, datetime.now(timezone.utc))
        assert image["exists"] is True
        assert template_path.exists()

    def test_replacing_background_changes_future_render_only(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
        save_universal_template(make_image_bytes((190, 30, 30)))

        first_path = generator.generate_post_image(
            "First custom story", "Test Publisher", template_id="universal_custom", output_filename="first.png"
        )
        first_snapshot = first_path.read_bytes()
        first_background_pixel = Image.open(first_path).getpixel((20, 20))

        save_universal_template(make_image_bytes((20, 50, 200), "JPEG"))
        second_path = generator.generate_post_image(
            "Second custom story", "Test Publisher", template_id="universal_custom", output_filename="second.png"
        )

        assert first_path.read_bytes() == first_snapshot
        assert first_background_pixel[0] > first_background_pixel[2]
        assert Image.open(second_path).getpixel((20, 20))[2] > Image.open(second_path).getpixel((20, 20))[0]
        with Image.open(second_path) as rendered:
            assert rendered.size == (1080, 1080)
            # Center panel and footer are present while outer artwork remains visible.
            assert rendered.getpixel((20, 20)) != rendered.getpixel((540, 535))
            brand_region = [rendered.getpixel((x, y)) for y in range(990, 1060) for x in range(850, 1030)]
            assert sum(1 for r, g, b in brand_region if r > 220 and g > 220 and b > 220) > 20

    def test_custom_renderer_wraps_lower_left_headline_and_uses_selected_color(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
        save_universal_template(make_image_bytes((35, 80, 140)))
        long_headline = "A long political headline that wraps into multiple readable lines " * 3
        _, wrapped_lines, _ = generator._fit_headline(
            ImageDraw.Draw(Image.new("RGB", (1080, 1080))),
            long_headline, "segoeuib", 66, 850, 260,
        )
        assert len(wrapped_lines) > 1

        output = generator.generate_post_image(
            long_headline, "Test Publisher", template_id="universal_custom|#FFD400",
            output_filename="yellow-headline.png",
        )
        with Image.open(output) as rendered:
            assert rendered.size == (1080, 1080)
            yellow_pixels = [
                (x, y) for y in range(500, 920) for x in range(30, 820)
                if (lambda pixel: pixel[0] > 180 and pixel[1] > 130 and pixel[2] < 100)(rendered.getpixel((x, y)))
            ]
            assert len(yellow_pixels) > 100
            assert min(y for _, y in yellow_pixels) > 500
            # Branding remains clearly visible at the lower-right edge.
            brand_region = [rendered.getpixel((x, y)) for y in range(970, 1035) for x in range(860, 1035)]
            assert sum(1 for r, g, b in brand_region if r > 220 and g > 220 and b > 220) > 20

    def test_custom_renderer_has_no_footer_metadata_and_has_independent_brand_color(self, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
        base_color = (35, 80, 140)
        save_universal_template(make_image_bytes(base_color))

        output = generator.generate_post_image(
            "A readable headline in yellow", "Hidden Source", template_id="universal_custom|#FFD400|#00FFCC",
            output_filename="separate-colors.png",
        )
        with Image.open(output) as rendered:
            assert rendered.getpixel((20, 1000)) == base_color
            metadata_area = [rendered.getpixel((x, y)) for y in range(970, 1070) for x in range(30, 800)]
            assert all(pixel == base_color for pixel in metadata_area)
            brand_region = [rendered.getpixel((x, y)) for y in range(970, 1050) for x in range(850, 1040)]
            assert sum(1 for r, g, b in brand_region if g > 170 and b > 130 and r < 100) > 20

    def test_builtin_template_renderer_still_generates_square_graphic(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
        output = generator.generate_post_image(
            "Built in template remains unchanged", "Test Publisher", template_id="breaking",
            output_filename="builtin-breaking.png",
        )
        with Image.open(output) as rendered:
            assert rendered.size == (1080, 1080)

    def test_legacy_custom_draft_keeps_headline_color_and_defaults_brand_to_white(self):
        from backend.app.services.graphics.custom_template import (
            hashtag_color_from_template_id,
            headline_color_from_template_id,
        )
        assert headline_color_from_template_id("universal_custom|#FFD400") == "#FFD400"
        assert hashtag_color_from_template_id("universal_custom|#FFD400") == "#FFFFFF"


class TestUniversalTemplateAPI:
    def _login(self, client):
        client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
        client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})

    def test_template_management_requires_admin(self, client, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        response = client.post(
            "/api/drafts/templates/universal-custom/upload",
            files={"file": ("background.png", make_image_bytes((10, 20, 30)), "image/png")},
        )
        assert response.status_code == 401
        assert not universal_template_path().exists()

    def test_admin_can_upload_view_replace_and_remove_background(self, client, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        self._login(client)

        uploaded = client.post(
            "/api/drafts/templates/universal-custom/upload",
            files={"file": ("background.png", make_image_bytes((30, 90, 140)), "image/png")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["template"]["exists"] is True

        image_response = client.get("/api/drafts/templates/universal-custom/image")
        assert image_response.status_code == 200
        assert image_response.headers["content-type"].startswith("image/png")

        replaced = client.post(
            "/api/drafts/templates/universal-custom/upload",
            files={"file": ("replacement.jpg", make_image_bytes((140, 50, 20), "JPEG"), "image/jpeg")},
        )
        assert replaced.status_code == 200
        assert replaced.json()["template"]["exists"] is True

        removed = client.delete("/api/drafts/templates/universal-custom")
        assert removed.status_code == 200
        assert removed.json()["exists"] is False

    def test_api_rejects_invalid_image_content_and_non_square_image(self, client, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        self._login(client)

        for name, data in [
            ("fake.png", b"not a png"),
            ("wide.png", make_image_bytes((20, 20, 20), size=(640, 480))),
        ]:
            response = client.post(
                "/api/drafts/templates/universal-custom/upload",
                files={"file": (name, data, "image/png")},
            )
            assert response.status_code == 422
            assert not universal_template_path().exists()

    def test_api_rejects_oversized_upload_without_creating_template(self, client, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        self._login(client)

        from backend.app.services.graphics.custom_template import MAX_CUSTOM_TEMPLATE_BYTES
        response = client.post(
            "/api/drafts/templates/universal-custom/upload",
            files={"file": ("large.png", b"x" * (MAX_CUSTOM_TEMPLATE_BYTES + 1), "image/png")},
        )
        assert response.status_code == 413
        assert not universal_template_path().exists()

    def test_custom_template_preview_requires_an_uploaded_background(self, client, db, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        self._login(client)
        from backend.app.models import Article, NewsSource
        source = NewsSource(publisher_name="Test Source", rss_url="https://example.test/rss")
        db.add(source)
        db.flush()
        article = Article(
            source_id=source.id,
            headline="Test headline",
            original_url="https://example.test/story",
            category="Politics",
        )
        db.add(article)
        db.commit()
        response = client.post(
            "/api/drafts/preview",
            json={"article_id": article.id, "template_id": "universal_custom"},
        )
        assert response.status_code == 409

    def test_preview_uses_selected_headline_color_and_wraps_lower_left(self, client, db, monkeypatch, tmp_path):
        use_temp_template_storage(monkeypatch, tmp_path)
        save_universal_template(make_image_bytes((35, 80, 140)))
        self._login(client)

        from backend.app.models import Article, NewsSource
        source = NewsSource(publisher_name="Preview Test", rss_url="https://preview-color.test/rss")
        db.add(source)
        db.flush()
        article = Article(
            source_id=source.id,
            headline="A long political headline that should wrap into multiple lines " * 3,
            original_url="https://preview-color.test/story",
            category="Politics",
        )
        db.add(article)
        db.commit()

        captured_template = {}
        original_generate = generator.generate_post_image
        def capture_template(*args, **kwargs):
            captured_template["template_id"] = kwargs.get("template_id")
            return original_generate(*args, **kwargs)
        monkeypatch.setattr("backend.app.api.drafts.generate_post_image", capture_template)

        preview = client.post("/api/drafts/preview", json={
            "article_id": article.id,
            "template_id": "universal_custom",
            "headline_color": "#FFD400",
            "hashtag_color": "#00FFCC",
        })
        assert preview.status_code == 200
        assert captured_template["template_id"] == "universal_custom|#FFD400|#00FFCC"
        image_response = client.get(preview.json()["image_url"])
        assert image_response.status_code == 200
        with Image.open(BytesIO(image_response.content)).convert("RGB") as rendered:
            assert rendered.size == (1080, 1080)
            headline_pixels = [rendered.getpixel((x, y)) for y in range(500, 920) for x in range(30, 820)]
            yellow_count = sum(1 for r, g, b in headline_pixels if r > 180 and g > 130 and b < 100)
            assert yellow_count > 100
            brand_pixels = [rendered.getpixel((x, y)) for y in range(970, 1050) for x in range(850, 1040)]
            assert sum(1 for r, g, b in brand_pixels if g > 170 and b > 130 and r < 100) > 20

        created = client.post("/api/drafts", json={
            "article_id": article.id,
            "template_id": "universal_custom",
            "headline_color": "#FFD400",
            "hashtag_color": "#00FFCC",
        })
        assert created.status_code == 201
        assert created.json()["template_id"] == "universal_custom"
        assert created.json()["headline_color"] == "#FFD400"
        assert created.json()["hashtag_color"] == "#00FFCC"
        from backend.app.models import PostDraft
        assert db.query(PostDraft).filter_by(id=created.json()["id"]).one().template_id == "universal_custom|#FFD400|#00FFCC"

