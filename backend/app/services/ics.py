# icalendar's components and properties are dynamically typed; strict mode would flag every use.
# pyright: basic
"""iCalendar in and out (SPEC 10): one mapping between VEVENTs and this app's events.

UID, DTSTART and DTEND (with TZID, in UTC, floating, or as dates), RRULE, EXDATE, RECURRENCE-ID
for overrides, SUMMARY, DESCRIPTION, LOCATION and CATEGORIES for tags. Alarms come with reminders.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import icalendar
from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.branding import get_branding
from app.errors import InvalidInputError
from app.models import Calendar, Event
from app.services import clock, events, recurrence, zones

MAX_BYTES = 10 * 1024 * 1024


class IcsError(Exception):
    """Something in one VEVENT that makes it impossible to import."""


@dataclass
class Moment:
    """A DTSTART, DTEND, EXDATE or RECURRENCE-ID value, still in the terms the file used."""

    value: datetime | date
    zone: str | None  # IANA zone, "UTC", or None for floating times and dates


@dataclass
class ParsedEvent:
    uid: str
    title: str
    description: str
    location: str
    all_day: bool
    start: datetime
    end: datetime
    timezone: str | None
    rrule: str | None
    exdates: list[Moment] = field(default_factory=list[Moment])
    recurrence_id: Moment | None = None
    cancelled: bool = False
    categories: list[str] = field(default_factory=list[str])
    sequence: int = 0


@dataclass
class Skipped:
    uid: str
    title: str
    reason: str


# Reading


def _zone_name(value: datetime, tzid: str | None) -> str | None:
    """The IANA name for an aware value, or None when only its offsets are known.

    Outlook writes Windows names ("Central Europe Standard Time"); those map to IANA names.
    """
    key = getattr(value.tzinfo, "key", None)
    for candidate in (key, tzid):
        if candidate in zones.ZONES:
            return candidate
        if candidate in WINDOWS_TO_OLSON:
            return WINDOWS_TO_OLSON[candidate]
    if value.utcoffset() == timedelta(0) and (tzid is None or tzid.upper() in {"UTC", "Z", "GMT"}):
        return "UTC"
    return None


def _moment(prop: Any) -> Moment:
    value = prop.dt
    if isinstance(value, datetime):
        tzid = prop.params.get("TZID")
        if value.tzinfo is None:
            return Moment(value, None)
        name = _zone_name(value, tzid)
        # A zone known only by its VTIMEZONE offsets: keep the instant, in UTC.
        return Moment(value if name else value.astimezone(UTC), name or "UTC")
    if isinstance(value, date):
        return Moment(value, None)
    raise IcsError(f"Unsupported date value {value!r}")


def local_in(moment: Moment, zone: str | None, *, all_day: bool) -> datetime:
    """A moment as wall-clock time in an event's zone (or a midnight for all-day events)."""
    value = moment.value
    if not isinstance(value, datetime):
        return zones.midnight(value)
    if all_day:
        return zones.midnight(value.date())
    if value.tzinfo is None:
        return value
    return zones.to_local(value, zone or "UTC")


def _text(component: Any, name: str) -> str:
    value = component.get(name)
    return str(value).strip() if value is not None else ""


def _categories(component: Any) -> list[str]:
    raw = component.get("CATEGORIES")
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    names: list[str] = []
    for item in items:
        names += [str(c).strip() for c in getattr(item, "cats", [item]) if str(c).strip()]
    return names


def _parse_event(component: Any, default_zone: str) -> ParsedEvent:
    uid = _text(component, "UID")
    if not uid:
        raise IcsError("The event has no UID")
    if component.get("DTSTART") is None:
        raise IcsError("The event has no start")
    start = _moment(component["DTSTART"])
    all_day = not isinstance(start.value, datetime)
    zone = None if all_day else (start.zone or default_zone)
    start_local = local_in(start, zone, all_day=all_day)
    if component.get("DTEND") is not None:
        end_local = local_in(_moment(component["DTEND"]), zone, all_day=all_day)
    elif component.get("DURATION") is not None:
        end_local = start_local + component["DURATION"].dt
    else:
        end_local = start_local + (timedelta(days=1) if all_day else timedelta(0))
    if all_day and end_local <= start_local:
        end_local = start_local + timedelta(days=1)
    if end_local < start_local:
        raise IcsError("The event ends before it starts")

    rrule = None
    if component.get("RRULE") is not None:
        raw = component["RRULE"]
        raw = raw[0] if isinstance(raw, list) else raw
        try:
            rrule = recurrence.normalize_rule(raw.to_ical().decode(), all_day=all_day, zone=zone)
        except InvalidInputError as exc:
            raise IcsError(exc.message) from None

    exdates: list[Moment] = []
    raw_exdates = component.get("EXDATE")
    for group in raw_exdates if isinstance(raw_exdates, list) else [raw_exdates] if raw_exdates else []:
        tzid = group.params.get("TZID")
        for item in group.dts:
            value = item.dt
            if isinstance(value, datetime) and value.tzinfo is not None:
                name = _zone_name(value, tzid)
                exdates.append(Moment(value if name else value.astimezone(UTC), name or "UTC"))
            else:
                exdates.append(Moment(value, None))

    recurrence_id = _moment(component["RECURRENCE-ID"]) if component.get("RECURRENCE-ID") else None
    sequence = component.get("SEQUENCE")
    return ParsedEvent(
        uid=uid[:255],
        title=_text(component, "SUMMARY")[:500],
        description=_text(component, "DESCRIPTION")[:20_000],
        location=_text(component, "LOCATION")[:500],
        all_day=all_day,
        start=start_local,
        end=end_local,
        timezone=zone,
        rrule=rrule,
        exdates=exdates,
        recurrence_id=recurrence_id,
        cancelled=_text(component, "STATUS").upper() == "CANCELLED",
        categories=_categories(component),
        sequence=int(sequence) if sequence is not None else 0,
    )


