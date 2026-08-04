"""Safe OPML import/export for RSS-AI-owned subscriptions."""
from __future__ import annotations

import hashlib
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Feed, Folder


def _outline_title(node: ET.Element) -> str:
    return (node.attrib.get("title") or node.attrib.get("text") or "未命名文件夹").strip()


async def import_opml(session: AsyncSession, document: str) -> dict[str, int]:
    """Import only feed metadata. Article content remains owned by FreshRSS."""
    try:
        root = ET.fromstring(document)
    except ET.ParseError as error:
        raise ValueError("OPML XML is invalid") from error
    body = root.find("body")
    if body is None:
        raise ValueError("OPML document does not contain a body")

    counts = {"folders": 0, "feeds": 0}

    async def visit(parent: ET.Element, folder: Folder | None = None) -> None:
        for node in parent.findall("outline"):
            feed_url = (node.attrib.get("xmlUrl") or "").strip()
            if not feed_url:
                name = _outline_title(node)
                # OPML can repeat a folder name at different levels, so scope it
                # by its parent rather than merging unrelated folders.
                folder_key = "opml-folder:" + hashlib.sha256(f"{folder.id if folder else 'root'}:{name}".encode()).hexdigest()
                current = await session.scalar(select(Folder).where(Folder.connection_id.is_(None), Folder.freshrss_folder_id == folder_key))
                if not current:
                    current = Folder(connection_id=None, freshrss_folder_id=folder_key, name=name)
                    session.add(current)
                    await session.flush()
                counts["folders"] += 1
                await visit(node, current)
                continue
            feed_key = "opml:" + hashlib.sha256(feed_url.encode()).hexdigest()
            item = await session.scalar(select(Feed).where(Feed.connection_id.is_(None), Feed.freshrss_feed_id == feed_key))
            if not item:
                item = Feed(connection_id=None, freshrss_feed_id=feed_key, title=_outline_title(node))
                session.add(item)
            item.title = _outline_title(node)
            item.feed_url = feed_url
            item.site_url = node.attrib.get("htmlUrl") or None
            item.folder_id = folder.id if folder else None
            counts["feeds"] += 1

    await visit(body)
    await session.commit()
    return counts


async def export_opml(session: AsyncSession) -> str:
    # Export both imported feeds and FreshRSS mirrors. This makes it a genuine
    # application backup instead of an export of only one import source.
    folders = list((await session.scalars(select(Folder).order_by(Folder.name))).all())
    feeds = list((await session.scalars(select(Feed).order_by(Feed.title))).all())
    grouped: dict[object, list[Feed]] = {}
    for feed in feeds:
        grouped.setdefault(feed.folder_id, []).append(feed)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0"><head><title>RSS-AI subscriptions</title></head><body>']
    def feed_line(feed: Feed) -> str:
        attrs = f'text="{escape(feed.title, {"\"": "&quot;"})}" title="{escape(feed.title, {"\"": "&quot;"})}" type="rss" xmlUrl="{escape(feed.feed_url or "", {"\"": "&quot;"})}"'
        if feed.site_url:
            attrs += f' htmlUrl="{escape(feed.site_url, {"\"": "&quot;"})}"'
        return f"<outline {attrs} />"
    for feed in grouped.get(None, []):
        lines.append(feed_line(feed))
    for folder in folders:
        lines.append(f'<outline text="{escape(folder.name, {"\"": "&quot;"})}" title="{escape(folder.name, {"\"": "&quot;"})}">')
        lines.extend(feed_line(feed) for feed in grouped.get(folder.id, []))
        lines.append("</outline>")
    lines.append("</body></opml>")
    return "\n".join(lines)
