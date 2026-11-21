from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from tests.conftest import Clock
from tests.helpers import create_event, occurrences, personal


def test_a_week_in_two_display_zones(admin: TestClient) -> None:
    create_event(admin, title="Standup", start="2026-11-23T09:00", end="2026-11-23T09:15")
    prague = occurrences(admin, "2026-11-23", "2026-11-30", "Europe/Prague")
    new_york = occurrences(admin, "2026-11-23", "2026-11-30", "America/New_York")
    assert [(o["start"], o["end"]) for o in prague] == [("2026-11-23T09:00:00", "2026-11-23T09:15:00")]
    assert [(o["start"], o["end"]) for o in new_york] == [("2026-11-23T03:00:00", "2026-11-23T03:15:00")]
    assert prague[0]["start_utc"] == new_york[0]["start_utc"] == "2026-11-23T08:00:00Z"


def test_display_zone_defaults_to_the_profile(admin: TestClient) -> None:
    create_event(admin, start="2026-11-23T09:00", end="2026-11-23T10:00", timezone="UTC")
    response = admin.get("/api/v1/occurrences", params={"start": "2026-11-23", "end": "2026-11-24"}).json()
    assert response["timezone"] == "Europe/Prague"
    assert response["items"][0]["start"] == "2026-11-23T10:00:00"


def test_occurrence_fields(admin: TestClient) -> None:
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    plain = create_event(admin, calendar_id=work, title="Plain", tags=["kids"])
    coloured = create_event(
        admin,
        calendar_id=work,
        title="Own colour",
        color="pink",
        start="2026-11-23T11:00",
        end="2026-11-23T12:00",
    )
    items = {o["title"]: o for o in occurrences(admin, "2026-11-23", "2026-11-24")}
    assert items["Plain"]["id"] == str(plain["id"])
    assert items["Plain"]["event_id"] == plain["id"]
    assert items["Plain"]["calendar_id"] == work
    assert items["Plain"]["color"] == "teal"
    assert items["Own colour"]["color"] == "pink"
    assert items["Own colour"]["event_id"] == coloured["id"]
    assert [t["name"] for t in items["Plain"]["tags"]] == ["kids"]
    assert items["Plain"]["recurring"] is False
    assert items["Plain"]["read_only"] is False


def test_now_is_given_in_the_display_zone(admin: TestClient, clock: Clock) -> None:
    clock.advance(timedelta(0))  # frozen at 2026-11-20 12:00 UTC
    response = admin.get(
        "/api/v1/occurrences", params={"start": "2026-11-20", "end": "2026-11-21", "tz": "Asia/Tokyo"}
    )
    assert response.json()["now"] == "2026-11-20T21:00:00"


def test_all_day_events_keep_their_date_in_every_zone(admin: TestClient) -> None:
    create_event(admin, title="Birthday", all_day=True, start="2026-05-03", end="2026-05-04")
    for zone in ("Pacific/Kiritimati", "Etc/GMT+12", "Europe/Prague", "America/Los_Angeles"):
        items = occurrences(admin, "2026-05-03", "2026-05-04", zone)
        assert [(o["start"], o["end"], o["all_day"]) for o in items] == [
            ("2026-05-03", "2026-05-04", True)
        ], zone
        assert occurrences(admin, "2026-05-02", "2026-05-03", zone) == [], zone
        assert occurrences(admin, "2026-05-04", "2026-05-05", zone) == [], zone


def test_multi_day_all_day_event_and_exclusive_end(admin: TestClient) -> None:
    create_event(admin, title="Trip", all_day=True, start="2026-07-10", end="2026-07-13")
    assert len(occurrences(admin, "2026-07-12", "2026-07-13", "Pacific/Kiritimati")) == 1
    assert occurrences(admin, "2026-07-13", "2026-07-14", "Etc/GMT+12") == []


