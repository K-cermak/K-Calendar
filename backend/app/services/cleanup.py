"""The nightly clean-up of rows nobody needs any more (SPEC 16)."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import CursorResult, delete, or_
from sqlalchemy.orm import Session

from app.models import AuthSession, Invite
from app.services import clock, reminders

LOG_KEEP = timedelta(days=30)


@dataclass
class Removed:
    sessions: int
    invites: int
    log_entries: int


def _count(result: object) -> int:
    return result.rowcount if isinstance(result, CursorResult) else 0


def run(db: Session) -> Removed:
    now = clock.now()
    sessions = db.execute(delete(AuthSession).where(AuthSession.expires_at_utc <= now))
    invites = db.execute(
        delete(Invite).where(or_(Invite.used_at_utc.is_not(None), Invite.expires_at_utc <= now))
    )
    log_entries = reminders.clean_up_log(db, LOG_KEEP)
    return Removed(_count(sessions), _count(invites), log_entries)
