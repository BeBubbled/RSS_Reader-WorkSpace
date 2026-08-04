from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import bleach
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Entry, Feed, Folder, FreshRSSConnection

READ_TAG = "user/-/state/com.google/read"
STARRED_TAG = "user/-/state/com.google/starred"


def crypt() -> Fernet:
    try:
        settings = get_settings()
        key = settings.app_encryption_key
        # Older Phase 0 .env files used this explanatory placeholder. Keep a
        # development upgrade path instead of making FreshRSS setup silently
        # impossible; production validation still rejects it.
        if key == "replace-with-a-fernet-key-generated-for-this-deployment" and settings.app_environment.lower() != "production":
            key = "lEgmaNLZbLEptAO6glxBrO5g2mES6wB6yMyGH0MnbE="
        return Fernet(key.encode())
    except ValueError as error:
        raise HTTPException(status_code=500, detail="APP_ENCRYPTION_KEY is invalid") from error


def encrypt_secret(value: str) -> str:
    return crypt().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return crypt().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise HTTPException(status_code=500, detail="Stored FreshRSS credential cannot be decrypted") from error


def normalized_hash(title: str, html: str) -> tuple[str, str]:
    text = bleach.clean(html, tags=[], strip=True)
    normalized = re.sub(r"\s+", " ", f"{title} {text}").strip().lower()
    return text, hashlib.sha256(normalized.encode()).hexdigest()


def fresh_rss_error(error: Exception) -> HTTPException:
    """Return a safe, actionable error for a FreshRSS network/API failure."""
    if isinstance(error, HTTPException):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        if code in (401, 403):
            detail = "FreshRSS rejected the username or Google Reader API password"
        elif code == 404:
            detail = "FreshRSS Google Reader API was not found at this URL; check the FreshRSS base URL and enable its API"
        else:
            detail = f"FreshRSS returned HTTP {code}"
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    if isinstance(error, httpx.TimeoutException):
        return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="FreshRSS request timed out")
    if isinstance(error, httpx.RequestError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cannot reach FreshRSS at the configured URL")
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="FreshRSS returned an invalid API response")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="FreshRSS synchronization failed")


class GoogleReaderClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="FreshRSS URL must start with http:// or https://")
        self.base_url = base_url.rstrip("/") + "/"
        self.username, self.password, self.token = username, password, None

    def endpoint(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    async def login(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(self.endpoint("api/greader.php/accounts/ClientLogin"), data={"Email": self.username, "Passwd": self.password, "service": "reader"})
                response.raise_for_status()
        except Exception as error:
            raise fresh_rss_error(error) from error
        auth = next((line[5:] for line in response.text.splitlines() if line.startswith("Auth=")), None)
        if not auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="FreshRSS did not return a Google Reader token")
        self.token = auth

    async def get(self, path: str, params: dict[str, str | int | None] | None = None) -> dict:
        if not self.token:
            await self.login()
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.endpoint(path), params=clean_params, headers={"Authorization": f"GoogleLogin auth={self.token}"})
                response.raise_for_status()
                return response.json()
        except Exception as error:
            raise fresh_rss_error(error) from error

    async def subscriptions(self) -> list[dict]:
        return (await self.get("api/greader.php/reader/api/0/subscription/list", {"output": "json"})).get("subscriptions", [])

    async def tags(self) -> list[dict]:
        return (await self.get("api/greader.php/reader/api/0/tag/list", {"output": "json"})).get("tags", [])

    async def entries(self, continuation: str | None = None, count: int = 1000) -> dict:
        return await self.get("api/greader.php/reader/api/0/stream/contents/user/-/state/com.google/reading-list", {"output": "json", "n": count, "c": continuation})


async def sync_connection(session: AsyncSession, connection: FreshRSSConnection, max_entries: int = 2000) -> dict[str, int]:
    client = GoogleReaderClient(connection.base_url, connection.username, decrypt_secret(connection.encrypted_api_password))
    connection.status = "syncing"; await session.commit()
    counts = {"folders": 0, "feeds": 0, "entries": 0}; folders: dict[str, Folder] = {}
    try:
        for tag in await client.tags():
            tag_id, name = tag.get("id", ""), tag.get("id", "").rsplit("/", 1)[-1]
            if not tag_id or "state/com.google" in tag_id: continue
            item = await session.scalar(select(Folder).where(Folder.connection_id == connection.id, Folder.freshrss_folder_id == tag_id))
            if not item: item = Folder(connection_id=connection.id, freshrss_folder_id=tag_id, name=name); session.add(item)
            else: item.name = name
            folders[tag_id] = item; counts["folders"] += 1
        await session.flush()
        feeds: dict[str, Feed] = {}
        for raw in await client.subscriptions():
            feed_id = raw["id"]; category = next((c.get("id") for c in raw.get("categories", []) if c.get("id") in folders), None)
            item = await session.scalar(select(Feed).where(Feed.connection_id == connection.id, Feed.freshrss_feed_id == feed_id))
            if not item: item = Feed(connection_id=connection.id, freshrss_feed_id=feed_id, title=raw.get("title", feed_id)); session.add(item)
            item.title, item.feed_url, item.site_url, item.folder_id = raw.get("title", feed_id), raw.get("url"), raw.get("htmlUrl"), folders.get(category).id if category else None
            feeds[feed_id] = item; counts["feeds"] += 1
        await session.flush(); continuation = None
        while counts["entries"] < max_entries:
            payload = await client.entries(continuation, min(1000, max_entries - counts["entries"]))
            for raw in payload.get("items", []):
                feed = feeds.get(raw.get("origin", {}).get("streamId"));
                if not feed: continue
                title, html = raw.get("title", "(untitled)"), raw.get("content", raw.get("summary", {})).get("content", "")
                text, content_hash = normalized_hash(title, html); entry_id = str(raw.get("id", ""))
                if not entry_id: continue
                item = await session.scalar(select(Entry).where(Entry.connection_id == connection.id, Entry.freshrss_entry_id == entry_id))
                published = datetime.fromtimestamp(int(raw.get("published", 0)), tz=UTC)
                if not item: item = Entry(connection_id=connection.id, freshrss_entry_id=entry_id, feed_id=feed.id, title=title, published_at=published, content_hash=content_hash); session.add(item)
                item.feed_id, item.title, item.url, item.author, item.published_at, item.content_html, item.content_text, item.content_hash = feed.id, title, raw.get("canonical", [{}])[0].get("href", raw.get("alternate", [{}])[0].get("href")), raw.get("author"), published, html, text, content_hash
                categories = raw.get("categories", []); item.is_read, item.is_starred = READ_TAG in categories, STARRED_TAG in categories; counts["entries"] += 1
            continuation = payload.get("continuation")
            if not continuation: break
        connection.last_sync_at, connection.status = datetime.now(UTC), "ok"; await session.commit(); return counts
    except Exception as error:
        # Credentials are deliberately never persisted in diagnostics.
        connection.status = "error"
        # The message is useful to the owner (wrong URL/API password) but strip
        # all URL credentials and cap it before writing it to the database.
        message = fresh_rss_error(error).detail
        connection.last_error = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://***:***@", message)[:500]
        await session.commit()
        raise
