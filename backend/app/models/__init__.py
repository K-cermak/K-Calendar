"""Importing this package registers every model on Base.metadata (Alembic relies on it)."""

from app.models.account import ApiToken, AuthSession, Invite, RecoveryCode, Setting, User
from app.models.calendar import Calendar, CalendarSubscription, Event, EventTag, Tag
from app.models.notify import NotificationLog, PushSubscription, Reminder

__all__ = [
    "ApiToken",
    "AuthSession",
    "Calendar",
    "CalendarSubscription",
    "Event",
    "EventTag",
    "Invite",
    "NotificationLog",
    "PushSubscription",
    "RecoveryCode",
    "Reminder",
    "Setting",
    "Tag",
    "User",
]
