from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import UtcDateTime


class Calendar(Base):
    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16), default="local")
    is_visible: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    feed_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    default_reminder_minutes: Mapped[int | None]


class Event(Base):
    """A single event, the master of a series, or an override of one occurrence (SPEC 4).

    start_local and end_local are what the user meant: wall-clock times in timezone, or midnights
    for all-day events, which have no zone. The *_utc columns are derived from them for queries.
    """

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("calendar_id", "uid", "original_start"),
        # SQLite treats NULLs as distinct, so the constraint above does not cover masters.
        Index(
            "uq_events_master_uid",
            "calendar_id",
            "uid",
            unique=True,
            sqlite_where=text("original_start IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str | None] = mapped_column(String(16))
    all_day: Mapped[bool] = mapped_column(default=False)
    start_local: Mapped[datetime] = mapped_column(DateTime)
    end_local: Mapped[datetime] = mapped_column(DateTime)
    timezone: Mapped[str | None] = mapped_column(String(64))
    start_utc: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    end_utc: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    rrule: Mapped[str | None] = mapped_column(Text)
    exdates: Mapped[list[Any]] = mapped_column(JSON, default=list)
    series_end_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)
    recurring_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    original_start: Mapped[datetime | None] = mapped_column(DateTime)
    sequence: Mapped[int] = mapped_column(default=0)
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class Tag(Base):
    __tablename__ = "tags"
    # name_key is the case-folded name: SQLite's own lower() only folds ASCII (SPEC 7, 9).
    __table_args__ = (UniqueConstraint("user_id", "name_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(16))


class EventTag(Base):
    __tablename__ = "event_tags"

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True
    )
