from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import Clock, count_rows
from tests.helpers import create_event, personal


def search(client: TestClient, q: str, tz: str | None = None) -> list[dict[str, Any]]:
    params = {"q": q} | ({"tz": tz} if tz else {})
    response = client.get("/api/v1/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def titles(client: TestClient, q: str) -> list[str]:
    return [r["title"] for r in search(client, q)]


def test_diacritics_and_case_are_ignored(admin: TestClient, clock: Clock) -> None:
    create_event(admin, title="Zubař", start="2026-12-01T09:00", end="2026-12-01T10:00")
    for query in ("zubar", "ZUBAŘ", "Zub", "zubař"):
        assert titles(admin, query) == ["Zubař"], query


def test_prefixes_of_every_word_must_match(admin: TestClient, clock: Clock) -> None:
    create_event(
        admin, title="Team planning", location="Room 4", start="2026-12-01T09:00", end="2026-12-01T10:00"
    )
    create_event(admin, title="Team lunch", start="2026-12-02T12:00", end="2026-12-02T13:00")
    assert titles(admin, "team") == ["Team planning", "Team lunch"]
    assert titles(admin, "tea pla") == ["Team planning"]
    assert titles(admin, "room") == ["Team planning"]
    assert titles(admin, "nothing here") == []
    assert search(admin, '"; DROP TABLE events; --') == []
    assert search(admin, "   ") == []


def test_description_and_tags_are_searched(admin: TestClient, clock: Clock) -> None:
    create_event(
        admin, title="A", description="Bring the passports", start="2026-12-01T09:00", end="2026-12-01T10:00"
    )
    event = create_event(admin, title="B", tags=["Školka"], start="2026-12-02T09:00", end="2026-12-02T10:00")
    assert titles(admin, "passport") == ["A"]
    assert titles(admin, "skolka") == ["B"]
    tag_id = event["tags"][0]["id"]
    admin.patch(f"/api/v1/tags/{tag_id}", json={"name": "Kindergarten"})
    assert titles(admin, "skolka") == []
    assert titles(admin, "kinder") == ["B"]
    admin.delete(f"/api/v1/tags/{tag_id}")
    assert titles(admin, "kinder") == []


def test_edits_are_reflected(admin: TestClient, clock: Clock) -> None:
    event = create_event(admin, title="Dentist", start="2026-12-01T09:00", end="2026-12-01T10:00")
    admin.patch(f"/api/v1/events/{event['id']}", json={"title": "Orthodontist"})
    assert titles(admin, "dentist") == []
    assert titles(admin, "ortho") == ["Orthodontist"]
    admin.delete(f"/api/v1/events/{event['id']}")
    assert titles(admin, "ortho") == []


def test_upcoming_first_nearest_first_then_past_most_recent_first(admin: TestClient, clock: Clock) -> None:
    # The clock stands at 2026-11-20 12:00 UTC.
    for title, day in [
        ("Call far", "2026-12-20"),
        ("Call old", "2026-10-01"),
        ("Call soon", "2026-11-25"),
        ("Call recent", "2026-11-10"),
    ]:
        create_event(admin, title=title, start=f"{day}T09:00", end=f"{day}T10:00")
    results = search(admin, "call")
    assert [(r["title"], r["upcoming"]) for r in results] == [
        ("Call soon", True),
        ("Call far", True),
        ("Call recent", False),
        ("Call old", False),
    ]


def test_a_series_appears_once_at_its_next_occurrence(admin: TestClient, clock: Clock) -> None:
    event = create_event(
        admin, title="Yoga", rrule="FREQ=WEEKLY", start="2026-11-02T18:00", end="2026-11-02T19:00"
    )
    results = search(admin, "yoga")
    assert len(results) == 1
    assert (results[0]["start"], results[0]["occurrence"], results[0]["upcoming"]) == (
        "2026-11-23T18:00:00",
        "20261123T180000",
        True,
    )
    assert results[0]["occurrence_id"] == f"{event['id']}_20261123T180000"
    # A renamed occurrence still keeps the series to one result.
    admin.patch(
        f"/api/v1/events/{event['id']}",
        params={"scope": "this", "occurrence": "20261130T180000"},
        json={"title": "Yoga outdoors"},
    )
    assert len(search(admin, "yoga")) == 1
    assert [r["title"] for r in search(admin, "outdoors")] == ["Yoga outdoors"]


def test_an_ended_series_shows_its_last_occurrence(admin: TestClient, clock: Clock) -> None:
    create_event(
        admin, title="Course", rrule="FREQ=WEEKLY;COUNT=3", start="2026-09-01T18:00", end="2026-09-01T19:00"
    )
    results = search(admin, "course")
    assert [(r["start"], r["upcoming"]) for r in results] == [("2026-09-15T18:00:00", False)]


def test_results_are_given_in_the_display_zone(admin: TestClient, clock: Clock) -> None:
    create_event(admin, title="Flight", start="2026-12-01T09:00", end="2026-12-01T11:00")
    assert search(admin, "flight", "Asia/Tokyo")[0]["start"] == "2026-12-01T17:00:00"


def test_hidden_calendars_are_searched_too(admin: TestClient, clock: Clock) -> None:
    create_event(admin, title="Secret", start="2026-12-01T09:00", end="2026-12-01T10:00")
    admin.patch(f"/api/v1/calendars/{personal(admin)}", json={"is_visible": False})
    assert titles(admin, "secret") == ["Secret"]


def test_deleting_a_calendar_or_user_empties_the_index(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient], clock: Clock
) -> None:
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    create_event(admin, calendar_id=work, title="Review", start="2026-12-01T09:00", end="2026-12-01T10:00")
    other = make_user()
    create_event(other, title="Theirs", start="2026-12-01T09:00", end="2026-12-01T10:00")
    assert count_rows(app, "events_fts") == 2
    admin.delete(f"/api/v1/calendars/{work}")
    assert count_rows(app, "events_fts") == 1
    admin.delete(f"/api/v1/admin/users/{other.get('/api/v1/me').json()['id']}")
    assert count_rows(app, "events_fts") == 0


def test_only_own_events_are_found(
    admin: TestClient, make_user: Callable[..., TestClient], clock: Clock
) -> None:
    other = make_user()
    create_event(other, title="Their dentist", start="2026-12-01T09:00", end="2026-12-01T10:00")
    create_event(admin, title="My dentist", start="2026-12-01T09:00", end="2026-12-01T10:00")
    assert titles(admin, "dentist") == ["My dentist"]
    assert titles(other, "dentist") == ["Their dentist"]


def test_search_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/search", params={"q": "x"}).status_code == 401


def test_clock_moves_results_into_the_past(admin: TestClient, clock: Clock) -> None:
    create_event(admin, title="Meeting", start="2026-11-21T09:00", end="2026-11-21T10:00")
    assert search(admin, "meeting")[0]["upcoming"] is True
    clock.advance(timedelta(days=2))
    assert search(admin, "meeting")[0]["upcoming"] is False
