from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(base_url="http://testserver", data_dir=tmp_path / "data")


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>index</title>")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("self")
    return dist


@pytest.fixture
def app(settings: Settings, static_dir: Path) -> FastAPI:
    return create_app(settings, static_dir=static_dir)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def new_client(app: FastAPI, client: TestClient) -> Callable[[], TestClient]:
    """Another browser: same server, its own cookie jar. Depends on client so the app has started."""
    return lambda: TestClient(app)


ADMIN = {
    "email": "admin@example.com",
    "display_name": "Admin",
    "password": "admin-password",
    "timezone": "Europe/Prague",
}
PASSWORD = "user-password"


class Clock:
    """Frozen time that a test moves forward on purpose (time-machine under the hood)."""

    def __init__(self, traveller: time_machine.TimeMachineFixture) -> None:
        self._traveller = traveller
        traveller.move_to(datetime(2026, 11, 20, 12, 0, tzinfo=UTC), tick=False)

    def advance(self, delta: timedelta) -> None:
        self._traveller.shift(delta)


@pytest.fixture
def clock(time_machine: time_machine.TimeMachineFixture) -> Clock:
    return Clock(time_machine)


def setup_admin(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/auth/setup", json=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    """The default client, signed in as the first admin."""
    setup_admin(client)
    return client


def invite_url(admin: TestClient, email: str | None = None) -> str:
    response = admin.post("/api/v1/admin/invites", json={"email": email})
    assert response.status_code == 201, response.text
    return response.json()["url"]


def token_of(url: str) -> str:
    return url.rsplit("/", 1)[1]


@pytest.fixture
def make_user(admin: TestClient, new_client: Callable[[], TestClient]) -> Callable[..., TestClient]:
    """Invite and sign up a user; returns their signed-in client."""

    def make(
        email: str = "user@example.com", display_name: str = "User", timezone: str = "UTC"
    ) -> TestClient:
        user = new_client()
        response = user.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": token_of(invite_url(admin)),
                "email": email,
                "display_name": display_name,
                "password": PASSWORD,
                "timezone": timezone,
            },
        )
        assert response.status_code == 201, response.text
        return user

    return make


def user_id(client: TestClient) -> int:
    return client.get("/api/v1/me").json()["id"]


def count_rows(app: FastAPI, table: str) -> int:
    db: Database = app.state.db
    with db.reader() as session:
        return session.connection().exec_driver_sql(f"SELECT count(*) FROM {table}").scalar() or 0  # noqa: S608
