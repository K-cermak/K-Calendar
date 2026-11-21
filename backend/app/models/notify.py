from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import UtcDateTime


class Reminder(Base):
    """An offset before each occurrence of an event (SPEC 8). Always on a master or single event.

    For all-day events the offset counts from midnight in the user's zone, so "the day before at
    18:00" is 360 and "on the day at 09:00" is -540.
    """

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    minutes_before: Mapped[int]
    next_fire_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    # The occurrence the next firing is for: its original start, as a wall-clock time.
    next_occurrence_start: Mapped[datetime | None] = mapped_column(DateTime)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(2000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    last_success_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime)


class NotificationLog(Base):
    """One delivery of one occurrence's reminder on one channel; the unique key makes it once only."""

    __tablename__ = "notification_log"
    __table_args__ = (UniqueConstraint("reminder_id", "occurrence_start", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"))
    occurrence_start: Mapped[datetime] = mapped_column(DateTime)
    channel: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8))
    error: Mapped[str | None] = mapped_column(String(1000))
    attempts: Mapped[int] = mapped_column(default=0)
    sent_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
