"""Turning events into occurrences in a range: the one place everything else asks (SPEC 5)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.errors import InvalidInputError
from app.models import Event
from app.services import zones

MAX_RANGE = timedelta(days=400)


@dataclass(frozen=True)
class Instance:
    """One occurrence of an event: its wall-clock times in the event's own terms, and the instants."""

    event: Event
    start_local: datetime
    end_local: datetime
    start_utc: datetime
    end_utc: datetime


def check_range(start: datetime, end: datetime) -> None:
    if end <= start:
        raise InvalidInputError("invalid_range", "The end of the range must be after its start")
    if end - start > MAX_RANGE:
        raise InvalidInputError("range_too_long", "A range can cover at most 400 days")


def instants(event: Event, start_local: datetime, end_local: datetime, display_zone: str) -> Instance:
    """All-day events take their instants from the display zone; timed ones from their own."""
    zone = event.timezone if not event.all_day and event.timezone else display_zone
    return Instance(
        event=event,
        start_local=start_local,
        end_local=end_local,
        start_utc=zones.to_utc(start_local, zone),
        end_utc=zones.to_utc(end_local, zone),
    )


def overlaps(instance: Instance, range_start: datetime, range_end: datetime) -> bool:
    if instance.start_utc >= range_end:
        return False
    # An event without duration sits at its start, which must be inside the range.
    if instance.end_utc == instance.start_utc:
        return instance.start_utc >= range_start
    return instance.end_utc > range_start


def expand(
    events: Iterable[Event], range_start: datetime, range_end: datetime, display_zone: str
) -> list[Instance]:
    """The occurrences of events that fall into [range_start, range_end), ordered by start."""
    check_range(range_start, range_end)
    result: list[Instance] = []
    for event in events:
        instance = instants(event, event.start_local, event.end_local, display_zone)
        if overlaps(instance, range_start, range_end):
            result.append(instance)
    result.sort(key=lambda i: (i.start_utc, i.end_utc, i.event.id))
    return result
