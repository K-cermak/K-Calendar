from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import AuthSession, User
from app.schemas.admin import AdminUser, AdminUserUpdate
from app.services.auth import sessions, totp


def _to_admin_user(user: User, last_seen: datetime | None) -> AdminUser:
    return AdminUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        has_password=user.password_hash is not None,
        totp_enabled=user.totp_enabled_at_utc is not None,
        oidc_linked=user.oidc_subject is not None,
        created_at_utc=user.created_at_utc,
        last_seen_at_utc=last_seen,
    )


def _last_seen(db: Session, user_id: int) -> datetime | None:
    return db.scalar(select(func.max(AuthSession.last_seen_at_utc)).where(AuthSession.user_id == user_id))


def list_users(db: Session) -> list[AdminUser]:
    last_seen = (
        select(AuthSession.user_id, func.max(AuthSession.last_seen_at_utc).label("last"))
        .group_by(AuthSession.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User, last_seen.c.last)
        .outerjoin(last_seen, last_seen.c.user_id == User.id)
        .order_by(User.created_at_utc)
    )
    return [_to_admin_user(user, last) for user, last in rows]


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError()
    return user


def _active_admins(db: Session) -> int:
    query = select(func.count()).select_from(User).where(User.is_admin, User.is_active)
    return db.scalar(query) or 0


def _guard(db: Session, actor: User | None, target: User, *, removes_admin: bool) -> None:
    """Refuse changes that lock an admin out or leave the instance without an active admin.

    actor is None for the CLI, which may change any account but still keeps one admin.
    """
    if actor is not None and actor.id == target.id:
        raise ConflictError("self_change", "You cannot do this to your own account here")
    if removes_admin and target.is_admin and target.is_active and _active_admins(db) <= 1:
        raise ConflictError("last_admin", "The instance must keep at least one active admin")


def update_user(db: Session, actor: User | None, user_id: int, update: AdminUserUpdate) -> AdminUser:
    user = _get(db, user_id)
    demote = update.is_admin is False and user.is_admin
    deactivate = update.is_active is False and user.is_active
    if demote or deactivate:
        _guard(db, actor, user, removes_admin=True)
    if update.is_admin is not None:
        user.is_admin = update.is_admin
    if update.is_active is not None:
        user.is_active = update.is_active
    if deactivate:
        sessions.revoke_all(db, user.id)
    db.commit()
    return _to_admin_user(user, None if deactivate else _last_seen(db, user.id))


def delete_user(db: Session, actor: User | None, user_id: int) -> None:
    user = _get(db, user_id)
    _guard(db, actor, user, removes_admin=True)
    # Everything the user owns goes with them through ON DELETE CASCADE.
    db.delete(user)
    db.commit()


def reset_totp(db: Session, user_id: int) -> None:
    """For a user who lost both the authenticator and the recovery codes."""
    totp.clear(db, _get(db, user_id))
    db.commit()
