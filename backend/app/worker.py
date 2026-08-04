from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()
celery = Celery("rss_ai", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_default_queue="rss_ai",
    timezone="UTC",
    broker_connection_retry_on_startup=True,
)


@celery.task(name="rss_ai.health_ping")
def health_ping() -> str:
    """Minimal task proving the Phase 0 worker can process a safe task."""

    return "ok"
