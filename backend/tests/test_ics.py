from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import create_event, occurrences, personal

DATA = Path(__file__).parent / "data" / "ics"


def upload(client: TestClient, calendar_id: int, content: bytes, name: str = "file.ics") -> Any:
    return client.post(
        f"/api/v1/calendars/{calendar_id}/import", files={"file": (name, content, "text/calendar")}
    )


def import_file(client: TestClient, fixture: str, calendar_id: int | None = None) -> dict[str, Any]:
    response = upload(client, calendar_id or personal(client), (DATA / fixture).read_bytes(), fixture)
    assert response.status_code == 200, response.text
    return response.json()


def summary(client: TestClient, start: str, end: str, tz: str = "Europe/Prague") -> list[tuple[str, str]]:
    return [(o["title"], o["start"]) for o in occurrences(client, start, end, tz)]


# Import


def test_google_export(admin: TestClient) -> None:
    result = import_file(admin, "google.ics")
    assert (result["created"], result["updated"], result["skipped"]) == (3, 0, [])
    assert summary(admin, "2026-11-01", "2026-12-31") == [
        ("Swimming lessons", "2026-11-02T18:00:00"),
        ("Swimming lessons", "2026-11-09T18:00:00"),
        # 16 November is an EXDATE, 23 November moved to Tuesday 17:00.
        ("Swimming lessons (moved)", "2026-11-24T17:00:00"),
        ("Swimming lessons", "2026-11-30T18:00:00"),
        ("Zubař", "2026-12-01T09:00:00"),
        ("Swimming lessons", "2026-12-07T18:00:00"),
        # UNTIL is 17:59:59 in Prague on the 21st, so that day's 18:00 is not part of the series.
        ("Swimming lessons", "2026-12-14T18:00:00"),
    ]
    swimming = occurrences(admin, "2026-11-02", "2026-11-03")[0]
    detail = admin.get(f"/api/v1/events/{swimming['event_id']}").json()
    assert detail["location"] == "City pool, Main Street 5"
    # UNTIL came in UTC and is stored as wall-clock time in the event's zone.
    assert set(detail["rrule"].split(";")) == {"FREQ=WEEKLY", "WKST=MO", "UNTIL=20261221T175959", "BYDAY=MO"}
    assert detail["timezone"] == "Europe/Prague"
    birthday = occurrences(admin, "2027-05-01", "2027-05-31")
    assert [(o["title"], o["start"], o["all_day"]) for o in birthday] == [
        ("Mum's birthday", "2027-05-03", True)
    ]


def test_apple_export(admin: TestClient) -> None:
    result = import_file(admin, "apple.ics")
    assert (result["created"], result["skipped"]) == (3, [])
    items = {o["title"]: o for o in occurrences(admin, "2026-11-20", "2026-12-31", "America/New_York")}
    planning = items["Quarterly planning"]
    assert (planning["start"], planning["end"]) == ("2026-11-23T09:00:00", "2026-11-23T11:00:00")
    assert sorted(t["name"] for t in planning["tags"]) == ["Planning", "Work"]
    # A floating time means the owner's own zone: noon in Prague.
    assert items["Lunch with Ana"]["start"] == "2026-11-25T06:00:00"
    assert (items["Christmas break"]["start"], items["Christmas break"]["end"]) == (
        "2026-12-24",
        "2026-12-27",
    )


def test_outlook_export_with_windows_zone_names(admin: TestClient) -> None:
    result = import_file(admin, "outlook.ics")
    assert (result["created"], result["skipped"]) == (1, [])
    standups = summary(admin, "2026-11-23", "2026-11-30")
    # Five days from the 23rd, without the EXDATE on the 25th and the cancelled 26th.
    assert standups == [
        ("Daily stand-up", "2026-11-23T08:00:00"),
        ("Daily stand-up", "2026-11-24T08:00:00"),
        ("Daily stand-up", "2026-11-27T08:00:00"),
    ]
    detail = admin.get(
        f"/api/v1/events/{occurrences(admin, '2026-11-23', '2026-11-24')[0]['event_id']}"
    ).json()
    assert detail["timezone"] in {"Europe/Budapest", "Europe/Prague", "Europe/Warsaw", "Europe/Belgrade"}


def test_malformed_events_are_skipped_with_reasons(admin: TestClient) -> None:
    result = import_file(admin, "malformed.ics")
    assert result["created"] == 1
    reasons = {s["uid"]: s["reason"] for s in result["skipped"]}
    assert set(reasons) == {"no-start", "secondly", "backwards", "bad-day", "orphan", ""}
    assert "start" in reasons["no-start"]
    assert "secondly" in reasons["secondly"]
    assert [o["title"] for o in occurrences(admin, "2026-11-23", "2026-11-24")] == ["Fine event"]


