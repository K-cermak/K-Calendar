"""Wall-clock time and zones: every conversion between the two happens here (SPEC 5)."""

from datetime import UTC, date, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

from app.errors import InvalidInputError

ZONES = frozenset(available_timezones()) | {"UTC"}

# All-day events float: 3 May is 3 May in every zone. Their UTC columns span the widest the day can
# be anywhere (UTC+14 to UTC-12), so a range query in UTC never misses one; the exact check happens
# afterwards in the display zone.
FLOATING_EARLIEST = timedelta(hours=14)
FLOATING_LATEST = timedelta(hours=12)


def check_zone(name: str) -> str:
    if name not in ZONES:
        raise InvalidInputError("invalid_timezone", f"{name!r} is not a known time zone")
    return name


@cache
def zone(name: str) -> ZoneInfo:
    return ZoneInfo(check_zone(name))


def to_utc(local: datetime, zone_name: str) -> datetime:
    """The instant a wall-clock time stands for in a zone.

    fold=0 gives both rules from SPEC 5: a time in the spring-forward gap is read with the offset
    from before the gap, which moves it forward by the gap's size, and an ambiguous autumn time
    takes its first occurrence.
    """
    return local.replace(tzinfo=zone(zone_name), fold=0).astimezone(UTC)


def to_local(instant: datetime, zone_name: str) -> datetime:
    """The wall-clock time an instant shows in a zone, without the zone attached."""
    return instant.astimezone(zone(zone_name)).replace(tzinfo=None)


def floating_bounds(start_local: datetime, end_local: datetime) -> tuple[datetime, datetime]:
    return (
        start_local.replace(tzinfo=UTC) - FLOATING_EARLIEST,
        end_local.replace(tzinfo=UTC) + FLOATING_LATEST,
    )


def parse_local(value: str) -> datetime:
    """An ISO date or date and time without an offset, as a naive datetime."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise InvalidInputError("invalid_datetime", f"{value!r} is not an ISO date or time") from None
    if parsed.tzinfo is not None:
        raise InvalidInputError(
            "invalid_datetime", f"{value!r} has an offset; send the wall-clock time and the zone"
        )
    return parsed


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidInputError("invalid_date", f"{value!r} is not an ISO date (YYYY-MM-DD)") from None


def format_local(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day)
