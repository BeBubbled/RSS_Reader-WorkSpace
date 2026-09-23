from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import Feed, Folder
from app.opml import export_opml, import_opml


@pytest.mark.asyncio
async def test_import_rejects_invalid_xml() -> None:
    with pytest.raises(ValueError, match="invalid"):
        await import_opml(AsyncMock(), "<not-valid-xml")


@pytest.mark.asyncio
async def test_export_includes_feeds_and_folders() -> None:
    folder = Folder(id=uuid4(), name="Tech")
    feed = Feed(id=uuid4(), title="Example", feed_url="https://example.com/feed", folder_id=folder.id)
    session = AsyncMock()
    folder_result = MagicMock(); folder_result.all = MagicMock(return_value=[folder])
    feed_result = MagicMock(); feed_result.all = MagicMock(return_value=[feed])
    session.scalars = AsyncMock(side_effect=[folder_result, feed_result])
    document = await export_opml(session)
    assert "Tech" in document
    assert "https://example.com/feed" in document
