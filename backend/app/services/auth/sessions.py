from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import NotFoundError
from app.models import AuthSession, User
from app.schemas.account import SessionInfo
from app.services import clock
from app.services.auth import credentials

# Sliding the expiry on every request would turn every read into a write.
TOUCH_INTERVAL = timedelta(hours=1)


def create(
    db: Session, settings: Settings, user: User, *, method: str, user_agent: str | None, ip: str | None
) -> str:
    """Start a session and return its token, which is only ever stored as a hash."""
    token = credentials.new_token()
    now = clock.now()
    db.add(
        AuthSession(
            token_hash=credentials.hash_token(token),
            user_id=user.id,
            auth_method=method,
            created_at_utc=now,
            last_seen_at_utc=now,
            expires_at_utc=now + timedelta(days=settings.session_days),
            user_agent=(user_agent or "")[:300] or None,
            ip=ip,
        )
    )
    return token


def resolve(db: Session, token: str) -> tuple[AuthSession, User] | None:
    """The session and its user, read fresh on every request so deactivation applies at once."""
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == credentials.hash_token(token))
    ).first()
    if row is None:
        return None
    session, user = row
    if session.expires_at_utc <= clock.now() or not user.is_active:
        return None
    return session, user


def touch_due(session: AuthSession) -> bool:
    return clock.now() - session.last_seen_at_utc >= TOUCH_INTERVAL


def touch(db: Session, settings: Settings, session_id: int) -> None:
    session = db.get(AuthSession, session_id)
    if session is None:
        return
    now = clock.now()
    session.last_seen_at_utc = now
    session.expires_at_utc = now + timedelta(days=settings.session_days)
    db.commit()


def list_for(db: Session, user: User, current_id: int) -> list[SessionInfo]:
    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.expires_at_utc > clock.now())
        .order_by(AuthSession.last_seen_at_utc.desc())
    )
    return [
        SessionInfo(
            id=s.id,
            auth_method=s.auth_method,
            created_at_utc=s.created_at_utc,
            last_seen_at_utc=s.last_seen_at_utc,
            expires_at_utc=s.expires_at_utc,
            user_agent=s.user_agent,
            ip=s.ip,
            current=s.id == current_id,
        )
        for s in rows
    ]


def revoke(db: Session, user: User, session_id: int) -> None:
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user.id:
        raise NotFoundError()
    db.delete(session)
    db.commit()


def revoke_others(db: Session, user_id: int, keep_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.id != keep_id))


def revoke_all(db: Session, user_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
