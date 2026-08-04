from __future__ import annotations

import sys

from redis import Redis

from app.config import get_settings


def main() -> int:
    """Container health command for Celery processes.

    Docker restarts a failed process; this check verifies that a running worker
    or scheduler can still reach the required Redis broker.
    """

    if len(sys.argv) != 2 or sys.argv[1] not in {"worker", "scheduler"}:
        return 2
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
    try:
        return 0 if client.ping() else 1
    except Exception:
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
