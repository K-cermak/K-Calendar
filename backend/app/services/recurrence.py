"""Turning events into occurrences in a range: the one place everything else asks (SPEC 5).

A series is expanded in wall-clock time from its naive local start, so 09:00 stays 09:00 across a
daylight saving change, and each occurrence is converted to UTC on its own.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dateutil.rrule import rrule, rrulestr

from app.errors import InvalidInputError
from app.models import Event
from app.services import zones

MAX_RANGE = timedelta(days=400)
MAX_OCCURRENCES = 1000
# dateutil walks a rule from its first occurrence, even to reach a range years later. This bounds
# that walk, which a rule with many BY* parts could otherwise make enormous.
MAX_SCAN = 100_000
# Finding where a finite series ends walks it to the end; longer than this counts as never ending.
MAX_SERIES = 20_000
# Sub-daily series would hit MAX_SCAN within months and then quietly lose occurrences, so they are
# refused instead; calendars practically never use them.
ALLOWED_FREQUENCIES = frozenset({"DAILY", "WEEKLY", "MONTHLY", "YEARLY"})
KEY_FORMAT = "%Y%m%dT%H%M%S"


@dataclass(frozen=True)
class Instance:
    """One occurrence: the row it shows, its wall-clock times in its own terms, and the instants.

    For a series, master_id and original_start identify the occurrence; event is the master, or
    the override row that replaces this occurrence.
    """

    event: Event
    start_local: datetime
    end_local: datetime
    start_utc: datetime
    end_utc: datetime
    master_id: int | None = None
    original_start: datetime | None = None

    @property
    def occurrence_key(self) -> str | None:
        return occurrence_key(self.original_start) if self.original_start else None

    @property
    def id(self) -> str:
        if self.master_id is None or self.original_start is None:
            return str(self.event.id)
        return f"{self.master_id}_{occurrence_key(self.original_start)}"


def occurrence_key(original_start: datetime) -> str:
    return original_start.strftime(KEY_FORMAT)


def parse_occurrence_key(value: str) -> datetime:
    try:
        return datetime.strptime(value, KEY_FORMAT)
    except ValueError:
        raise InvalidInputError("invalid_occurrence", f"{value!r} is not an occurrence") from None


def check_range(start: datetime, end: datetime) -> None:
    if end <= start:
        raise InvalidInputError("invalid_range", "The end of the range must be after its start")
    if end - start > MAX_RANGE:
        raise InvalidInputError("range_too_long", "A range can cover at most 400 days")


# Rules


def _parts(text: str) -> list[tuple[str, str]]:
    body = text.strip()
    if body.upper().startswith("RRULE:"):
        body = body[6:]
    parts: list[tuple[str, str]] = []
    for part in body.split(";"):
        if not part.strip():
            continue
        key, sep, value = part.partition("=")
        if not sep:
            raise InvalidInputError("invalid_rrule", f"{text!r} is not a recurrence rule")
        parts.append((key.strip().upper(), value.strip().upper()))
    return parts


def _join(parts: list[tuple[str, str]]) -> str:
    return ";".join(f"{key}={value}" for key, value in parts)


def normalize_rule(text: str, *, all_day: bool, zone: str | None) -> str:
    """A rule in the form this app stores: no RRULE: prefix, and UNTIL as wall-clock time.

    UNTIL in UTC (with Z), as other calendars write it, becomes the wall-clock time in the event's
    zone, because the series is expanded in wall-clock time. All-day series get a date.
    """
    parts = _parts(text)
    keys = [key for key, _ in parts]
    if "FREQ" not in keys:
        raise InvalidInputError("invalid_rrule", "A recurrence rule needs FREQ")
    freq = dict(parts)["FREQ"]
    if freq not in ALLOWED_FREQUENCIES:
        raise InvalidInputError("unsupported_rrule", f"Events cannot repeat {freq.lower()}")
    if "COUNT" in keys and "UNTIL" in keys:
        raise InvalidInputError("invalid_rrule", "A rule has COUNT or UNTIL, not both")
    normalized: list[tuple[str, str]] = []
    for key, value in parts:
        if key == "UNTIL":
            value = _normalize_until(value, all_day=all_day, zone=zone)
        normalized.append((key, value))
    result = _join(normalized)
    # Parsed once here so that a broken rule is refused when saved rather than when shown.
    try:
        rrulestr(result, dtstart=datetime(2000, 1, 1))
    except (ValueError, TypeError) as exc:
        raise InvalidInputError("invalid_rrule", f"The recurrence rule is not valid: {exc}") from None
    return result


def _normalize_until(value: str, *, all_day: bool, zone: str | None) -> str:
    try:
        if len(value) == 8:
            day = datetime.strptime(value, "%Y%m%d")
            return value if all_day else (day + timedelta(days=1, seconds=-1)).strftime(KEY_FORMAT)
        utc = value.endswith("Z")
        moment = datetime.strptime(value.rstrip("Z"), KEY_FORMAT)
    except ValueError:
        raise InvalidInputError("invalid_rrule", f"UNTIL={value} is not a date or time") from None
    if utc:
        moment = zones.to_local(moment.replace(tzinfo=UTC), zone or "UTC")
    return moment.strftime("%Y%m%d") if all_day else moment.strftime(KEY_FORMAT)


def rule_parts(text: str) -> dict[str, str]:
    return dict(_parts(text))


def with_parts(text: str, **changes: str | None) -> str:
    """The rule with some parts replaced, added, or removed (None)."""
    parts = [(k, v) for k, v in _parts(text) if k not in {c.upper() for c in changes}]
    parts += [(key.upper(), value) for key, value in changes.items() if value is not None]
    return _join(parts)


def build(event: Event) -> rrule:
    assert event.rrule is not None
    parsed = rrulestr(event.rrule, dtstart=event.start_local)
    assert isinstance(parsed, rrule)
    return parsed


def _excluded(event: Event) -> set[datetime]:
    return {datetime.fromisoformat(value) for value in event.exdates}


def series_end(event: Event) -> datetime | None:
    """The naive local end of the last occurrence, or None if the series never ends."""
    rule = build(event)
    parts = rule_parts(event.rrule or "")
    if "COUNT" not in parts and "UNTIL" not in parts:
        return None
    last: datetime | None = None
    for index, start in enumerate(rule):
        if index >= MAX_SERIES:
            return None
        last = start
    if last is None:
        return event.start_local
    return last + (event.end_local - event.start_local)


def series_end_utc(event: Event) -> datetime | None:
    end = series_end(event)
    if end is None:
        return None
    if event.all_day:
        return zones.floating_bounds(event.start_local, end)[1]
    assert event.timezone is not None
    return zones.to_utc(end, event.timezone)


def starts_before(event: Event, moment: datetime) -> int:
    """How many occurrences of the series start before moment (local), for splitting a COUNT."""
    count = 0
    for start in build(event):
        if start >= moment or count >= MAX_SERIES:
            break
        count += 1
    return count


def is_occurrence(event: Event, original_start: datetime) -> bool:
    if original_start in _excluded(event):
        return False
    for index, start in enumerate(build(event)):
        if start == original_start:
            return True
        if start > original_start or index >= MAX_SCAN:
            return False
    return False


# Expansion


def instants(
    event: Event,
    start_local: datetime,
    end_local: datetime,
    display_zone: str,
    *,
    master_id: int | None = None,
    original_start: datetime | None = None,
) -> Instance:
    """All-day events take their instants from the display zone; timed ones from their own."""
    zone = event.timezone if not event.all_day and event.timezone else display_zone
    return Instance(
        event=event,
        start_local=start_local,
        end_local=end_local,
        start_utc=zones.to_utc(start_local, zone),
        end_utc=zones.to_utc(end_local, zone),
        master_id=master_id,
        original_start=original_start,
    )


def overlaps(instance: Instance, range_start: datetime, range_end: datetime) -> bool:
    if instance.start_utc >= range_end:
        return False
    # An event without duration sits at its start, which must be inside the range.
    if instance.end_utc == instance.start_utc:
        return instance.start_utc >= range_start
    return instance.end_utc > range_start


def _local_window(
    event: Event, range_start: datetime, range_end: datetime, display_zone: str
) -> tuple[datetime, datetime]:
    """The wall-clock starts that can produce an occurrence in the range, with a day to spare for
    offsets and daylight saving; the exact check happens on the instants."""
    zone = event.timezone if not event.all_day and event.timezone else display_zone
    duration = event.end_local - event.start_local
    margin = timedelta(days=1)
    return (
        zones.to_local(range_start, zone) - duration - margin,
        zones.to_local(range_end, zone) + margin,
    )


def expand_series(
    master: Event,
    range_start: datetime,
    range_end: datetime,
    display_zone: str,
    overridden: set[datetime],
) -> list[Instance]:
    """The master's own occurrences in the range, without exdates and overridden ones."""
    rule = build(master)
    duration = master.end_local - master.start_local
    window_start, window_end = _local_window(master, range_start, range_end, display_zone)
    excluded = _excluded(master) | overridden
    result: list[Instance] = []
    for scanned, start in enumerate(rule):
        if start > window_end or scanned >= MAX_SCAN or len(result) >= MAX_OCCURRENCES:
            break
        if start < window_start or start in excluded:
            continue
        instance = instants(
            master, start, start + duration, display_zone, master_id=master.id, original_start=start
        )
        if overlaps(instance, range_start, range_end):
            result.append(instance)
    return result


def expand(
    events: Iterable[Event],
    range_start: datetime,
    range_end: datetime,
    display_zone: str,
    overridden: dict[int, set[datetime]] | None = None,
) -> list[Instance]:
    """The occurrences of events that fall into [range_start, range_end), ordered by start.

    events holds single events, masters and override rows; overridden maps each master to the
    original starts its overrides replace, wherever those overrides moved to.
    """
    check_range(range_start, range_end)
    overridden = overridden or {}
    result: list[Instance] = []
    for event in events:
        if event.rrule is not None and event.recurring_event_id is None:
            result += expand_series(
                event, range_start, range_end, display_zone, overridden.get(event.id, set())
            )
            continue
        instance = instants(
            event,
            event.start_local,
            event.end_local,
            display_zone,
            master_id=event.recurring_event_id,
            original_start=event.original_start,
        )
        if overlaps(instance, range_start, range_end):
            result.append(instance)
    result.sort(key=lambda i: (i.start_utc, i.end_utc, i.event.id))
    return result
