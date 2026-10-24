"""Focused Stage 1 security and publishing regression tests."""
import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_secret_key_must_be_configured_and_not_use_the_example():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY="short")

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY="change-this-to-a-long-random-secret-key-minimum-32-chars",
        )

    settings = Settings(_env_file=None, SECRET_KEY="isolated-test-key-with-at-least-32-characters")
    assert len(settings.SECRET_KEY) >= 32
