from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import engine


async def database_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def redis_ready() -> bool:
    client = Redis.from_url(get_settings().redis_url)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
