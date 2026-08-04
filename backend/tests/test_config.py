import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_example_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(app_environment="production")


def test_allowed_origins_are_parsed_without_empty_values() -> None:
    settings = Settings(app_allowed_origins="https://rss.example, ,https://admin.example")
    assert settings.allowed_origins == ["https://rss.example", "https://admin.example"]
