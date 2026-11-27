"""Instance limits an admin sets in the administration rather than through the environment (SPEC 14)."""

from sqlalchemy.orm import Session

from app.models import Setting

SESSION_DAYS = "session_days"

DEFAULTS = {SESSION_DAYS: 180}


def _get(db: Session, key: str) -> int:
    row = db.get(Setting, key)
    return int(row.value) if row is not None else DEFAULTS[key]


def set_value(db: Session, key: str, value: int) -> None:
    db.merge(Setting(key=key, value=str(value)))


def session_days(db: Session) -> int:
    return _get(db, SESSION_DAYS)
