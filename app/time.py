"""UTC defaults preserving the existing naive-UTC database/API representation."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
