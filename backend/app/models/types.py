from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """An aware UTC datetime, stored naive in UTC.

    SQLite has no time zone type. Storing every instant naive in UTC keeps the text in the
    column sortable, so range queries and indexes on *_utc columns work.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UtcDateTime needs an aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        assert isinstance(value, datetime)
        return value.replace(tzinfo=UTC)
