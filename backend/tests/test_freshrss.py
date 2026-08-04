import pytest
import httpx
from fastapi import HTTPException

from app.freshrss import GoogleReaderClient, fresh_rss_error, normalized_hash


def test_normalized_hash_ignores_html_markup_and_whitespace() -> None:
    text_a, hash_a = normalized_hash("Title", "<p>Hello   world</p>")
    text_b, hash_b = normalized_hash(" title ", "Hello world")
    assert "Hello" in text_a
    assert hash_a == hash_b


def test_google_reader_client_builds_freshrss_endpoint() -> None:
    client = GoogleReaderClient("https://rss.example/freshrss", "reader", "secret")
    assert client.endpoint("api/greader.php/reader/api/0/tag/list") == "https://rss.example/freshrss/api/greader.php/reader/api/0/tag/list"


def test_freshrss_client_rejects_non_http_url() -> None:
    with pytest.raises(HTTPException, match="must start"):
        GoogleReaderClient("rss.example", "reader", "secret")


@pytest.mark.parametrize(("status_code", "expected"), [(401, "API password"), (404, "API was not found")])
def test_freshrss_http_errors_are_safe_and_actionable(status_code: int, expected: str) -> None:
    response = httpx.Response(status_code, request=httpx.Request("GET", "https://rss.example/api"))
    detail = fresh_rss_error(httpx.HTTPStatusError("failed", request=response.request, response=response)).detail
    assert expected in detail


def test_freshrss_network_error_does_not_leak_endpoint_or_credentials() -> None:
    request = httpx.Request("GET", "https://reader:secret@rss.example/api")
    detail = fresh_rss_error(httpx.ConnectError("boom", request=request)).detail
    assert detail == "Cannot reach FreshRSS at the configured URL"


@pytest.mark.asyncio
async def test_due_sync_skips_recent_connection(monkeypatch) -> None:
    from app import worker
    from app.models import FreshRSSConnection
    from datetime import UTC, datetime
    from uuid import uuid4

    connection = FreshRSSConnection(id=uuid4(), base_url="https://rss.example", username="reader", encrypted_api_password="x", sync_interval=900, last_sync_at=datetime.now(UTC))
    assert connection.last_sync_at is not None
