import re
from zoneinfo import available_timezones

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    TooManyRequestsError,
    UnauthorizedError,
)
from app.models import User
from app.schemas.account import Me, ProfileUpdate
from app.services import clock
from app.services.auth import credentials, sessions
from app.services.auth.throttle import LoginThrottle

MIN_PASSWORD_LENGTH = 10
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")
_ZONES = frozenset(available_timezones())


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL.match(normalized):
        raise InvalidInputError("invalid_email", "Enter a valid e-mail address")
    return normalized


def check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInputError("password_too_short", f"Use at least {MIN_PASSWORD_LENGTH} characters")


def check_display_name(display_name: str) -> str:
    name = display_name.strip()
    if not name:
        raise InvalidInputError("display_name_required", "Enter a display name")
    return name


def check_timezone(zone: str) -> str:
    if zone not in _ZONES:
        raise InvalidInputError("invalid_timezone", f"{zone!r} is not a known time zone")
    return zone


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str | None,
    timezone: str | None = None,
    is_admin: bool = False,
) -> User:
    email = normalize_email(email)
    display_name = check_display_name(display_name)
    if password is not None:
        check_password(password)
    if get_by_email(db, email) is not None:
        raise ConflictError("email_taken", "An account with this e-mail address already exists")
    # A zone the server does not know (an old browser, a typo) is not worth refusing a sign-up over.
    zone = timezone if timezone in _ZONES else "UTC"
    user = User(
        email=email,
        display_name=display_name,
        password_hash=credentials.hash_password(password) if password is not None else None,
        is_admin=is_admin,
        is_active=True,
        timezone=zone,
        created_at_utc=clock.now(),
    )
    db.add(user)
    db.flush()
    return user


def setup_admin(db: Session, *, email: str, display_name: str, password: str, timezone: str | None) -> User:
    if user_count(db) > 0:
        raise ConflictError("setup_done", "The instance is already set up")
    return create_user(
        db, email=email, display_name=display_name, password=password, timezone=timezone, is_admin=True
    )


def authenticate(db: Session, throttle: LoginThrottle, *, email: str, password: str, ip: str) -> User:
    """Check credentials. Unknown e-mail and wrong password look the same to the caller."""
    account = email.strip().lower()
    retry_after = throttle.retry_after(account, ip)
    if retry_after:
        raise TooManyRequestsError(retry_after)
    user = get_by_email(db, account)
    if not credentials.verify_password(user.password_hash if user else None, password) or user is None:
        throttle.failed(account, ip)
        raise UnauthorizedError("The e-mail address or password is not correct")
    if not user.is_active:
        raise ForbiddenError("account_disabled", "This account has been deactivated")
    throttle.succeeded(account)
    assert user.password_hash is not None
    if credentials.password_needs_rehash(user.password_hash):
        user.password_hash = credentials.hash_password(password)
    return user


def to_me(user: User) -> Me:
    return Me.model_validate(
        {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "timezone": user.timezone,
            "locale": user.locale,
            "week_start": user.week_start,
            "time_format": user.time_format,
            "default_view": user.default_view,
            "theme": user.theme,
            "email_reminders_enabled": user.email_reminders_enabled,
            "has_password": user.password_hash is not None,
        }
    )


def update_profile(db: Session, user: User, update: ProfileUpdate) -> User:
    if update.display_name is not None:
        user.display_name = check_display_name(update.display_name)
    if update.timezone is not None:
        user.timezone = check_timezone(update.timezone)
    if update.locale is not None:
        user.locale = update.locale
    if update.week_start is not None:
        user.week_start = update.week_start
    if update.time_format is not None:
        user.time_format = update.time_format
    if update.default_view is not None:
        user.default_view = update.default_view
    if update.theme is not None:
        user.theme = update.theme
    db.commit()
    return user


def change_password(db: Session, user: User, *, current: str, new: str, keep_session_id: int) -> None:
    if not credentials.verify_password(user.password_hash, current):
        raise InvalidInputError("wrong_password", "The current password is not correct")
    check_password(new)
    user.password_hash = credentials.hash_password(new)
    sessions.revoke_others(db, user.id, keep_session_id)
    db.commit()


def set_password(db: Session, user: User, password: str) -> None:
    """Set a new password and sign the user out everywhere, for reset links."""
    check_password(password)
    user.password_hash = credentials.hash_password(password)
    sessions.revoke_all(db, user.id)
