import logging
from datetime import timedelta
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    TooManyRequestsError,
)
from app.models import Invite, User
from app.schemas.admin import CreatedLink, PendingInvite
from app.services import accounts, clock, instance, smtp
from app.services.auth import credentials
from app.services.auth.throttle import LoginThrottle
from app.services.notify import email
from app.services.reminders import DeliveryError

logger = logging.getLogger(__name__)

INVITE_LIFETIME = timedelta(days=7)
RESET_LIFETIME = timedelta(hours=24)

Purpose = Literal["invite", "reset"]


class InvalidLinkError(AppError):
    def __init__(self) -> None:
        super().__init__(404, "invalid_link", "This link is invalid, has expired or has already been used")


def _create(
    db: Session,
    settings: Settings,
    *,
    purpose: Purpose,
    created_by: User | None,
    email: str | None = None,
    user_id: int | None = None,
) -> CreatedLink:
    token = credentials.new_token()
    now = clock.now()
    invite = Invite(
        token_hash=credentials.hash_token(token),
        purpose=purpose,
        email=email,
        user_id=user_id,
        created_by=created_by.id if created_by else None,
        created_at_utc=now,
        expires_at_utc=now + (INVITE_LIFETIME if purpose == "invite" else RESET_LIFETIME),
    )
    db.add(invite)
    db.commit()
    return CreatedLink(
        id=invite.id, url=f"{settings.base_url}/{purpose}/{token}", expires_at_utc=invite.expires_at_utc
    )


def create_invite(db: Session, settings: Settings, admin: User, address: str | None) -> CreatedLink:
    normalized = accounts.normalize_email(address) if address else None
    if normalized and accounts.get_by_email(db, normalized):
        raise ConflictError("email_taken", "An account with this e-mail address already exists")
    link = _create(db, settings, purpose="invite", created_by=admin, email=normalized)
    if normalized and smtp.enabled(db):
        # The link is shown either way, so a mail server that refuses is not an error here.
        try:
            email.send_link(db, settings, admin.locale, normalized, "invite", link.url)
            link.emailed = True
        except DeliveryError as exc:
            logger.warning("Invite e-mail could not be sent: %s", exc)
    return link


def request_reset(db: Session, settings: Settings, throttle: LoginThrottle, *, email: str, ip: str) -> None:
    if not smtp.enabled(db):
        raise ForbiddenError("email_disabled", "Ask your administrator for a reset link")
    retry_after = throttle.retry_after(f"reset:{ip}", ip)
    if retry_after:
        raise TooManyRequestsError(retry_after)
    # Every request counts against the address, so the endpoint cannot be used to flood a mailbox.
    throttle.failed(f"reset:{ip}", ip)
    user = accounts.get_by_email(db, email)
    if user is None or not user.is_active or user.password_hash is None:
        return
    link = create_reset_link(db, settings, None, user.id)
    try:
        _send_reset(db, settings, user, link.url)
    except DeliveryError as exc:
        # The answer must look the same either way; the admin finds the failure in the log.
        logger.warning("Password reset e-mail could not be sent: %s", exc)


def _send_reset(db: Session, settings: Settings, user: User, url: str) -> None:
    email.send_link(db, settings, user.locale, user.email, "reset", url)


def create_reset_link(db: Session, settings: Settings, admin: User | None, user_id: int) -> CreatedLink:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError()
    # Only the newest reset link for a user works.
    db.execute(
        update(Invite)
        .where(Invite.purpose == "reset", Invite.user_id == user.id, Invite.used_at_utc.is_(None))
        .values(used_at_utc=clock.now())
    )
    return _create(db, settings, purpose="reset", created_by=admin, email=user.email, user_id=user.id)


def _find(db: Session, token: str, purpose: Purpose) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == credentials.hash_token(token)))
    if invite is None or invite.purpose != purpose or invite.used_at_utc is not None:
        raise InvalidLinkError()
    if invite.expires_at_utc <= clock.now():
        raise InvalidLinkError()
    return invite


def invite_email(db: Session, token: str) -> str | None:
    return _find(db, token, "invite").email


def accept_invite(
    db: Session, token: str, *, email: str | None, display_name: str, password: str, timezone: str | None
) -> User:
    invite = _find(db, token, "invite")
    chosen = invite.email or email
    if not chosen:
        raise InvalidInputError("invalid_email", "Enter a valid e-mail address")
    user = accounts.create_user(
        db, email=chosen, display_name=display_name, password=password, timezone=timezone
    )
    invite.used_at_utc = clock.now()
    return user


def register(db: Session, *, email: str, display_name: str, password: str, timezone: str | None) -> User:
    if not instance.registration_enabled(db):
        raise ForbiddenError("registration_closed", "Registration is closed")
    return accounts.create_user(
        db, email=email, display_name=display_name, password=password, timezone=timezone
    )


def reset_email(db: Session, token: str) -> str | None:
    invite = _find(db, token, "reset")
    user = db.get(User, invite.user_id) if invite.user_id else None
    return user.email if user else None


def reset_password(db: Session, token: str, password: str) -> User:
    invite = _find(db, token, "reset")
    user = db.get(User, invite.user_id) if invite.user_id else None
    if user is None:
        raise InvalidLinkError()
    if not user.is_active:
        raise ForbiddenError("account_disabled", "This account has been deactivated")
    accounts.set_password(db, user, password)
    invite.used_at_utc = clock.now()
    return user


def list_pending(db: Session) -> list[PendingInvite]:
    rows = db.scalars(
        select(Invite)
        .where(Invite.purpose == "invite", Invite.used_at_utc.is_(None), Invite.expires_at_utc > clock.now())
        .order_by(Invite.created_at_utc.desc())
    )
    return [
        PendingInvite(
            id=i.id, email=i.email, created_at_utc=i.created_at_utc, expires_at_utc=i.expires_at_utc
        )
        for i in rows
    ]


def revoke_invite(db: Session, invite_id: int) -> None:
    invite = db.get(Invite, invite_id)
    if invite is None or invite.purpose != "invite":
        raise NotFoundError()
    db.delete(invite)
    db.commit()
