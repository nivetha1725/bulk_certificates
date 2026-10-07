from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (SQLite does not store timezones)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