def test_range_boundaries(admin: TestClient) -> None:
    def make(title: str, start: str, end: str) -> None:
        create_event(admin, title=title, start=start, end=end, timezone="UTC")

    make("spans the start", "2026-11-22T23:00", "2026-11-23T01:00")
    make("spans the end", "2026-11-23T23:30", "2026-11-24T00:30")
    make("spans everything", "2026-11-20T00:00", "2026-11-30T00:00")
    make("ends at the start", "2026-11-22T23:00", "2026-11-23T00:00")
    make("starts at the end", "2026-11-24T00:00", "2026-11-24T01:00")
    make("instant at the start", "2026-11-23T00:00", "2026-11-23T00:00")
    make("instant at the end", "2026-11-24T00:00", "2026-11-24T00:00")
    titles = {o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-24", "UTC")}
    assert titles == {"spans the start", "spans the end", "spans everything", "instant at the start"}


def test_range_bounds_may_be_instants(admin: TestClient) -> None:
    create_event(admin, start="2026-11-23T09:00", end="2026-11-23T10:00")  # 08:00 UTC
    inside = occurrences(admin, "2026-11-23T07:30:00Z", "2026-11-23T08:30:00Z", "Asia/Tokyo")
    assert len(inside) == 1
    assert occurrences(admin, "2026-11-23T10:00:00+01:00", "2026-11-23T12:00:00+01:00", "Asia/Tokyo") == []


def test_ordering_is_by_start(admin: TestClient) -> None:
    create_event(admin, title="Later", start="2026-11-23T15:00", end="2026-11-23T16:00")
    create_event(admin, title="Earlier", start="2026-11-23T08:00", end="2026-11-23T09:00")
    create_event(admin, title="All day", all_day=True, start="2026-11-23", end="2026-11-24")
    titles = [o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-24")]
    assert titles == ["All day", "Earlier", "Later"]


def test_daylight_saving_week(admin: TestClient) -> None:
    # The week Prague falls back: the same 09:00 local is 08:00 UTC before and 08:00 UTC after only
    # because the offset changes from +2 to +1.
    create_event(admin, title="Before", start="2026-10-23T09:00", end="2026-10-23T10:00")
    create_event(admin, title="After", start="2026-10-26T09:00", end="2026-10-26T10:00")
    items = {o["title"]: o for o in occurrences(admin, "2026-10-19", "2026-10-26T23:00", "Europe/Prague")}
    assert items["Before"]["start_utc"] == "2026-10-23T07:00:00Z"
    assert items["After"]["start_utc"] == "2026-10-26T08:00:00Z"
    assert items["Before"]["start"] == "2026-10-23T09:00:00"
    assert items["After"]["start"] == "2026-10-26T09:00:00"


def test_hidden_calendars_are_left_out(admin: TestClient) -> None:
    cal = personal(admin)
    create_event(admin)
    admin.patch(f"/api/v1/calendars/{cal}", json={"is_visible": False})
    assert occurrences(admin, "2026-11-23", "2026-11-24") == []
    admin.patch(f"/api/v1/calendars/{cal}", json={"is_visible": True})
    assert len(occurrences(admin, "2026-11-23", "2026-11-24")) == 1


def test_range_limits(admin: TestClient) -> None:
    too_long = admin.get("/api/v1/occurrences", params={"start": "2026-01-01", "end": "2027-02-10"})
    assert too_long.json()["code"] == "range_too_long"
    backwards = admin.get("/api/v1/occurrences", params={"start": "2026-02-01", "end": "2026-01-01"})
    assert backwards.json()["code"] == "invalid_range"
    nonsense = admin.get("/api/v1/occurrences", params={"start": "x", "end": "2026-01-01"})
    assert nonsense.json()["code"] == "invalid_datetime"
    bad_zone = admin.get(
        "/api/v1/occurrences", params={"start": "2026-01-01", "end": "2026-01-02", "tz": "X"}
    )
    assert bad_zone.json()["code"] == "invalid_timezone"
    assert (
        admin.get("/api/v1/occurrences", params={"start": "2026-01-01", "end": "2027-02-04"}).status_code
        == 200
    )


def test_only_own_events_are_listed(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    other = make_user()
    create_event(other, title="Theirs")
    create_event(admin, title="Mine")
    assert [o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-24")] == ["Mine"]
    assert [o["title"] for o in occurrences(other, "2026-11-23", "2026-11-24")] == ["Theirs"]
