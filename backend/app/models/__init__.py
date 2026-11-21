"""Importing this package registers every model on Base.metadata (Alembic relies on it)."""

from app.models.account import AuthSession, Invite, Setting, User
from app.models.calendar import Calendar, Event, EventTag, Tag

__all__ = ["AuthSession", "Calendar", "Event", "EventTag", "Invite", "Setting", "Tag", "User"]
