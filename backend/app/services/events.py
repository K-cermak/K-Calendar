import uuid
from datetime import datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import InvalidInputError, NotFoundError
from app.models import Calendar, Event, EventTag, Tag, User
from app.schemas.calendar import EventCreate, EventOut, EventUpdate
from app.services import calendars, clock, tags, zones


def get_owned(db: Session, user: User, event_id: int) -> tuple[Event, Calendar]:
    """An event in one of this user's calendars. Someone else's is reported as missing."""
    row = db.execute(
        select(Event, Calendar)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .where(Event.id == event_id, Calendar.user_id == user.id)
    ).first()
    if row is None:
        raise NotFoundError()
    return row[0], row[1]


def tags_of(db: Session, event_ids: list[int]) -> dict[int, list[Tag]]:
    result: dict[int, list[Tag]] = {event_id: [] for event_id in event_ids}
    if not event_ids:
        return result
    rows = db.execute(
        select(EventTag.event_id, Tag)
        .join(Tag, Tag.id == EventTag.tag_id)
        .where(EventTag.event_id.in_(event_ids))
        .order_by(Tag.name_key)
    )
    for event_id, tag in rows:
        result[event_id].append(tag)
    return result


def local_text(event: Event, value: datetime) -> str:
    return value.date().isoformat() if event.all_day else zones.format_local(value)


def to_out(db: Session, event: Event, calendar: Calendar) -> EventOut:
    return EventOut.model_validate(
        {
            "id": event.id,
            "calendar_id": event.calendar_id,
            "uid": event.uid,
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "color": event.color,
            "all_day": event.all_day,
            "start": local_text(event, event.start_local),
            "end": local_text(event, event.end_local),
            "timezone": event.timezone,
            "rrule": event.rrule,
            "tags": [tags.to_out(t) for t in tags_of(db, [event.id])[event.id]],
            "read_only": calendar.kind == "subscription",
            "created_at_utc": event.created_at_utc,
            "updated_at_utc": event.updated_at_utc,
        }
    )


def derive(event: Event) -> None:
    """Recomputes the UTC columns from what the user entered."""
    if event.all_day:
        event.start_utc, event.end_utc = zones.floating_bounds(event.start_local, event.end_local)
    else:
        assert event.timezone is not None
        event.start_utc = zones.to_utc(event.start_local, event.timezone)
        event.end_utc = zones.to_utc(event.end_local, event.timezone)
    event.series_end_utc = event.end_utc if event.rrule is None else None


def _all_day_span(start: str, end: str) -> tuple[datetime, datetime]:
    start_day = zones.parse_local(start).date()
    end_day = zones.parse_local(end).date()
    if end_day <= start_day:
        raise InvalidInputError("invalid_span", "An all-day event ends at least one day after it starts")
    return zones.midnight(start_day), zones.midnight(end_day)


def _timed_span(start: str, end: str, zone: str, input_zone: str | None) -> tuple[datetime, datetime]:
    start_local, end_local = zones.parse_local(start), zones.parse_local(end)
    if input_zone and input_zone != zone:
        # Values from a grid shown in another zone: the same instants, written in the event's zone.
        start_local = zones.to_local(zones.to_utc(start_local, input_zone), zone)
        end_local = zones.to_local(zones.to_utc(end_local, input_zone), zone)
    if end_local < start_local:
        raise InvalidInputError("invalid_span", "The end must not be before the start")
    return start_local, end_local


def _set_tags(db: Session, user: User, event: Event, names: list[str]) -> None:
    db.execute(sql_delete(EventTag).where(EventTag.event_id == event.id))
    for tag in tags.resolve(db, user, names):
        db.add(EventTag(event_id=event.id, tag_id=tag.id))


def create(db: Session, user: User, body: EventCreate) -> EventOut:
    calendar = calendars.get_writable(db, user, body.calendar_id)
    if body.all_day:
        start_local, end_local = _all_day_span(body.start, body.end)
        zone = None
    else:
        zone = zones.check_zone(body.timezone or user.timezone)
        if body.input_timezone:
            zones.check_zone(body.input_timezone)
        start_local, end_local = _timed_span(body.start, body.end, zone, body.input_timezone)
    now = clock.now()
    event = Event(
        calendar_id=calendar.id,
        uid=str(uuid.uuid4()),
        title=body.title.strip(),
        description=body.description,
        location=body.location.strip(),
        color=body.color,
        all_day=body.all_day,
        start_local=start_local,
        end_local=end_local,
        timezone=zone,
        exdates=[],
        sequence=0,
        created_at_utc=now,
        updated_at_utc=now,
    )
    derive(event)
    db.add(event)
    db.flush()
    _set_tags(db, user, event, body.tags)
    db.commit()
    return to_out(db, event, calendar)


def get(db: Session, user: User, event_id: int) -> EventOut:
    event, calendar = get_owned(db, user, event_id)
    return to_out(db, event, calendar)


def _apply_times(event: Event, user: User, body: EventUpdate) -> None:
    all_day = event.all_day if body.all_day is None else body.all_day
    if all_day != event.all_day and (body.start is None or body.end is None):
        raise InvalidInputError("times_required", "Send start and end when switching all-day on or off")
    if all_day:
        if body.start is not None or body.end is not None:
            start = body.start or event.start_local.date().isoformat()
            end = body.end or event.end_local.date().isoformat()
            event.start_local, event.end_local = _all_day_span(start, end)
        event.timezone = None
    else:
        zone = zones.check_zone(body.timezone or event.timezone or user.timezone)
        if body.input_timezone:
            zones.check_zone(body.input_timezone)
        if body.start is not None or body.end is not None:
            start = body.start or zones.format_local(event.start_local)
            end = body.end or zones.format_local(event.end_local)
            input_zone = body.input_timezone or (zone if event.all_day else event.timezone)
            event.start_local, event.end_local = _timed_span(start, end, zone, input_zone)
        # A new zone without new times keeps the wall-clock times: "9:00" stays 9:00, in the new zone.
        event.timezone = zone
    event.all_day = all_day


def update(db: Session, user: User, event_id: int, body: EventUpdate) -> EventOut:
    event, calendar = get_owned(db, user, event_id)
    calendar = calendars.get_writable(db, user, calendar.id)
    if body.calendar_id is not None and body.calendar_id != calendar.id:
        calendar = calendars.get_writable(db, user, body.calendar_id)
        event.calendar_id = calendar.id
    if body.title is not None:
        event.title = body.title.strip()
    if body.description is not None:
        event.description = body.description
    if body.location is not None:
        event.location = body.location.strip()
    if "color" in body.model_fields_set:
        event.color = body.color
    _apply_times(event, user, body)
    derive(event)
    if body.tags is not None:
        _set_tags(db, user, event, body.tags)
    event.sequence += 1
    event.updated_at_utc = clock.now()
    db.commit()
    return to_out(db, event, calendar)


def delete(db: Session, user: User, event_id: int) -> None:
    event, calendar = get_owned(db, user, event_id)
    calendars.get_writable(db, user, calendar.id)
    db.delete(event)
    db.commit()
