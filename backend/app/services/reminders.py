"""Reminders: when each fires next, and delivering them (SPEC 8).

Each reminder keeps next_fire_at_utc, so a tick of the background loop is one indexed query for
what is due, never an expansion of every event. It is recomputed whenever its event or the
reminder changes, and after each firing.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import InvalidInputError
from app.models import Calendar, Event, NotificationLog, PushSubscription, Reminder, User
from app.services import clock, recurrence

logger = logging.getLogger(__name__)

LATE = timedelta(minutes=15)
HORIZON = timedelta(days=399)
MAX_ATTEMPTS = 3
# All-day reminders count from midnight; a day before at most, and up to four weeks before.
MIN_MINUTES = -24 * 60
MAX_MINUTES = 4 * 7 * 24 * 60


def check_minutes(values: list[int]) -> list[int]:
    for value in values:
        if not MIN_MINUTES <= value <= MAX_MINUTES:
            raise InvalidInputError("invalid_reminder", "A reminder is at most four weeks before")
    return sorted(set(values), reverse=True)


def set_for(db: Session, event: Event, minutes: list[int]) -> None:
    """Replaces an event's reminders, keeping the rows that stay (and their delivery log)."""
    wanted = check_minutes(minutes)
    existing = {
        r.minutes_before: r for r in db.scalars(select(Reminder).where(Reminder.event_id == event.id))
    }
    for value, reminder in existing.items():
        if value not in wanted:
            db.delete(reminder)
    for value in wanted:
        if value not in existing:
            db.add(Reminder(event_id=event.id, minutes_before=value))
    db.flush()


