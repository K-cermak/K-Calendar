from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import InvalidInputError
from app.models import Calendar, Event, User
from app.schemas.calendar import Occurrence, OccurrenceList
from app.services import clock, events, recurrence, tags, zones


def _instant(value: str, zone: str) -> datetime:
    """A range bound: wall-clock in the display zone, or an instant if it carries an offset."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise InvalidInputError("invalid_datetime", f"{value!r} is not an ISO date or time") from None
    return zones.to_utc(parsed, zone) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _candidates(db: Session, user: User, start: datetime, end: datetime) -> list[tuple[Event, Calendar]]:
    """Events of visible calendars whose UTC span may touch the range; expansion decides exactly."""
    rows = db.execute(
        select(Event, Calendar)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .where(
            Calendar.user_id == user.id,
            Calendar.is_visible,
            Event.recurring_event_id.is_(None),
            Event.start_utc < end,
            or_(Event.series_end_utc.is_(None), Event.series_end_utc >= start),
        )
    )
    return [(event, calendar) for event, calendar in rows]


def list_for(db: Session, user: User, start: str, end: str, tz: str | None) -> OccurrenceList:
    zone = zones.check_zone(tz or user.timezone)
    range_start, range_end = _instant(start, zone), _instant(end, zone)
    recurrence.check_range(range_start, range_end)
    rows = _candidates(db, user, range_start, range_end)
    calendar_of = {event.id: calendar for event, calendar in rows}
    instances = recurrence.expand([event for event, _ in rows], range_start, range_end, zone)
    tags_by_event = events.tags_of(db, sorted({i.event.id for i in instances}))

    items: list[Occurrence] = []
    for instance in instances:
        event = instance.event
        calendar = calendar_of[event.id]
        if event.all_day:
            start_text = instance.start_local.date().isoformat()
            end_text = instance.end_local.date().isoformat()
        else:
            start_text = zones.format_local(zones.to_local(instance.start_utc, zone))
            end_text = zones.format_local(zones.to_local(instance.end_utc, zone))
        items.append(
            Occurrence.model_validate(
                {
                    "id": str(event.id),
                    "event_id": event.id,
                    "calendar_id": calendar.id,
                    "title": event.title,
                    "location": event.location,
                    "color": event.color or calendar.color,
                    "all_day": event.all_day,
                    "start": start_text,
                    "end": end_text,
                    "start_utc": instance.start_utc,
                    "end_utc": instance.end_utc,
                    "tags": [tags.to_out(t) for t in tags_by_event[event.id]],
                    "recurring": event.rrule is not None,
                    "read_only": calendar.kind == "subscription",
                }
            )
        )
    now = zones.format_local(zones.to_local(clock.now(), zone))
    return OccurrenceList(timezone=zone, now=now, items=items)
