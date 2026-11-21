"""Importing this package registers every model on Base.metadata (Alembic relies on it)."""

from app.models.account import AuthSession, Invite, Setting, User
from app.models.calendar import Calendar, CalendarSubscription, Event, EventTag, Tag

__all__ = [
    "AuthSession",
    "Calendar",
    "CalendarSubscription",
    "Event",
    "EventTag",
    "Invite",
    "Setting",
    "Tag",
    "User",
]