def test_importing_the_same_file_twice_duplicates_nothing(admin: TestClient) -> None:
    import_file(admin, "google.ics")
    again = import_file(admin, "google.ics")
    assert (again["created"], again["updated"]) == (0, 3)
    assert len(occurrences(admin, "2026-11-01", "2026-12-31")) == 7


def test_not_a_calendar_and_too_large(admin: TestClient) -> None:
    cal = personal(admin)
    assert upload(admin, cal, b"hello").json()["code"] == "invalid_ics"
    big = b"BEGIN:VCALENDAR\r\n" + b"X" * (10 * 1024 * 1024)
    response = upload(admin, cal, big)
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


# Export


def test_export_and_import_round_trip(admin: TestClient) -> None:
    source = personal(admin)
    series = create_event(admin, title="Weekly", rrule="FREQ=WEEKLY;UNTIL=20261221T235959", tags=["team"])
    admin.patch(
        f"/api/v1/events/{series['id']}",
        params={"scope": "this", "occurrence": "20261130T090000"},
        json={"title": "Moved", "start": "2026-12-01T15:00", "end": "2026-12-01T16:00"},
    )
    admin.delete(f"/api/v1/events/{series['id']}", params={"scope": "this", "occurrence": "20261207T090000"})
    create_event(admin, title="Trip", all_day=True, start="2026-12-10", end="2026-12-13", location="Vienna")
    create_event(
        admin,
        title="New York call",
        timezone="America/New_York",
        start="2026-12-02T10:00",
        end="2026-12-02T11:00",
    )
    before = occurrences(admin, "2026-11-20", "2026-12-31")

    response = admin.get(f"/api/v1/calendars/{source}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" in response.headers["content-disposition"]
    body = response.content
    assert b"BEGIN:VTIMEZONE" in body
    assert b"UNTIL=20261221T225959Z" in body  # wall-clock UNTIL goes out in UTC

    target = admin.post("/api/v1/calendars", json={"name": "Copy", "color": "teal"}).json()["id"]
    admin.patch(f"/api/v1/calendars/{source}", json={"is_visible": False})
    result = upload(admin, target, body).json()
    assert (result["created"], result["skipped"]) == (3, [])
    after = occurrences(admin, "2026-11-20", "2026-12-31")

    def comparable(items: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
        return [
            (o["title"], o["start"], o["end"], o["all_day"], [t["name"] for t in o["tags"]]) for o in items
        ]

    assert comparable(after) == comparable(before)


def test_export_of_another_users_calendar_is_not_found(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    other = make_user()
    assert admin.get(f"/api/v1/calendars/{personal(other)}/export").status_code == 404
    assert upload(admin, personal(other), (DATA / "google.ics").read_bytes()).status_code == 404


# Feed


def test_feed_is_served_without_login_and_can_be_replaced_or_removed(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    cal = personal(admin)
    create_event(admin, title="Visible in the feed")
    assert admin.get("/api/v1/calendars").json()[0]["feed_url"] is None
    url = admin.put(f"/api/v1/calendars/{cal}/feed").json()["feed_url"]
    assert url.startswith("http://testserver/feeds/") and url.endswith(".ics")
    path = url.removeprefix("http://testserver")
    anonymous = new_client()
    response = anonymous.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    assert b"SUMMARY:Visible in the feed" in response.content

    new_url = admin.put(f"/api/v1/calendars/{cal}/feed").json()["feed_url"]
    assert new_url != url
    assert anonymous.get(path).status_code == 404
    assert anonymous.get(new_url.removeprefix("http://testserver")).status_code == 200
    assert admin.delete(f"/api/v1/calendars/{cal}/feed").status_code == 204
    assert anonymous.get(new_url.removeprefix("http://testserver")).status_code == 404
    assert anonymous.get("/feeds/.ics").status_code == 404


def test_feed_of_another_users_calendar_cannot_be_managed(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    other = make_user()
    theirs = personal(other)
    assert admin.put(f"/api/v1/calendars/{theirs}/feed").status_code == 404
    assert admin.delete(f"/api/v1/calendars/{theirs}/feed").status_code == 404


def test_ics_endpoints_need_a_session(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/calendars/1/export"),
        ("POST", "/api/v1/calendars/1/import"),
        ("PUT", "/api/v1/calendars/1/feed"),
        ("DELETE", "/api/v1/calendars/1/feed"),
        ("POST", "/api/v1/calendars/1/refresh"),
        ("POST", "/api/v1/calendars/subscriptions"),
    ]:
        assert client.request(method, path).status_code == 401, (method, path)
