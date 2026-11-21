"""Writing parsed iCalendar events into a calendar: file imports and subscriptions (SPEC 10)."""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Calendar, Event, EventTag, User
from app.services import clock, events, reminders, tags
from app.services.ics import ParsedEvent, Skipped, local_in


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    skipped: list[Skipped] = field(default_factory=list[Skipped])


def _fill(event: Event, parsed: ParsedEvent) -> None:
    event.title = parsed.title
    event.description = parsed.description
    event.location = parsed.location
    event.all_day = parsed.all_day
    event.start_local = parsed.start
    event.end_local = parsed.end
    event.timezone = parsed.timezone
    event.sequence = parsed.sequence


def _set_tags(db: Session, user: User, event: Event, names: list[str]) -> None:
    db.execute(delete(EventTag).where(EventTag.event_id == event.id))
    for tag in tags.resolve(db, user, names[:50]):
        db.add(EventTag(event_id=event.id, tag_id=tag.id))


def _new_event(calendar: Calendar, uid: str) -> Event:
    now = clock.now()
    return Event(
        calendar_id=calendar.id, uid=uid, exdates=[], sequence=0, created_at_utc=now, updated_at_utc=now
    )


def _original_start(parsed: ParsedEvent, master: Event) -> datetime:
    assert parsed.recurrence_id is not None
    return local_in(parsed.recurrence_id, master.timezone, all_day=master.all_day)


def _write_series(
    db: Session,
    user: User,
    calendar: Calendar,
    master_data: ParsedEvent | None,
    overrides: list[ParsedEvent],
    uid: str,
    with_reminders: bool,
) -> bool:
    """Creates or updates one event with its overrides. Returns True if it was new."""
    master = db.scalar(
        select(Event).where(
            Event.calendar_id == calendar.id, Event.uid == uid, Event.original_start.is_(None)
        )
    )
    created = master is None
    if master_data is not None:
        if master is None:
            master = _new_event(calendar, uid)
            db.add(master)
        _fill(master, master_data)
        master.rrule = master_data.rrule
        master.exdates = sorted(
            {local_in(m, master.timezone, all_day=master.all_day).isoformat() for m in master_data.exdates}
        )
        master.updated_at_utc = clock.now()
        events.derive(master)
        db.flush()
        _set_tags(db, user, master, master_data.categories)
        if with_reminders:
            reminders.set_for(db, master, master_data.alarms[:10])
        # The file is the whole truth about this series: its overrides replace the stored ones.
        db.execute(delete(Event).where(Event.recurring_event_id == master.id))
    elif master is None or master.rrule is None:
        raise ValueError("The file changes single occurrences of a series it does not contain")

    for parsed in overrides:
        original = _original_start(parsed, master)
        if parsed.cancelled:
            master.exdates = sorted({*master.exdates, original.isoformat()})
            continue
        if master_data is None:
            db.execute(
                delete(Event).where(Event.recurring_event_id == master.id, Event.original_start == original)
            )
        override = _new_event(calendar, uid)
        _fill(override, parsed)
        override.recurring_event_id = master.id
        override.original_start = original
        events.derive(override)
        db.add(override)
        db.flush()
        _set_tags(db, user, override, parsed.categories)
    if master_data is not None or overrides:
        events.derive(master)
    if with_reminders:
        reminders.refresh(db, [master.id])
    return created


def apply(
    db: Session,
    user: User,
    calendar: Calendar,
    parsed: list[ParsedEvent],
    skipped: list[Skipped],
    *,
    with_reminders: bool = True,
) -> ImportReport:
    """Matches events by UID within the calendar: a known UID is updated, a new one created.

    Each series is written in a savepoint, so one bad event does not fail the whole file.
    """
    report = ImportReport(skipped=list(skipped))
    by_uid: dict[str, tuple[ParsedEvent | None, list[ParsedEvent]]] = {}
    for item in parsed:
        master, overrides = by_uid.get(item.uid, (None, []))
        if item.recurrence_id is None:
            master = item
        else:
            overrides.append(item)
        by_uid[item.uid] = (master, overrides)

    for uid, (master, overrides) in by_uid.items():
        if master is not None and master.rrule is None and overrides:
            # Overrides of an event that does not repeat are noise from the other calendar.
            overrides = []
        savepoint = db.begin_nested()
        try:
            created = _write_series(db, user, calendar, master, overrides, uid, with_reminders)
        except (ValueError, TypeError) as exc:
            savepoint.rollback()
            title = (master or overrides[0]).title if (master or overrides) else ""
            report.skipped.append(Skipped(uid, title, str(exc)))
            continue
        savepoint.commit()
        if created:
            report.created += 1
        else:
            report.updated += 1
    return report


def replace_all(db: Session, user: User, calendar: Calendar, parsed: list[ParsedEvent]) -> None:
    """A subscription's new content replaces everything in its calendar, inside one transaction."""
    db.execute(delete(Event).where(Event.calendar_id == calendar.id))
    db.flush()
    # Subscribed calendars have no reminders (SPEC 8), so their alarms are left out.
    apply(db, user, calendar, parsed, [], with_reminders=False)
