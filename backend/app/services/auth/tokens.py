"""Personal API tokens for scripts (SPEC 6)."""

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import ApiToken, User
from app.schemas.account import ApiTokenCreate, ApiTokenInfo
from app.services import clock
from app.services.auth import credentials

# A fixed prefix makes a leaked token recognisable, for example to secret scanners.
TOKEN_PREFIX = "cal_"  # noqa: S105
DISPLAYED_PREFIX_LENGTH = 12
# As with sessions: recording every use would turn every read into a write.
TOUCH_INTERVAL = timedelta(hours=1)


def _info(token: ApiToken) -> ApiTokenInfo:
    return ApiTokenInfo(
        id=token.id,
        name=token.name,
        prefix=token.token_prefix,
        scope=token.scope,  # pyright: ignore[reportArgumentType]
        created_at_utc=token.created_at_utc,
        last_used_at_utc=token.last_used_at_utc,
        expires_at_utc=token.expires_at_utc,
    )


def create(db: Session, user: User, request: ApiTokenCreate) -> tuple[ApiTokenInfo, str]:
    """Creates a token and returns it in plain text, the only time it is available."""
    secret = TOKEN_PREFIX + secrets.token_urlsafe(32)
    now = clock.now()
    token = ApiToken(
        user_id=user.id,
        name=request.name.strip() or "Token",
        token_hash=credentials.hash_token(secret),
        token_prefix=secret[:DISPLAYED_PREFIX_LENGTH],
        scope=request.scope,
        created_at_utc=now,
        last_used_at_utc=None,
        expires_at_utc=now + timedelta(days=request.expires_in_days) if request.expires_in_days else None,
        revoked_at_utc=None,
    )
    db.add(token)
    db.commit()
    return _info(token), secret


def list_for(db: Session, user: User) -> list[ApiTokenInfo]:
    rows = db.scalars(
        select(ApiToken)
        .where(ApiToken.user_id == user.id, ApiToken.revoked_at_utc.is_(None))
        .order_by(ApiToken.created_at_utc.desc())
    )
    return [_info(row) for row in rows]


def revoke(db: Session, user: User, token_id: int) -> None:
    token = db.get(ApiToken, token_id)
    if token is None or token.user_id != user.id or token.revoked_at_utc is not None:
        raise NotFoundError()
    token.revoked_at_utc = clock.now()
    db.commit()


def resolve(db: Session, secret: str) -> tuple[ApiToken, User] | None:
    """The token and its user, if the token is valid and the account active."""
    if not secret.startswith(TOKEN_PREFIX):
        return None
    row = db.execute(
        select(ApiToken, User)
        .join(User, User.id == ApiToken.user_id)
        .where(ApiToken.token_hash == credentials.hash_token(secret))
    ).first()
    if row is None:
        return None
    token, user = row
    expired = token.expires_at_utc is not None and token.expires_at_utc <= clock.now()
    if token.revoked_at_utc is not None or expired or not user.is_active:
        return None
    return token, user


def touch_due(token: ApiToken) -> bool:
    return token.last_used_at_utc is None or clock.now() - token.last_used_at_utc >= TOUCH_INTERVAL


def touch(db: Session, token_id: int) -> None:
    token = db.get(ApiToken, token_id)
    if token is not None:
        token.last_used_at_utc = clock.now()
        db.commit()