def parse(data: bytes, default_zone: str) -> tuple[list[ParsedEvent], list[Skipped]]:
    """Every VEVENT that can be read, and the ones that cannot with the reason."""
    if len(data) > MAX_BYTES:
        raise InvalidInputError("file_too_large", "The file is larger than 10 MB")
    try:
        calendars = icalendar.Calendar.from_ical(data, multiple=True)
    except (ValueError, IndexError, KeyError) as exc:
        raise InvalidInputError("invalid_ics", f"This is not an iCalendar file: {exc}") from None
    parsed: list[ParsedEvent] = []
    skipped: list[Skipped] = []
    for cal in calendars:
        for component in cal.walk("VEVENT"):
            try:
                parsed.append(_parse_event(component, default_zone))
            except (IcsError, ValueError, TypeError, AttributeError, KeyError) as exc:
                skipped.append(Skipped(_text(component, "UID"), _text(component, "SUMMARY"), str(exc)))
    return parsed, skipped


# Writing


def _dt(value: datetime, zone: str | None, all_day: bool) -> datetime | date:
    if all_day:
        return value.date()
    return value.replace(tzinfo=UTC if zone == "UTC" else ZoneInfo(zone or "UTC"))


def _export_rule(event: Event) -> icalendar.vRecur:
    """UNTIL goes out in UTC for timed events, as RFC 5545 requires with a TZID start."""
    assert event.rrule is not None
    parts = recurrence.rule_parts(event.rrule)
    until = parts.get("UNTIL")
    rule = event.rrule
    if until and not event.all_day and len(until) == 15:
        local = datetime.strptime(until, recurrence.KEY_FORMAT)
        instant = zones.to_utc(local, event.timezone or "UTC")
        rule = recurrence.with_parts(rule, UNTIL=instant.strftime(recurrence.KEY_FORMAT) + "Z")
    return icalendar.vRecur.from_ical(rule)


def _component(event: Event, master: Event | None, tag_names: list[str]) -> icalendar.Event:
    source = master or event
    vevent = icalendar.Event()
    vevent.add("UID", event.uid)
    vevent.add("DTSTAMP", clock.now())
    vevent.add("CREATED", event.created_at_utc)
    vevent.add("LAST-MODIFIED", event.updated_at_utc)
    vevent.add("SEQUENCE", event.sequence)
    vevent.add("SUMMARY", event.title)
    if event.description:
        vevent.add("DESCRIPTION", event.description)
    if event.location:
        vevent.add("LOCATION", event.location)
    if tag_names:
        vevent.add("CATEGORIES", tag_names)
    vevent.add("DTSTART", _dt(event.start_local, event.timezone, event.all_day))
    vevent.add("DTEND", _dt(event.end_local, event.timezone, event.all_day))
    if master is not None and event.original_start is not None:
        vevent.add("RECURRENCE-ID", _dt(event.original_start, source.timezone, source.all_day))
    if master is None and event.rrule:
        vevent.add("RRULE", _export_rule(event))
        if event.exdates:
            vevent.add(
                "EXDATE",
                [_dt(datetime.fromisoformat(v), event.timezone, event.all_day) for v in event.exdates],
            )
    return vevent


def serialize(db: Session, calendar: Calendar) -> bytes:
    cal = icalendar.Calendar()
    cal.add("PRODID", f"-//{get_branding().name}//EN")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("X-WR-CALNAME", calendar.name)
    rows = list(db.scalars(select(Event).where(Event.calendar_id == calendar.id).order_by(Event.id)))
    masters = {e.id: e for e in rows if e.recurring_event_id is None}
    tags = events.tags_of(db, [e.id for e in rows])
    for event in rows:
        master = masters.get(event.recurring_event_id) if event.recurring_event_id else None
        if event.recurring_event_id is not None and master is None:
            continue
        cal.add_component(_component(event, master, [t.name for t in tags[event.id]]))
    cal.add_missing_timezones()
    return cal.to_ical()
