from __future__ import annotations

import uuid
from datetime import datetime

import bleach
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Entry, Feed, Folder, ReadingPosition

SAFE_TAGS = {"a", "article", "b", "blockquote", "br", "code", "del", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul"}
SAFE_ATTRIBUTES = {"a": ["href", "title"], "img": ["src", "alt", "title"], "*": ["class"]}


def sanitize_article_html(content: str | None) -> str:
    return bleach.clean(content or "", tags=SAFE_TAGS, attributes=SAFE_ATTRIBUTES, protocols={"http", "https", "mailto"}, strip=True)


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class FeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    folder_id: uuid.UUID | None
    site_url: str | None


class EntryOut(BaseModel):
    id: uuid.UUID
    feed_id: uuid.UUID
    title: str
    url: str | None
    author: str | None
    published_at: datetime
    content_html: str
    content_text: str | None
    is_read: bool
    is_starred: bool
    reading_position: float = 0.0


class EntryListOut(BaseModel):
    items: list[EntryOut]
    next_cursor: str | None


class EntryStatePatch(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None


class ReadingPositionPatch(BaseModel):
    scroll_ratio: float = Field(ge=0, le=1)


def as_entry_out(entry: Entry) -> EntryOut:
    return EntryOut(
        id=entry.id,
        feed_id=entry.feed_id,
        title=entry.title,
        url=entry.url,
        author=entry.author,
        published_at=entry.published_at,
        content_html=sanitize_article_html(entry.content_html),
        content_text=entry.content_text,
        is_read=entry.is_read,
        is_starred=entry.is_starred,
        reading_position=entry.reading_position.scroll_ratio if entry.reading_position else 0,
    )


async def get_entry_or_404(session: AsyncSession, entry_id: uuid.UUID) -> Entry:
    entry = await session.scalar(select(Entry).options(selectinload(Entry.reading_position)).where(Entry.id == entry_id))
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


async def list_entries(session: AsyncSession, *, feed_id: uuid.UUID | None, folder_id: uuid.UUID | None, is_read: bool | None, is_starred: bool | None, cursor: uuid.UUID | None, limit: int) -> EntryListOut:
    query: Select[tuple[Entry]] = select(Entry).options(selectinload(Entry.reading_position)).order_by(Entry.published_at.desc(), Entry.id.desc())
    if feed_id:
        query = query.where(Entry.feed_id == feed_id)
    if folder_id:
        query = query.join(Feed).where(Feed.folder_id == folder_id)
    if is_read is not None:
        query = query.where(Entry.is_read == is_read)
    if is_starred is not None:
        query = query.where(Entry.is_starred == is_starred)
    if cursor:
        cursor_entry = await session.scalar(select(Entry).where(Entry.id == cursor))
        if cursor_entry:
            query = query.where((Entry.published_at < cursor_entry.published_at) | ((Entry.published_at == cursor_entry.published_at) & (Entry.id < cursor_entry.id)))
    result = (await session.scalars(query.limit(limit + 1))).all()
    next_cursor = str(result[limit].id) if len(result) > limit else None
    return EntryListOut(items=[as_entry_out(entry) for entry in result[:limit]], next_cursor=next_cursor)


async def save_reading_position(session: AsyncSession, entry: Entry, ratio: float) -> Entry:
    if entry.reading_position:
        entry.reading_position.scroll_ratio = ratio
    else:
        entry.reading_position = ReadingPosition(scroll_ratio=ratio)
    await session.commit()
    await session.refresh(entry, attribute_names=["reading_position"])
    return entry
