from datetime import UTC, datetime

import pytest

from app.errors import InvalidInputError
from app.services import zones


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_plain_conversion_in_both_seasons() -> None:
    assert zones.to_utc(datetime(2026, 1, 15, 9, 0), "Europe/Prague") == utc(2026, 1, 15, 8, 0)
    assert zones.to_utc(datetime(2026, 7, 15, 9, 0), "Europe/Prague") == utc(2026, 7, 15, 7, 0)
    assert zones.to_utc(datetime(2026, 1, 15, 9, 0), "America/New_York") == utc(2026, 1, 15, 14, 0)
    assert zones.to_utc(datetime(2026, 7, 15, 9, 0), "America/New_York") == utc(2026, 7, 15, 13, 0)


@pytest.mark.parametrize(
    ("zone", "gap_local", "expected_utc"),
    [
        # Prague springs forward on 29 March 2026 from 02:00 to 03:00; 02:30 becomes 03:30.
        ("Europe/Prague", datetime(2026, 3, 29, 2, 30), utc(2026, 3, 29, 1, 30)),
        # New York springs forward on 8 March 2026 from 02:00 to 03:00.
        ("America/New_York", datetime(2026, 3, 8, 2, 30), utc(2026, 3, 8, 7, 30)),
    ],
)
def test_time_in_the_spring_gap_moves_forward_by_the_gap(
    zone: str, gap_local: datetime, expected_utc: datetime
) -> None:
    instant = zones.to_utc(gap_local, zone)
    assert instant == expected_utc
    assert zones.to_local(instant, zone) == gap_local.replace(hour=3)


@pytest.mark.parametrize(
    ("zone", "ambiguous_local", "first_utc"),
    [
        # Prague falls back on 25 October 2026: 02:30 happens at 00:30 and again at 01:30 UTC.
        ("Europe/Prague", datetime(2026, 10, 25, 2, 30), utc(2026, 10, 25, 0, 30)),
        # New York falls back on 1 November 2026: 01:30 happens at 05:30 and again at 06:30 UTC.
        ("America/New_York", datetime(2026, 11, 1, 1, 30), utc(2026, 11, 1, 5, 30)),
    ],
)
def test_ambiguous_time_takes_the_first_occurrence(
    zone: str, ambiguous_local: datetime, first_utc: datetime
) -> None:
    assert zones.to_utc(ambiguous_local, zone) == first_utc


def test_floating_bounds_cover_every_zone_on_earth() -> None:
    start, end = zones.floating_bounds(datetime(2026, 5, 3), datetime(2026, 5, 4))
    for zone in ("Pacific/Kiritimati", "Etc/GMT+12", "UTC", "Europe/Prague"):
        assert start <= zones.to_utc(datetime(2026, 5, 3), zone)
        assert end >= zones.to_utc(datetime(2026, 5, 4), zone)


def test_unknown_zone_is_refused() -> None:
    with pytest.raises(InvalidInputError):
        zones.check_zone("Europe/Atlantis")


def test_local_values_must_not_carry_an_offset() -> None:
    assert zones.parse_local("2026-11-23T09:00") == datetime(2026, 11, 23, 9, 0)
    assert zones.parse_local("2026-11-23") == datetime(2026, 11, 23)
    with pytest.raises(InvalidInputError):
        zones.parse_local("2026-11-23T09:00+01:00")
    with pytest.raises(InvalidInputError):
        zones.parse_local("next tuesday")
