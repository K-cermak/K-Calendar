from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import DAY_MS, FakeClock, user_id
from tests.helpers import create_event, personal


def make_token(client: TestClient, scope: str = "read", **extra: Any) -> dict[str, Any]:
    response = client.post("/api/v1/me/tokens", json={"name": "Script", "scope": scope, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def test_token_is_shown_once_with_a_recognisable_prefix(admin: TestClient) -> None:
    created = make_token(admin, expires_in_days=30)
    assert created["token"].startswith("cal_")
    assert created["prefix"] == created["token"][:12]
    listed = admin.get("/api/v1/me/tokens").json()
    assert [t["prefix"] for t in listed] == [created["prefix"]]
    assert "token" not in listed[0]
    assert listed[0]["expires_at_utc"]


def test_read_token_reads_calendar_data_and_nothing_else(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    create_event(admin, title="Visible")
    token = make_token(admin)["token"]
    script = new_client()
    occurrences = script.get(
        "/api/v1/occurrences", params={"start": "2026-11-23", "end": "2026-11-24"}, headers=bearer(token)
    )
    assert [o["title"] for o in occurrences.json()["items"]] == ["Visible"]
    assert script.get("/api/v1/calendars", headers=bearer(token)).status_code == 200
    assert script.get("/api/v1/search", params={"q": "vis"}, headers=bearer(token)).status_code == 200
    refused = script.post(
        "/api/v1/events",
        json={"calendar_id": personal(admin), "start": "2026-11-23T09:00", "end": "2026-11-23T10:00"},
        headers=bearer(token),
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "insufficient_scope"
    for method, path in [
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/me/tokens"),
        ("POST", "/api/v1/me/tokens"),
        ("POST", "/api/v1/me/password"),
        ("GET", "/api/v1/me/sessions"),
        ("POST", "/api/v1/me/totp/setup"),
        ("DELETE", "/api/v1/me/oidc"),
        ("GET", "/api/v1/admin/users"),
    ]:
        response = script.request(method, path, json={}, headers=bearer(token))
        assert response.status_code == 403, (method, path)
        assert response.json()["code"] == "token_not_allowed"


def test_write_token_changes_calendar_data_from_anywhere(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    token = make_token(admin, scope="write")["token"]
    script = new_client()
    # A script is not a browser: the cross-site check does not apply to Bearer requests.
    headers = bearer(token) | {"origin": "https://elsewhere.test"}
    created = script.post(
        "/api/v1/events",
        json={
            "calendar_id": personal(admin),
            "title": "From a script",
            "start": "2026-11-23T09:00",
            "end": "2026-11-23T10:00",
        },
        headers=headers,
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert (
        script.patch(f"/api/v1/events/{event_id}", json={"title": "Changed"}, headers=headers).status_code
        == 200
    )
    assert script.delete(f"/api/v1/events/{event_id}", headers=headers).status_code == 204


def test_invalid_expired_and_revoked_tokens_are_refused(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    script = new_client()
    for header in ("Bearer cal_nonsense", "Bearer nothing", "Basic abc"):
        response = script.get("/api/v1/calendars", headers={"authorization": header})
        assert response.status_code == 401, header
    expiring = make_token(admin, expires_in_days=1)["token"]
    assert script.get("/api/v1/calendars", headers=bearer(expiring)).status_code == 200
    fake_clock.advance(DAY_MS + 1)
    assert script.get("/api/v1/calendars", headers=bearer(expiring)).status_code == 401
    revoked = make_token(admin)
    assert admin.delete(f"/api/v1/me/tokens/{revoked['id']}").status_code == 204
    assert script.get("/api/v1/calendars", headers=bearer(revoked["token"])).status_code == 401
    assert all(t["id"] != revoked["id"] for t in admin.get("/api/v1/me/tokens").json())


def test_a_deactivated_users_tokens_stop_working(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    user = make_user()
    token = make_token(user)["token"]
    script = new_client()
    assert script.get("/api/v1/calendars", headers=bearer(token)).status_code == 200
    admin.patch(f"/api/v1/admin/users/{user_id(user)}", json={"is_active": False})
    assert script.get("/api/v1/calendars", headers=bearer(token)).status_code == 401


def test_tokens_see_only_their_owners_data(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    other = make_user()
    theirs = create_event(other, title="Theirs")
    token = make_token(admin, scope="write")["token"]
    script = new_client()
    assert script.get(f"/api/v1/events/{theirs['id']}", headers=bearer(token)).status_code == 404
    assert script.delete(f"/api/v1/events/{theirs['id']}", headers=bearer(token)).status_code == 404
    other_token = make_token(other)
    assert admin.delete(f"/api/v1/me/tokens/{other_token['id']}").status_code == 404


def test_last_use_is_recorded(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    created = make_token(admin)
    assert admin.get("/api/v1/me/tokens").json()[0]["last_used_at_utc"] is None
    new_client().get("/api/v1/calendars", headers=bearer(created["token"]))
    assert admin.get("/api/v1/me/tokens").json()[0]["last_used_at_utc"] is not None


def test_token_management_needs_a_session(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/me/tokens"),
        ("POST", "/api/v1/me/tokens"),
        ("DELETE", "/api/v1/me/tokens/1"),
    ]:
        assert client.request(method, path, json={}).status_code == 401, (method, path)
