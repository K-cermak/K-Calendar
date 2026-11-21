from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import count_rows, setup_admin


def test_a_new_user_gets_a_personal_calendar(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    for client in (admin, make_user()):
        calendars = client.get("/api/v1/calendars").json()
        assert [(c["name"], c["kind"], c["is_visible"], c["read_only"]) for c in calendars] == [
            ("Personal", "local", True, False)
        ]


def test_create_rename_recolour_hide(admin: TestClient) -> None:
    created = admin.post("/api/v1/calendars", json={"name": " Work ", "color": "teal"})
    assert created.status_code == 201
    work = created.json()
    assert (work["name"], work["color"], work["sort_order"]) == ("Work", "teal", 1)
    changed = admin.patch(
        f"/api/v1/calendars/{work['id']}",
        json={"name": "Job", "color": "red", "is_visible": False, "default_reminder_minutes": 10},
    ).json()
    assert (changed["name"], changed["color"], changed["is_visible"]) == ("Job", "red", False)
    assert changed["default_reminder_minutes"] == 10
    cleared = admin.patch(f"/api/v1/calendars/{work['id']}", json={"default_reminder_minutes": None})
    assert cleared.json()["default_reminder_minutes"] is None
    untouched = admin.patch(f"/api/v1/calendars/{work['id']}", json={"name": "Job 2"})
    assert untouched.json()["is_visible"] is False


def test_calendar_input_is_validated(admin: TestClient) -> None:
    assert admin.post("/api/v1/calendars", json={"name": "x", "color": "beige"}).status_code == 422
    blank = admin.post("/api/v1/calendars", json={"name": "  ", "color": "red"})
    assert blank.json()["code"] == "name_required"
    reminder = admin.post(
        "/api/v1/calendars", json={"name": "x", "color": "red", "default_reminder_minutes": -5}
    )
    assert reminder.status_code == 422


def test_reorder(admin: TestClient) -> None:
    personal = admin.get("/api/v1/calendars").json()[0]["id"]
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    ordered = admin.put("/api/v1/calendars/order", json={"ids": [work, personal]}).json()
    assert [c["id"] for c in ordered] == [work, personal]
    incomplete = admin.put("/api/v1/calendars/order", json={"ids": [work]})
    assert incomplete.json()["code"] == "invalid_order"


def test_delete_removes_events_and_keeps_the_last_calendar(admin: TestClient) -> None:
    personal = admin.get("/api/v1/calendars").json()[0]["id"]
    last = admin.delete(f"/api/v1/calendars/{personal}")
    assert last.status_code == 409
    assert last.json()["code"] == "last_calendar"
    work = admin.post("/api/v1/calendars", json={"name": "Work", "color": "teal"}).json()["id"]
    event = admin.post(
        "/api/v1/events",
        json={"calendar_id": work, "title": "x", "start": "2026-11-23T09:00", "end": "2026-11-23T10:00"},
    ).json()
    assert admin.delete(f"/api/v1/calendars/{work}").status_code == 204
    assert admin.get(f"/api/v1/events/{event['id']}").status_code == 404
    assert [c["id"] for c in admin.get("/api/v1/calendars").json()] == [personal]


def test_other_users_calendars_are_not_found(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    other = make_user()
    theirs = other.get("/api/v1/calendars").json()[0]["id"]
    assert [c["id"] for c in admin.get("/api/v1/calendars").json()] != [theirs]
    for method, path, body in [
        ("PATCH", f"/api/v1/calendars/{theirs}", {"name": "Mine now"}),
        ("DELETE", f"/api/v1/calendars/{theirs}", None),
    ]:
        response = admin.request(method, path, json=body)
        assert response.status_code == 404, (method, path)
    mine = admin.get("/api/v1/calendars").json()[0]["id"]
    sneaky = admin.put("/api/v1/calendars/order", json={"ids": [theirs, mine]})
    assert sneaky.status_code == 422
    assert other.get("/api/v1/calendars").json()[0]["name"] == "Personal"


def test_calendar_endpoints_need_a_session(client: TestClient) -> None:
    setup_admin(client)
    client.post("/api/v1/auth/logout")
    for method, path in [
        ("GET", "/api/v1/calendars"),
        ("POST", "/api/v1/calendars"),
        ("PUT", "/api/v1/calendars/order"),
        ("PATCH", "/api/v1/calendars/1"),
        ("DELETE", "/api/v1/calendars/1"),
    ]:
        assert client.request(method, path, json={}).status_code == 401, (method, path)


def test_deleting_a_user_deletes_their_calendars(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    other = make_user()
    uid = other.get("/api/v1/me").json()["id"]
    cal = other.get("/api/v1/calendars").json()[0]["id"]
    other.post(
        "/api/v1/events",
        json={"calendar_id": cal, "title": "x", "start": "2026-11-23T09:00", "end": "2026-11-23T10:00"},
    )
    assert admin.delete(f"/api/v1/admin/users/{uid}").status_code == 204
    assert (count_rows(app, "calendars"), count_rows(app, "events")) == (1, 0)
