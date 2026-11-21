from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import Database
from app.models import Calendar
from tests.helpers import create_event, personal


def test_timed_event_uses_the_profile_zone_by_default(admin: TestClient) -> None:
    event = create_event(admin, title="  Standup  ", location=" Room 4 ")
    assert (event["title"], event["location"]) == ("Standup", "Room 4")
    assert (event["start"], event["end"], event["timezone"]) == (
        "2026-11-23T09:00:00",
        "2026-11-23T10:00:00",
        "Europe/Prague",
    )
    assert event["all_day"] is False
    assert event["uid"]
    assert event["rrule"] is None
    assert event["read_only"] is False


def test_explicit_zone_is_kept(admin: TestClient) -> None:
    event = create_event(admin, timezone="America/New_York")
    assert (event["start"], event["timezone"]) == ("2026-11-23T09:00:00", "America/New_York")


def test_values_from_another_display_zone_are_converted_into_the_event_zone(admin: TestClient) -> None:
    # Dragged in a grid shown in New York time, to 03:00 there; the event lives in Prague.
    event = create_event(
        admin,
        start="2026-11-23T03:00:00",
        end="2026-11-23T04:00:00",
        timezone="Europe/Prague",
        input_timezone="America/New_York",
    )
    assert (event["start"], event["end"]) == ("2026-11-23T09:00:00", "2026-11-23T10:00:00")


def test_all_day_event_has_no_zone_and_an_exclusive_end(admin: TestClient) -> None:
    event = create_event(admin, all_day=True, start="2026-05-03", end="2026-05-04", timezone="Asia/Tokyo")
    assert (event["start"], event["end"], event["timezone"]) == ("2026-05-03", "2026-05-04", None)
    empty = admin.post(
        "/api/v1/events",
        json={"calendar_id": personal(admin), "all_day": True, "start": "2026-05-03", "end": "2026-05-03"},
    )
    assert empty.json()["code"] == "invalid_span"


def test_event_input_is_validated(admin: TestClient) -> None:
    cal = personal(admin)
    cases = [
        ({"start": "2026-11-23T10:00", "end": "2026-11-23T09:00"}, "invalid_span"),
        ({"start": "2026-11-23T09:00+01:00", "end": "2026-11-23T10:00"}, "invalid_datetime"),
        ({"start": "soon", "end": "2026-11-23T10:00"}, "invalid_datetime"),
        (
            {"start": "2026-11-23T09:00", "end": "2026-11-23T10:00", "timezone": "Mars/Base"},
            "invalid_timezone",
        ),
        ({"start": "2026-11-23T09:00", "end": "2026-11-23T10:00", "color": "beige"}, "validation_error"),
    ]
    for fields, code in cases:
        response = admin.post("/api/v1/events", json={"calendar_id": cal, **fields})
        assert response.json()["code"] == code, fields
    zero = admin.post(
        "/api/v1/events", json={"calendar_id": cal, "start": "2026-11-23T09:00", "end": "2026-11-23T09:00"}
    )
    assert zero.status_code == 201


def test_update_fields_and_times(admin: TestClient) -> None:
    event = create_event(admin, tags=["kids"])
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    updated = admin.patch(
        f"/api/v1/events/{event['id']}",
        json={
            "calendar_id": work,
            "title": "Review",
            "description": "See https://example.com",
            "color": "violet",
            "start": "2026-11-24T14:00",
            "end": "2026-11-24T15:30",
            "tags": ["travel"],
        },
    ).json()
    assert updated["calendar_id"] == work
    assert (updated["title"], updated["color"]) == ("Review", "violet")
    assert (updated["start"], updated["end"]) == ("2026-11-24T14:00:00", "2026-11-24T15:30:00")
    assert [t["name"] for t in updated["tags"]] == ["travel"]
    cleared = admin.patch(f"/api/v1/events/{event['id']}", json={"color": None}).json()
    assert cleared["color"] is None
    assert cleared["title"] == "Review"


def test_changing_the_zone_keeps_the_wall_clock_time(admin: TestClient) -> None:
    event = create_event(admin)
    moved = admin.patch(f"/api/v1/events/{event['id']}", json={"timezone": "Asia/Tokyo"}).json()
    assert (moved["start"], moved["timezone"]) == ("2026-11-23T09:00:00", "Asia/Tokyo")


def test_switching_all_day_needs_new_times(admin: TestClient) -> None:
    event = create_event(admin)
    missing = admin.patch(f"/api/v1/events/{event['id']}", json={"all_day": True})
    assert missing.json()["code"] == "times_required"
    all_day = admin.patch(
        f"/api/v1/events/{event['id']}", json={"all_day": True, "start": "2026-11-23", "end": "2026-11-24"}
    ).json()
    assert (all_day["start"], all_day["timezone"]) == ("2026-11-23", None)
    timed = admin.patch(
        f"/api/v1/events/{event['id']}",
        json={"all_day": False, "start": "2026-11-23T08:00", "end": "2026-11-23T08:30"},
    ).json()
    assert (timed["start"], timed["timezone"]) == ("2026-11-23T08:00:00", "Europe/Prague")


def test_delete(admin: TestClient) -> None:
    event = create_event(admin)
    assert admin.delete(f"/api/v1/events/{event['id']}").status_code == 204
    assert admin.get(f"/api/v1/events/{event['id']}").status_code == 404
    assert admin.delete(f"/api/v1/events/{event['id']}").status_code == 404


def test_subscription_calendars_are_read_only(app: FastAPI, admin: TestClient) -> None:
    db: Database = app.state.db
    user_id = admin.get("/api/v1/me").json()["id"]
    with db.writer() as session:
        calendar = Calendar(user_id=user_id, name="Holidays", color="green", kind="subscription")
        session.add(calendar)
        session.commit()
        subscription = calendar.id
    event = create_event(admin)
    refused = admin.post(
        "/api/v1/events",
        json={"calendar_id": subscription, "start": "2026-11-23T09:00", "end": "2026-11-23T10:00"},
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "read_only_calendar"
    moved = admin.patch(f"/api/v1/events/{event['id']}", json={"calendar_id": subscription})
    assert moved.json()["code"] == "read_only_calendar"


def test_other_users_events_are_not_found(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    other = make_user()
    theirs = create_event(other, title="Private")
    their_calendar = personal(other)
    mine = create_event(admin)
    assert admin.get(f"/api/v1/events/{theirs['id']}").status_code == 404
    assert admin.patch(f"/api/v1/events/{theirs['id']}", json={"title": "x"}).status_code == 404
    assert admin.delete(f"/api/v1/events/{theirs['id']}").status_code == 404
    planted = admin.post(
        "/api/v1/events",
        json={"calendar_id": their_calendar, "start": "2026-11-23T09:00", "end": "2026-11-23T10:00"},
    )
    assert planted.status_code == 404
    moved = admin.patch(f"/api/v1/events/{mine['id']}", json={"calendar_id": their_calendar})
    assert moved.status_code == 404
    assert other.get(f"/api/v1/events/{theirs['id']}").json()["title"] == "Private"


def test_event_endpoints_need_a_session(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/occurrences?start=2026-11-23&end=2026-11-30"),
        ("POST", "/api/v1/events"),
        ("GET", "/api/v1/events/1"),
        ("PATCH", "/api/v1/events/1"),
        ("DELETE", "/api/v1/events/1"),
    ]:
        assert client.request(method, path, json={}).status_code == 401, (method, path)
