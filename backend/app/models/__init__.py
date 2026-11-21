"""Importing this package registers every model on Base.metadata (Alembic relies on it)."""

from app.models.account import AuthSession, Invite, Setting, User

__all__ = ["AuthSession", "Invite", "Setting", "User"]
