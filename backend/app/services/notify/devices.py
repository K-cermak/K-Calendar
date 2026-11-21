from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PushSubscription, User
from app.schemas.account import PushSubscriptionIn
from app.services import clock


def subscribe(db: Session, user: User, body: PushSubscriptionIn, user_agent: str | None) -> None:
    """Registers this device for push. An endpoint is one browser profile, so it belongs to
    whoever subscribed with it last."""
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
