import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.i18n import t
from app.models import Calendar, CalendarSubscription, User
from app.schemas.calendar import CalendarCreate, CalendarOrder, CalendarOut, CalendarUpdate, SubscriptionInfo

DEFAULT_COLOR = "blue"


def feed_url(base_url: str, calendar: Calendar) -> str | None:
    return f"{base_url}/feeds/{calendar.feed_token}.ics" if calendar.feed_token else None


def to_out(
    calendar: Calendar, base_url: str, subscription: CalendarSubscription | None = None
) -> CalendarOut:
    info = (
        SubscriptionInfo.model_validate(
            {
                "source_url": subscription.source_url,
                "refresh_interval_minutes": subscription.refresh_interval_minutes,
                "last_fetched_at_utc": subscription.last_fetched_at_utc,
                "last_status": subscription.last_status,
                "last_error": subscription.last_error,
            }
        )
        if subscription
        else None
    )
    return CalendarOut.model_validate(
        {
            "feed_url": feed_url(base_url, calendar),
            "subscription": info,
            "id": calendar.id,
            "name": calendar.name,
            "color": calendar.color,
            "kind": calendar.kind,
            "is_visible": calendar.is_visible,
            "sort_order": calendar.sort_order,
            "default_reminder_minutes": calendar.default_reminder_minutes,
            "read_only": calendar.kind == "subscription",
        }
    )


def get_owned(db: Session, user: User, calendar_id: int) -> Calendar:
    """A calendar of this user. Someone else's is reported as missing, not as forbidden."""
    calendar = db.get(Calendar, calendar_id)
    if calendar is None or calendar.user_id != user.id:
        raise NotFoundError()
    return calendar


def get_writable(db: Session, user: User, calendar_id: int) -> Calendar:
    calendar = get_owned(db, user, calendar_id)
    if calendar.kind == "subscription":
        raise ConflictError("read_only_calendar", "Events in a subscribed calendar cannot be changed")
    return calendar


def list_for(db: Session, user: User, base_url: str) -> list[CalendarOut]:
    rows = db.execute(
        select(Calendar, CalendarSubscription)
        .outerjoin(CalendarSubscription, CalendarSubscription.calendar_id == Calendar.id)
        .where(Calendar.user_id == user.id)
        .order_by(Calendar.sort_order, Calendar.id)
    )
    return [to_out(calendar, base_url, subscription) for calendar, subscription in rows]


def out(db: Session, calendar: Calendar, base_url: str) -> CalendarOut:
    return to_out(calendar, base_url, db.get(CalendarSubscription, calendar.id))


def _check_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise InvalidInputError("name_required", "Enter a name")
    return stripped


def next_sort_order(db: Session, user: User) -> int:
    highest = db.scalar(select(func.max(Calendar.sort_order)).where(Calendar.user_id == user.id))
    return (highest if highest is not None else -1) + 1


def create_default(db: Session, user: User) -> Calendar:
    calendar = Calendar(
        user_id=user.id,
        name=t(user.locale, "calendar.default_name"),
        color=DEFAULT_COLOR,
        kind="local",
        is_visible=True,
        sort_order=0,
    )
    db.add(calendar)
    db.flush()
    return calendar


def create(db: Session, user: User, body: CalendarCreate, base_url: str) -> CalendarOut:
    calendar = Calendar(
        user_id=user.id,
        name=_check_name(body.name),
        color=body.color,
        kind="local",
        is_visible=True,
        sort_order=next_sort_order(db, user),
        default_reminder_minutes=body.default_reminder_minutes,
    )
    db.add(calendar)
    db.commit()
    return to_out(calendar, base_url)


def update(db: Session, user: User, calendar_id: int, body: CalendarUpdate, base_url: str) -> CalendarOut:
    calendar = get_owned(db, user, calendar_id)
    if body.name is not None:
        calendar.name = _check_name(body.name)
    if body.color is not None:
        calendar.color = body.color
    if body.is_visible is not None:
        calendar.is_visible = body.is_visible
    if "default_reminder_minutes" in body.model_fields_set:
        calendar.default_reminder_minutes = body.default_reminder_minutes
    if body.refresh_interval_minutes is not None:
        subscription = db.get(CalendarSubscription, calendar.id)
        if subscription is None:
            raise InvalidInputError("not_subscription", "Only subscribed calendars are refreshed")
        subscription.refresh_interval_minutes = body.refresh_interval_minutes
    db.commit()
    return out(db, calendar, base_url)


def reorder(db: Session, user: User, body: CalendarOrder, base_url: str) -> list[CalendarOut]:
    owned = {c.id: c for c in db.scalars(select(Calendar).where(Calendar.user_id == user.id))}
    if sorted(body.ids) != sorted(owned):
        raise InvalidInputError("invalid_order", "List every calendar exactly once")
    for position, calendar_id in enumerate(body.ids):
        owned[calendar_id].sort_order = position
    db.commit()
    return list_for(db, user, base_url)


def delete(db: Session, user: User, calendar_id: int) -> None:
    calendar = get_owned(db, user, calendar_id)
    if calendar.kind == "local":
        local_count = db.scalar(
            select(func.count()).where(Calendar.user_id == user.id, Calendar.kind == "local")
        )
        # Quick create and imports need somewhere to put events.
        if (local_count or 0) <= 1:
            raise ConflictError("last_calendar", "Keep at least one calendar of your own")
    # Its events, their tags links and (later) reminders go with it through ON DELETE CASCADE.
    db.delete(calendar)
    db.commit()


def set_feed(db: Session, user: User, calendar_id: int, base_url: str) -> CalendarOut:
    """Switches the secret feed address on, or replaces it; the old address stops working."""
    calendar = get_owned(db, user, calendar_id)
    calendar.feed_token = secrets.token_urlsafe(32)
    db.commit()
    return out(db, calendar, base_url)


def remove_feed(db: Session, user: User, calendar_id: int) -> None:
    calendar = get_owned(db, user, calendar_id)
    calendar.feed_token = None
    db.commit()


def by_feed_token(db: Session, token: str) -> Calendar | None:
    if not token:
        return None
    calendar = db.scalar(select(Calendar).where(Calendar.feed_token == token))
    # Compared again in constant time; the index lookup alone could leak timing on prefixes.
    if calendar is None or not secrets.compare_digest(calendar.feed_token or "", token):
        return None
    return calendar
