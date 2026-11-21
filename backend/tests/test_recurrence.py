from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_event, occurrences


def starts(client: TestClient, start: str, end: str, tz: str | None = None) -> list[str]:
    return [o["start"] for o in occurrences(client, start, end, tz)]


def series(client: TestClient, rrule: str, **fields: Any) -> dict[str, Any]:
    return create_event(client, rrule=rrule, **fields)


def change(client: TestClient, event_id: int, occurrence: str, scope: str, **body: Any) -> dict[str, Any]:
    response = client.patch(
        f"/api/v1/events/{event_id}", params={"scope": scope, "occurrence": occurrence}, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def remove(client: TestClient, event_id: int, occurrence: str, scope: str) -> None:
    response = client.delete(f"/api/v1/events/{event_id}", params={"scope": scope, "occurrence": occurrence})
    assert response.status_code == 204, response.text


# Daylight saving


@pytest.mark.parametrize(
    ("zone", "before", "after", "utc_before", "utc_after"),
    [
        ("Europe/Prague", "2026-03-23", "2026-03-30", "08:00", "07:00"),
        ("Europe/Prague", "2026-10-19", "2026-10-26", "07:00", "08:00"),
        ("America/New_York", "2026-03-02", "2026-03-09", "14:00", "13:00"),
        ("America/New_York", "2026-10-26", "2026-11-02", "13:00", "14:00"),
    ],
)
def test_weekly_series_keeps_its_local_time_across_dst(
    admin: TestClient, zone: str, before: str, after: str, utc_before: str, utc_after: str
) -> None:
    series(admin, "FREQ=WEEKLY", start=f"{before}T09:00", end=f"{before}T10:00", timezone=zone)
    items = occurrences(admin, before, f"{after}T23:00", zone)
    assert [o["start"] for o in items] == [f"{before}T09:00:00", f"{after}T09:00:00"]
    assert [o["start_utc"][11:16] for o in items] == [utc_before, utc_after]


def test_daily_series_through_the_spring_gap(admin: TestClient) -> None:
    # 02:30 does not exist in Prague on 29 March 2026; that occurrence moves to 03:30.
    series(admin, "FREQ=DAILY;COUNT=3", start="2026-03-28T02:30", end="2026-03-28T03:00")
    assert starts(admin, "2026-03-28", "2026-03-31", "Europe/Prague") == [
        "2026-03-28T02:30:00",
        "2026-03-29T03:30:00",
        "2026-03-30T02:30:00",
    ]


def test_series_seen_from_another_zone(admin: TestClient) -> None:
    series(admin, "FREQ=WEEKLY;COUNT=2", start="2026-10-19T09:00", end="2026-10-19T10:00")
    # New York changes a week after Prague, so for one week the gap is five hours, not six.
    assert starts(admin, "2026-10-18", "2026-11-01", "America/New_York") == [
        "2026-10-19T03:00:00",
        "2026-10-26T04:00:00",
    ]


# Rule shapes


def test_monthly_on_the_31st_skips_short_months(admin: TestClient) -> None:
    series(admin, "FREQ=MONTHLY;COUNT=4", start="2026-01-31T12:00", end="2026-01-31T13:00")
    assert [s[:10] for s in starts(admin, "2026-01-01", "2026-12-31")] == [
        "2026-01-31",
        "2026-03-31",
        "2026-05-31",
        "2026-07-31",
    ]


@pytest.mark.parametrize(("day", "february"), [(29, 0), (30, 0)])
def test_monthly_late_days_have_no_february(admin: TestClient, day: int, february: int) -> None:
    series(admin, f"FREQ=MONTHLY;BYMONTHDAY={day}", start=f"2027-01-{day}T12:00", end=f"2027-01-{day}T13:00")
    found = [s[:7] for s in starts(admin, "2027-01-01", "2027-04-01")]
    assert found.count("2027-02") == february
    assert found == ["2027-01", "2027-03"]


def test_yearly_on_29_february_only_in_leap_years(admin: TestClient) -> None:
    series(admin, "FREQ=YEARLY", all_day=True, start="2028-02-29", end="2028-03-01")
    assert starts(admin, "2028-01-01", "2029-01-01") == ["2028-02-29"]
    assert starts(admin, "2029-01-01", "2030-01-01") == []
    assert starts(admin, "2031-06-01", "2032-06-01") == ["2032-02-29"]


def test_nth_weekday_rules(admin: TestClient) -> None:
    series(admin, "FREQ=MONTHLY;BYDAY=2TU", start="2026-11-10T18:00", end="2026-11-10T19:00")
    series(admin, "FREQ=MONTHLY;BYDAY=-1FR", start="2026-11-27T16:00", end="2026-11-27T17:00", title="Last")
    items = occurrences(admin, "2026-11-01", "2027-02-01")
    second_tuesdays = [o["start"][:10] for o in items if o["title"] == "Meeting"]
    last_fridays = [o["start"][:10] for o in items if o["title"] == "Last"]
    assert second_tuesdays == ["2026-11-10", "2026-12-08", "2027-01-12"]
    assert last_fridays == ["2026-11-27", "2026-12-25", "2027-01-29"]


def test_count_until_and_interval(admin: TestClient) -> None:
    series(
        admin,
        "FREQ=DAILY;INTERVAL=2;COUNT=3",
        title="Count",
        start="2026-11-01T08:00",
        end="2026-11-01T09:00",
    )
    series(
        admin,
        "FREQ=WEEKLY;UNTIL=20261115T235959",
        title="Until",
        start="2026-11-01T10:00",
        end="2026-11-01T11:00",
    )
    items = occurrences(admin, "2026-10-25", "2026-12-31")
    assert [o["start"][:10] for o in items if o["title"] == "Count"] == [
        "2026-11-01",
        "2026-11-03",
        "2026-11-05",
    ]
    assert [o["start"][:10] for o in items if o["title"] == "Until"] == [
        "2026-11-01",
        "2026-11-08",
        "2026-11-15",
    ]


def test_until_in_utc_is_read_as_the_events_wall_clock(admin: TestClient) -> None:
    # Written by another calendar: the last occurrence is at 09:00 Prague time on 15 November.
    event = series(
        admin, "RRULE:FREQ=WEEKLY;UNTIL=20261115T080000Z", start="2026-11-01T09:00", end="2026-11-01T10:00"
    )
    assert event["rrule"] == "FREQ=WEEKLY;UNTIL=20261115T090000"
    assert len(starts(admin, "2026-10-25", "2026-12-31")) == 3


def test_occurrence_ids_and_keys(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=2")
    items = occurrences(admin, "2026-11-23", "2026-11-25")
    assert [(o["id"], o["event_id"], o["occurrence"], o["recurring"]) for o in items] == [
        (f"{event['id']}_20261123T090000", event["id"], "20261123T090000", True),
        (f"{event['id']}_20261124T090000", event["id"], "20261124T090000", True),
    ]


def test_all_day_series_far_east_and_west(admin: TestClient) -> None:
    series(admin, "FREQ=WEEKLY;COUNT=3", all_day=True, start="2026-05-03", end="2026-05-04")
    for zone in ("Pacific/Kiritimati", "Etc/GMT+12"):
        items = occurrences(admin, "2026-05-01", "2026-05-31", zone)
        assert [(o["start"], o["end"]) for o in items] == [
            ("2026-05-03", "2026-05-04"),
            ("2026-05-10", "2026-05-11"),
            ("2026-05-17", "2026-05-18"),
        ], zone


def test_series_boundaries(admin: TestClient) -> None:
    series(admin, "FREQ=DAILY;COUNT=3", title="Ended", start="2026-01-01T09:00", end="2026-01-01T10:00")
    series(
        admin,
        "FREQ=WEEKLY",
        title="Overnight",
        start="2026-11-22T23:00",
        end="2026-11-23T01:00",
        timezone="UTC",
    )
    titles = [o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-24", "UTC")]
    assert titles == ["Overnight"]


def test_a_series_that_started_long_ago(admin: TestClient) -> None:
    series(admin, "FREQ=DAILY", start="1990-01-01T07:00", end="1990-01-01T07:30")
    assert len(starts(admin, "2026-11-23", "2026-11-30")) == 7


# Safety limits


def test_one_event_produces_at_most_1000_occurrences(admin: TestClient) -> None:
    series(
        admin, "FREQ=DAILY;BYHOUR=0,1,2,3,4,5,6,7,8,9,10,11", start="2026-01-01T00:00", end="2026-01-01T00:30"
    )
    assert len(occurrences(admin, "2026-01-01", "2027-01-01")) == 1000


def test_rules_are_validated(admin: TestClient) -> None:
    cases = {
        "FREQ=SECONDLY": "unsupported_rrule",
        "FREQ=MINUTELY;INTERVAL=5": "unsupported_rrule",
        "BYDAY=MO": "invalid_rrule",
        "FREQ=WEEKLY;COUNT=2;UNTIL=20270101": "invalid_rrule",
        "FREQ=WEEKLY;BYDAY=XX": "invalid_rrule",
        "nonsense": "invalid_rrule",
    }
    for rule, code in cases.items():
        response = admin.post(
            "/api/v1/events",
            json={
                "calendar_id": admin.get("/api/v1/calendars").json()[0]["id"],
                "start": "2026-11-23T09:00",
                "end": "2026-11-23T10:00",
                "rrule": rule,
            },
        )
        assert response.json()["code"] == code, rule


# Reading one occurrence


def test_get_one_occurrence(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=5", title="Daily")
    one = admin.get(f"/api/v1/events/{event['id']}", params={"occurrence": "20261125T090000"}).json()
    assert (one["start"], one["end"], one["occurrence"], one["recurring"]) == (
        "2026-11-25T09:00:00",
        "2026-11-25T10:00:00",
        "20261125T090000",
        True,
    )
    assert one["rrule"] == "FREQ=DAILY;COUNT=5"
    missing = admin.get(f"/api/v1/events/{event['id']}", params={"occurrence": "20261125T100000"})
    assert missing.status_code == 404
    bad = admin.get(f"/api/v1/events/{event['id']}", params={"occurrence": "tomorrow"})
    assert bad.status_code == 422


# Edit scope: this


def test_this_changes_one_occurrence_and_can_move_it_to_another_day(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=3", title="Daily", tags=["team"])
    changed = change(
        admin,
        event["id"],
        "20261124T090000",
        "this",
        title="Moved",
        start="2026-11-27T15:00",
        end="2026-11-27T16:00",
    )
    assert (changed["title"], changed["start"], changed["occurrence"]) == (
        "Moved",
        "2026-11-27T15:00:00",
        "20261124T090000",
    )
    items = occurrences(admin, "2026-11-23", "2026-11-30")
    assert [(o["title"], o["start"]) for o in items] == [
        ("Daily", "2026-11-23T09:00:00"),
        ("Daily", "2026-11-25T09:00:00"),
        ("Moved", "2026-11-27T15:00:00"),
    ]
    moved = items[2]
    assert (moved["id"], moved["event_id"], moved["occurrence"]) == (
        f"{event['id']}_20261124T090000",
        event["id"],
        "20261124T090000",
    )
    assert [t["name"] for t in moved["tags"]] == ["team"]
    # The moved occurrence is still found by its original key, and changes again in place.
    again = change(admin, event["id"], "20261124T090000", "this", title="Moved again")
    assert again["start"] == "2026-11-27T15:00:00"
    assert len(occurrences(admin, "2026-11-23", "2026-11-30")) == 3


def test_override_outside_the_range_still_hides_its_original(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=3")
    change(admin, event["id"], "20261124T090000", "this", start="2026-12-24T09:00", end="2026-12-24T10:00")
    assert starts(admin, "2026-11-23", "2026-11-26") == ["2026-11-23T09:00:00", "2026-11-25T09:00:00"]
    assert starts(admin, "2026-12-24", "2026-12-25") == ["2026-12-24T09:00:00"]


def test_this_cannot_change_the_rule_or_calendar(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=3")
    params = {"scope": "this", "occurrence": "20261124T090000"}
    rule = admin.patch(f"/api/v1/events/{event['id']}", params=params, json={"rrule": "FREQ=WEEKLY"})
    assert rule.json()["code"] == "rule_for_series"
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    moved = admin.patch(f"/api/v1/events/{event['id']}", params=params, json={"calendar_id": work})
    assert moved.json()["code"] == "calendar_for_series"


def test_scope_is_required_for_an_occurrence(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=3")
    params = {"occurrence": "20261124T090000"}
    assert (
        admin.patch(f"/api/v1/events/{event['id']}", params=params, json={}).json()["code"]
        == "scope_required"
    )
    assert admin.delete(f"/api/v1/events/{event['id']}", params=params).json()["code"] == "scope_required"


def test_delete_this_adds_an_exdate_and_drops_its_override(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=4")
    change(admin, event["id"], "20261124T090000", "this", title="Changed")
    remove(admin, event["id"], "20261124T090000", "this")
    remove(admin, event["id"], "20261125T090000", "this")
    assert starts(admin, "2026-11-23", "2026-11-30") == ["2026-11-23T09:00:00", "2026-11-26T09:00:00"]
    gone = admin.get(f"/api/v1/events/{event['id']}", params={"occurrence": "20261124T090000"})
    assert gone.status_code == 404


# Edit scope: all


def test_all_without_timing_change_keeps_exceptions(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=4", title="Daily")
    change(admin, event["id"], "20261124T090000", "this", start="2026-11-24T11:00", end="2026-11-24T12:00")
    remove(admin, event["id"], "20261125T090000", "this")
    change(admin, event["id"], "20261126T090000", "all", title="Renamed", location="Room 2")
    items = occurrences(admin, "2026-11-23", "2026-11-30")
    assert [(o["start"][8:16], o["title"]) for o in items] == [
        ("23T09:00", "Renamed"),
        ("24T11:00", "Daily"),  # overrides keep their own fields
        ("26T09:00", "Renamed"),
    ]


def test_all_with_a_new_time_moves_every_occurrence_and_drops_exceptions(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=4")
    change(admin, event["id"], "20261124T090000", "this", title="Changed")
    remove(admin, event["id"], "20261125T090000", "this")
    # Dragging Thursday's occurrence from 09:00 to 10:30 moves the whole series by 90 minutes.
    updated = change(
        admin, event["id"], "20261126T090000", "all", start="2026-11-26T10:30", end="2026-11-26T11:30"
    )
    assert (updated["start"], updated["occurrence"]) == ("2026-11-23T10:30:00", None)
    assert starts(admin, "2026-11-23", "2026-11-30") == [
        "2026-11-23T10:30:00",
        "2026-11-24T10:30:00",
        "2026-11-25T10:30:00",
        "2026-11-26T10:30:00",
    ]
    assert {o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-30")} == {"Meeting"}


def test_all_can_change_the_rule(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=10")
    change(admin, event["id"], "20261125T090000", "all", rrule="FREQ=WEEKLY;COUNT=2")
    assert starts(admin, "2026-11-23", "2026-12-31") == ["2026-11-23T09:00:00", "2026-11-30T09:00:00"]


def test_all_to_all_day_and_back(admin: TestClient) -> None:
    event = series(admin, "FREQ=WEEKLY;COUNT=2")
    change(admin, event["id"], "20261130T090000", "all", all_day=True, start="2026-11-30", end="2026-12-01")
    assert starts(admin, "2026-11-23", "2026-12-07") == ["2026-11-23", "2026-11-30"]
    change(
        admin,
        event["id"],
        "20261130T000000",
        "all",
        all_day=False,
        start="2026-11-30T08:00",
        end="2026-11-30T08:30",
    )
    assert starts(admin, "2026-11-23", "2026-12-07") == ["2026-11-23T08:00:00", "2026-11-30T08:00:00"]


def test_ending_the_repetition(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=5")
    plain = admin.patch(f"/api/v1/events/{event['id']}", json={"rrule": None}).json()
    assert (plain["rrule"], plain["recurring"]) == (None, False)
    assert starts(admin, "2026-11-23", "2026-11-30") == ["2026-11-23T09:00:00"]


def test_delete_all(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=5")
    change(admin, event["id"], "20261124T090000", "this", title="Changed")
    remove(admin, event["id"], "20261125T090000", "all")
    assert occurrences(admin, "2026-11-23", "2026-11-30") == []


# Edit scope: following


def test_following_splits_a_series_with_until(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;UNTIL=20261127T235959", title="Daily")
    follower = change(
        admin, event["id"], "20261125T090000", "following", start="2026-11-25T14:00", end="2026-11-25T15:00"
    )
    assert follower["id"] != event["id"]
    assert follower["rrule"] == "FREQ=DAILY;UNTIL=20261127T235959"
    first = admin.get(f"/api/v1/events/{event['id']}").json()
    assert first["rrule"] == "FREQ=DAILY;UNTIL=20261125T085959"
    assert starts(admin, "2026-11-23", "2026-11-30") == [
        "2026-11-23T09:00:00",
        "2026-11-24T09:00:00",
        "2026-11-25T14:00:00",
        "2026-11-26T14:00:00",
        "2026-11-27T14:00:00",
    ]


def test_following_splits_a_count_into_the_remaining_occurrences(admin: TestClient) -> None:
    event = series(admin, "FREQ=WEEKLY;COUNT=6")
    follower = change(admin, event["id"], "20261207T090000", "following", title="Later")
    assert admin.get(f"/api/v1/events/{event['id']}").json()["rrule"] == "FREQ=WEEKLY;COUNT=2"
    assert follower["rrule"] == "FREQ=WEEKLY;COUNT=4"
    items = occurrences(admin, "2026-11-01", "2027-02-01")
    assert [o["title"] for o in items] == ["Meeting"] * 2 + ["Later"] * 4


def test_following_without_timing_change_moves_later_exceptions(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=6", title="Daily")
    change(admin, event["id"], "20261124T090000", "this", title="Early override")
    change(admin, event["id"], "20261127T090000", "this", title="Late override")
    remove(admin, event["id"], "20261126T090000", "this")
    follower = change(admin, event["id"], "20261125T090000", "following", title="Renamed")
    items = occurrences(admin, "2026-11-23", "2026-11-30")
    assert [(o["start"][8:10], o["title"], o["event_id"]) for o in items] == [
        ("23", "Daily", event["id"]),
        ("24", "Early override", event["id"]),
        ("25", "Renamed", follower["id"]),
        ("27", "Late override", follower["id"]),
        ("28", "Renamed", follower["id"]),
    ]


def test_following_with_a_timing_change_drops_later_exceptions(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=6", title="Daily")
    change(admin, event["id"], "20261124T090000", "this", title="Early override")
    change(admin, event["id"], "20261127T090000", "this", title="Late override")
    remove(admin, event["id"], "20261126T090000", "this")
    change(
        admin, event["id"], "20261125T090000", "following", start="2026-11-25T07:00", end="2026-11-25T08:00"
    )
    items = occurrences(admin, "2026-11-23", "2026-11-30")
    assert [(o["start"][8:16], o["title"]) for o in items] == [
        ("23T09:00", "Daily"),
        ("24T09:00", "Early override"),
        ("25T07:00", "Daily"),
        ("26T07:00", "Daily"),
        ("27T07:00", "Daily"),
        ("28T07:00", "Daily"),
    ]


def test_following_from_the_first_occurrence_is_all(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=3")
    changed = change(admin, event["id"], "20261123T090000", "following", title="All of them")
    assert changed["id"] == event["id"]
    assert {o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-30")} == {"All of them"}


def test_delete_following_only_truncates(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;COUNT=5")
    change(admin, event["id"], "20261126T090000", "this", title="Later override")
    remove(admin, event["id"], "20261125T090000", "following")
    assert starts(admin, "2026-11-23", "2026-11-30") == ["2026-11-23T09:00:00", "2026-11-24T09:00:00"]
    assert admin.get(f"/api/v1/events/{event['id']}").json()["rrule"] == "FREQ=DAILY;COUNT=2"


def test_all_day_series_split(admin: TestClient) -> None:
    event = series(admin, "FREQ=DAILY;UNTIL=20261205", all_day=True, start="2026-12-01", end="2026-12-02")
    change(admin, event["id"], "20261203T000000", "following", title="Second half")
    assert admin.get(f"/api/v1/events/{event['id']}").json()["rrule"] == "FREQ=DAILY;UNTIL=20261202"
    items = occurrences(admin, "2026-12-01", "2026-12-08")
    assert [(o["start"], o["title"]) for o in items] == [
        ("2026-12-01", "Meeting"),
        ("2026-12-02", "Meeting"),
        ("2026-12-03", "Second half"),
        ("2026-12-04", "Second half"),
        ("2026-12-05", "Second half"),
    ]


# Ownership


def test_other_users_cannot_reach_a_series(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    other = make_user()
    event = series(other, "FREQ=DAILY;COUNT=3")
    params = {"scope": "this", "occurrence": "20261124T090000"}
    assert (
        admin.get(f"/api/v1/events/{event['id']}", params={"occurrence": "20261124T090000"}).status_code
        == 404
    )
    assert admin.patch(f"/api/v1/events/{event['id']}", params=params, json={"title": "x"}).status_code == 404
    assert admin.delete(f"/api/v1/events/{event['id']}", params=params).status_code == 404
    assert len(occurrences(other, "2026-11-23", "2026-11-30")) == 3