def minutes_of(db: Session, event_ids: list[int]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {event_id: [] for event_id in event_ids}
    if event_ids:
        rows = db.execute(
            select(Reminder.event_id, Reminder.minutes_before)
            .where(Reminder.event_id.in_(event_ids))
            .order_by(Reminder.minutes_before.desc())
        )
        for event_id, minutes in rows:
            result[event_id].append(minutes)
    return result


# Scheduling


def _series_rows(db: Session, master: Event) -> tuple[list[Event], dict[int, set[datetime]]]:
    overrides = list(db.scalars(select(Event).where(Event.recurring_event_id == master.id)))
    starts = {o.original_start for o in overrides if o.original_start is not None}
    return [master, *overrides], {master.id: starts}


def _next_instance(
    db: Session, master: Event, zone: str, minutes: int, after: datetime
) -> recurrence.Instance | None:
    """The earliest occurrence whose reminder fires at or after `after`."""
    earliest_start = after + timedelta(minutes=minutes)
    if master.rrule is None:
        instance = recurrence.instants(master, master.start_local, master.end_local, zone)
        return instance if instance.start_utc >= earliest_start else None
    rows, overridden = _series_rows(db, master)
    instances = recurrence.expand(rows, earliest_start, earliest_start + HORIZON, zone, overridden)
    upcoming = [i for i in instances if i.start_utc >= earliest_start]
    return min(upcoming, key=lambda i: i.start_utc) if upcoming else None


def schedule(db: Session, reminder: Reminder, master: Event, user: User, after: datetime) -> None:
    instance = _next_instance(db, master, user.timezone, reminder.minutes_before, after)
    if instance is None:
        reminder.next_fire_at_utc = None
        reminder.next_occurrence_start = None
        return
    reminder.next_fire_at_utc = instance.start_utc - timedelta(minutes=reminder.minutes_before)
    reminder.next_occurrence_start = instance.original_start or instance.start_local


def refresh(db: Session, master_ids: list[int]) -> None:
    """Recomputes the reminders of these events after any change to them or their occurrences.

    Starting a little in the past lets a reminder that came due a moment before an edit still
    fire; the delivery log keeps it from firing twice.
    """
    if not master_ids:
        return
    rows = db.execute(
        select(Reminder, Event, User)
        .join(Event, Event.id == Reminder.event_id)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .join(User, User.id == Calendar.user_id)
        .where(Reminder.event_id.in_(master_ids))
    )
    after = clock.now() - LATE
    for reminder, master, user in rows:
        schedule(db, reminder, master, user, after)


def refresh_user(db: Session, user: User) -> None:
    """After a change of zone, all-day reminders (counted from local midnight) move."""
    ids = db.scalars(
        select(Event.id)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .join(Reminder, Reminder.event_id == Event.id)
        .where(Calendar.user_id == user.id, Event.all_day)
    )
    refresh(db, list(set(ids)))


# Delivery


@dataclass
class Delivery:
    """What one reminder says, ready for each channel."""

    user: User
    master: Event
    shown: Event
    start: datetime  # the occurrence's start, as an instant
    occurrence_id: str


Sender = Callable[[Session, Settings, Delivery], None]


class DeliveryError(Exception):
    """A channel failed in a way that is worth trying again."""


def _delivery(db: Session, reminder: Reminder, master: Event, user: User) -> Delivery | None:
    original = reminder.next_occurrence_start
    if original is None:
        return None
    shown = master
    start_local, end_local = master.start_local, master.end_local
    master_id: int | None = None
    if master.rrule is not None:
        master_id = master.id
        override = db.scalar(
            select(Event).where(Event.recurring_event_id == master.id, Event.original_start == original)
        )
        if override is not None:
            shown, start_local, end_local = override, override.start_local, override.end_local
        else:
            start_local, end_local = original, original + (master.end_local - master.start_local)
    instance = recurrence.instants(
        shown,
        start_local,
        end_local,
        user.timezone,
        master_id=master_id,
        original_start=original if master_id else None,
    )
    return Delivery(user, master, shown, instance.start_utc, instance.id)


def _log(db: Session, reminder: Reminder, channel: str) -> NotificationLog:
    assert reminder.next_occurrence_start is not None
    entry = db.scalar(
        select(NotificationLog).where(
            NotificationLog.reminder_id == reminder.id,
            NotificationLog.occurrence_start == reminder.next_occurrence_start,
            NotificationLog.channel == channel,
        )
    )
    if entry is None:
        entry = NotificationLog(
            reminder_id=reminder.id,
            occurrence_start=reminder.next_occurrence_start,
            channel=channel,
            status="pending",
            attempts=0,
        )
        db.add(entry)
        db.flush()
    return entry


def channels(db: Session, settings: Settings, user: User) -> list[str]:
    result: list[str] = []
    has_device = db.scalar(select(PushSubscription.id).where(PushSubscription.user_id == user.id).limit(1))
    if has_device is not None:
        result.append("push")
    if user.email_reminders_enabled and settings.smtp_enabled:
        result.append("email")
    return result


def fire(db: Session, settings: Settings, reminder_id: int, senders: dict[str, Sender]) -> None:
    """Delivers one due reminder on each channel, then moves it on to the next occurrence.

    A channel that fails is tried again on later ticks, three times in all; the reminder only
    moves on once every channel has succeeded or given up.
    """
    row = db.execute(
        select(Reminder, Event, User)
        .join(Event, Event.id == Reminder.event_id)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .join(User, User.id == Calendar.user_id)
        .where(Reminder.id == reminder_id)
    ).first()
    if row is None:
        return
    reminder, master, user = row
    now = clock.now()
    fired_at = reminder.next_fire_at_utc
    delivery = _delivery(db, reminder, master, user) if user.is_active else None
    pending = False
    # An occurrence that began more than 15 minutes ago means the server was down, or the event
    # was edited into the past: the reminder is skipped, not sent late.
    if delivery is not None and delivery.start >= now - LATE:
        for channel in channels(db, settings, user):
            entry = _log(db, reminder, channel)
            if entry.status in ("sent", "failed"):
                continue
            entry.attempts += 1
            try:
                senders[channel](db, settings, delivery)
            except DeliveryError as exc:
                entry.error = str(exc)[:1000]
                entry.status = "failed" if entry.attempts >= MAX_ATTEMPTS else "retry"
                pending = pending or entry.status == "retry"
                logger.info("Reminder %s via %s failed: %s", reminder.id, channel, exc)
            else:
                entry.status = "sent"
                entry.error = None
                entry.sent_at_utc = now
            # Each channel is committed as soon as it is done, so a crash does not resend it.
            db.commit()
    if not pending and fired_at is not None:
        schedule(db, reminder, master, user, fired_at + timedelta(seconds=1))
    db.commit()


def due(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(Reminder.id)
            .where(Reminder.next_fire_at_utc.is_not(None), Reminder.next_fire_at_utc <= clock.now())
            .order_by(Reminder.next_fire_at_utc)
        )
    )


def clean_up_log(db: Session, keep: timedelta) -> None:
    db.execute(delete(NotificationLog).where(NotificationLog.sent_at_utc < clock.now() - keep))
