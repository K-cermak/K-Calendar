from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import InvalidInputError
from app.models import PushSubscription, User
from app.schemas.account import PushSubscriptionIn
from app.services import clock, subscriptions


def endpoint_allowed(settings: Settings, endpoint: str) -> bool:
    """A push endpoint comes from the browser, so the server posts to an address a user chose.
    Like subscription URLs it must not lead into private networks (SPEC 15)."""
    parts = urlsplit(endpoint)
    private_ok = settings.allow_private_subscription_urls
    if parts.scheme != "https" and not (private_ok and parts.scheme == "http"):
        return False
    if not parts.hostname:
        return False
    try:
        subscriptions.resolve(parts.hostname, parts.port or 443, private_ok)
    except subscriptions.FetchError:
        return False
    return True


def subscribe(
    db: Session, settings: Settings, user: User, body: PushSubscriptionIn, user_agent: str | None
) -> None:
    """Registers this device for push. An endpoint is one browser profile, so it belongs to
    whoever subscribed with it last."""
    if not endpoint_allowed(settings, body.endpoint):
        raise InvalidInputError("invalid_endpoint", "This push address is not allowed")
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if existing is None:
        existing = PushSubscription(endpoint=body.endpoint, created_at_utc=clock.now())
        db.add(existing)
    existing.user_id = user.id
    existing.p256dh = body.keys.p256dh
    existing.auth = body.keys.auth
    existing.user_agent = (user_agent or "")[:300] or None
    db.commit()


def unsubscribe(db: Session, user: User, endpoint: str) -> None:
    existing = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()


def is_subscribed(db: Session, user: User, endpoint: str) -> bool:
    return (
        db.scalar(
            select(PushSubscription.id).where(
                PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
            )
        )
        is not None
    )
