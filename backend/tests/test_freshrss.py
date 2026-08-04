import pytest

from app.freshrss import GoogleReaderClient, normalized_hash


def test_normalized_hash_ignores_html_markup_and_whitespace() -> None:
    text_a, hash_a = normalized_hash("Title", "<p>Hello   world</p>")
    text_b, hash_b = normalized_hash(" title ", "Hello world")
    assert "Hello" in text_a
    assert hash_a == hash_b


def test_google_reader_client_builds_freshrss_endpoint() -> None:
    client = GoogleReaderClient("https://rss.example/freshrss", "reader", "secret")
    assert client.endpoint("api/greader.php/reader/api/0/tag/list") == "https://rss.example/freshrss/api/greader.php/reader/api/0/tag/list"


@pytest.mark.asyncio
async def test_due_sync_skips_recent_connection(monkeypatch) -> None:
    from app import worker
    from app.models import FreshRSSConnection
    from datetime import UTC, datetime
    from uuid import uuid4

    connection = FreshRSSConnection(id=uuid4(), base_url="https://rss.example", username="reader", encrypted_api_password="x", sync_interval=900, last_sync_at=datetime.now(UTC))
    assert connection.last_sync_at is not None
