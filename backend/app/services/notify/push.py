"""Web Push with VAPID (SPEC 8). The key pair is generated on first start and kept in the settings
table, unless the environment provides one."""

import base64
import json
import logging
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush  # pyright: ignore[reportUnknownVariableType]
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PushSubscription, Setting
from app.services import clock
from app.services.notify import devices, messages
from app.services.reminders import Delivery, DeliveryError

logger = logging.getLogger(__name__)

PUBLIC_KEY = "vapid_public_key"
PRIVATE_KEY = "vapid_private_key"
TTL_S = 60 * 60


def ensure_keys(db: Session, settings: Settings) -> None:
    if settings.vapid_public_key or db.get(Setting, PUBLIC_KEY) is not None:
        return
    key = ec.generate_private_key(ec.SECP256R1())
    # pywebpush reads a key given as text as base64url DER (or a raw 32-byte key), not PEM.
    private_der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    raw_public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    db.add(Setting(key=PRIVATE_KEY, value=base64.urlsafe_b64encode(private_der).rstrip(b"=").decode()))
    db.add(Setting(key=PUBLIC_KEY, value=base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode()))
    db.commit()
    logger.info("Generated the VAPID key pair for push notifications")


def public_key(db: Session, settings: Settings) -> str | None:
    if settings.vapid_public_key:
        return settings.vapid_public_key
    row = db.get(Setting, PUBLIC_KEY)
    return row.value if row else None


def _private_key(db: Session, settings: Settings) -> str:
    if settings.vapid_private_key:
        return settings.vapid_private_key
    row = db.get(Setting, PRIVATE_KEY)
    if row is None:
        raise DeliveryError("Push is not set up")
    return row.value


def contact(settings: Settings) -> str:
    """Who push services can reach about this instance. They accept only mailto: and https: URIs."""
    if settings.vapid_contact:
        return settings.vapid_contact
    if settings.smtp_from:
        return f"mailto:{settings.smtp_from}"
    if settings.base_url.startswith("https://"):
        return settings.base_url
    host = urlsplit(settings.base_url).hostname or "localhost"
    # py_vapid refuses an address whose domain has no dot, as on localhost during development.
    return f"mailto:calendar@{host if '.' in host else host + '.localdomain'}"


def send_payload(db: Session, settings: Settings, user_id: int, payload: dict[str, str]) -> int:
    """Sends to every device of the user; returns how many took it. Dead subscriptions are removed."""
    data = json.dumps(payload)
    delivered = 0
    errors: list[str] = []
    private = _private_key(db, settings)
    for subscription in list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))):
        # Checked again before each send: a name can resolve elsewhere than when it was stored.
        if not devices.endpoint_allowed(settings, subscription.endpoint):
            errors.append("address not allowed")
            continue
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=data,
                vapid_private_key=private,
                vapid_claims={"sub": contact(settings)},
                ttl=TTL_S,
                timeout=15,
            )
        except WebPushException as exc:
            status: int | None = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                # The browser dropped this subscription; it will never work again.
                db.execute(delete(PushSubscription).where(PushSubscription.id == subscription.id))
                continue
            errors.append(f"{status or 'no answer'}")
            continue
        except Exception as exc:  # network errors from requests, bad keys
            errors.append(type(exc).__name__)
            continue
        subscription.last_success_at_utc = clock.now()
        delivered += 1
    if delivered == 0 and errors:
        raise DeliveryError("Push failed: " + ", ".join(errors))
    return delivered


def send_reminder(db: Session, settings: Settings, delivery: Delivery) -> None:
    user, event = delivery.user, delivery.shown
    send_payload(
        db,
        settings,
        user.id,
        {
            "title": messages.title(user, event),
            "body": messages.reminder_body(user, event, delivery.start),
            "occurrence_id": delivery.occurrence_id,
            "url": f"/event/{delivery.occurrence_id}",
            "tag": f"reminder-{delivery.occurrence_id}",
        },
    )
