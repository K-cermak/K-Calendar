from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import Database
from app.models import Setting

SERVER = {
    "host": "mail.example.com",
    "port": 2525,
    "username": "calendar",
    "password": "mail-password",
    "from_address": "calendar@example.com",
    "security": "starttls",
}


def test_email_is_off_until_an_admin_sets_up_a_mail_server(admin: TestClient) -> None:
    assert admin.get("/api/v1/config").json()["email_enabled"] is False
    assert admin.get("/api/v1/admin/smtp").json() == {
        "host": "",
        "port": None,
        "username": "",
        "from_address": "",
        "security": "starttls",
        "password_set": False,
    }
    assert admin.put("/api/v1/admin/smtp", json=SERVER).status_code == 200
    assert admin.get("/api/v1/config").json()["email_enabled"] is True
    assert admin.get("/api/v1/admin/status").json()["smtp_configured"] is True

    # Clearing the server and the sender turns it off again.
    assert admin.put("/api/v1/admin/smtp", json={}).status_code == 200
    assert admin.get("/api/v1/config").json()["email_enabled"] is False


def test_the_password_is_never_shown_and_kept_by_a_save_without_one(app: FastAPI, admin: TestClient) -> None:
    saved = admin.put("/api/v1/admin/smtp", json=SERVER).json()
    assert "password" not in saved
    assert saved["password_set"] is True
    assert "mail-password" not in admin.get("/api/v1/admin/smtp").text

    # The form sends the other fields back with the password left empty.
    changed = admin.put("/api/v1/admin/smtp", json={**SERVER, "port": 587, "password": ""}).json()
    assert (changed["port"], changed["password_set"]) == (587, True)

    # Stored encrypted, not as written.
    db: Database = app.state.db
    with db.reader() as session:
        row = session.get(Setting, "smtp")
        assert row is not None and "mail-password" not in row.value

    # Without a user name there is no sign-in, so the password goes.
    dropped = admin.put("/api/v1/admin/smtp", json={**SERVER, "username": "", "password": ""}).json()
    assert dropped["password_set"] is False


def test_mail_server_settings_are_checked(admin: TestClient) -> None:
    def put(**changes: object) -> dict[str, object]:
        return admin.put("/api/v1/admin/smtp", json={**SERVER, **changes}).json()

    assert put(from_address="")["code"] == "smtp_incomplete"
    assert put(host="")["code"] == "smtp_incomplete"
    assert put(host="mail example.com")["code"] == "smtp_host_invalid"
    assert put(from_address="calendar")["code"] == "invalid_email"
    assert admin.put("/api/v1/admin/smtp", json={**SERVER, "port": 70000}).status_code == 422
    assert admin.put("/api/v1/admin/smtp", json={**SERVER, "security": "tls"}).status_code == 422


def test_only_an_admin_sees_or_sets_the_mail_server(make_user: Callable[..., TestClient]) -> None:
    user = make_user()
    assert user.get("/api/v1/admin/smtp").status_code == 403
    assert user.put("/api/v1/admin/smtp", json=SERVER).status_code == 403
