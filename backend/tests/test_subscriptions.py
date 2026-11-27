import socket
import threading
from collections.abc import Callable, Iterator
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import scheduler
from app.branding import get_branding
from app.config import Settings
from app.db import Database
from app.services import subscriptions
from tests.conftest import Clock
from tests.helpers import occurrences

DATA = Path(__file__).parent / "data" / "ics"


class Feed:
    """A tiny ICS server: serves a body with an ETag, answers 304 to a matching If-None-Match."""

    def __init__(self) -> None:
        self.body = (DATA / "google.ics").read_bytes()
        self.status = 200
        self.etag = '"v1"'
        self.requests: list[dict[str, str]] = []
        self.redirect_to: str | None = None


@pytest.fixture
def feed() -> Iterator[tuple[Feed, str]]:
    state = Feed()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests.append({k.lower(): v for k, v in self.headers.items()})
            if state.redirect_to and self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", state.redirect_to)
                self.end_headers()
                return
            if state.status != 200:
                self.send_response(state.status)
                self.end_headers()
                return
            if self.headers.get("If-None-Match") == state.etag:
                self.send_response(304)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.send_header("ETag", state.etag)
            self.send_header("Last-Modified", "Fri, 20 Nov 2026 10:00:00 GMT")
            self.end_headers()
            self.wfile.write(state.body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # The test server listens on loopback, which subscriptions normally refuse.
    return Settings(
        base_url="http://testserver", data_dir=tmp_path / "data", allow_private_subscription_urls=True
    )


def subscribe(client: TestClient, url: str, **extra: Any) -> dict[str, Any]:
    response = client.post("/api/v1/calendars/subscriptions", json={"url": url, "color": "green", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_subscribing_fetches_at_once_and_is_read_only(admin: TestClient, feed: tuple[Feed, str]) -> None:
    state, base = feed
    calendar = subscribe(admin, f"{base}/family.ics", name="Family")
    assert (calendar["kind"], calendar["read_only"], calendar["name"]) == ("subscription", True, "Family")
    info = calendar["subscription"]
    assert (info["last_status"], info["last_error"], info["refresh_interval_minutes"]) == ("ok", None, 60)
    assert info["last_fetched_at_utc"]
    items = occurrences(admin, "2026-11-01", "2026-12-31")
    assert len(items) == 7
    assert all(o["read_only"] for o in items)
    event_id = items[0]["event_id"]
    refused = admin.patch(
        f"/api/v1/events/{event_id}",
        params={"scope": "all", "occurrence": items[0]["occurrence"]},
        json={"title": "x"},
    )
    assert refused.json()["code"] == "read_only_calendar"
    assert admin.delete(f"/api/v1/events/{event_id}").json()["code"] == "read_only_calendar"
    assert state.requests[0]["user-agent"].startswith(f"{get_branding().name}/")


def test_refresh_sends_conditional_headers_and_keeps_events_on_304(
    admin: TestClient, feed: tuple[Feed, str]
) -> None:
    state, base = feed
    calendar = subscribe(admin, f"{base}/family.ics")
    response = admin.post(f"/api/v1/calendars/{calendar['id']}/refresh")
    assert response.json()["subscription"]["last_status"] == "ok"
    assert state.requests[1]["if-none-match"] == '"v1"'
    assert state.requests[1]["if-modified-since"] == "Fri, 20 Nov 2026 10:00:00 GMT"
    assert len(occurrences(admin, "2026-11-01", "2026-12-31")) == 7


def test_new_content_replaces_the_events(admin: TestClient, feed: tuple[Feed, str]) -> None:
    state, base = feed
    calendar = subscribe(admin, f"{base}/family.ics")
    state.body = (DATA / "apple.ics").read_bytes()
    state.etag = '"v2"'
    admin.post(f"/api/v1/calendars/{calendar['id']}/refresh")
    titles = {o["title"] for o in occurrences(admin, "2026-11-01", "2026-12-31")}
    assert titles == {"Quarterly planning", "Lunch with Ana", "Christmas break"}


def test_a_failed_refresh_keeps_the_previous_events(admin: TestClient, feed: tuple[Feed, str]) -> None:
    state, base = feed
    calendar = subscribe(admin, f"{base}/family.ics")
    state.status = 500
    state.etag = '"v2"'
    info = admin.post(f"/api/v1/calendars/{calendar['id']}/refresh").json()["subscription"]
    assert (info["last_status"], info["last_error"]) == ("error", "The server answered 500")
    assert info["last_fetched_at_utc"]
    assert len(occurrences(admin, "2026-11-01", "2026-12-31")) == 7
    state.status = 200
    state.body = b"this is not a calendar"
    info = admin.post(f"/api/v1/calendars/{calendar['id']}/refresh").json()["subscription"]
    assert info["last_status"] == "error"
    assert "not an iCalendar file" in info["last_error"]
    assert len(occurrences(admin, "2026-11-01", "2026-12-31")) == 7


def test_webcal_is_fetched_over_https(admin: TestClient) -> None:
    assert subscriptions.normalize_url("webcal://example.com/a.ics") == "https://example.com/a.ics"
    for bad in (
        "ftp://example.com/a.ics",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:pw@example.com/",
    ):
        response = admin.post("/api/v1/calendars/subscriptions", json={"url": bad, "color": "green"})
        assert response.json()["code"] == "invalid_url", bad


def test_unreachable_host_is_recorded_as_an_error(admin: TestClient) -> None:
    calendar = subscribe(admin, "http://calendar.invalid/feed.ics")
    assert calendar["subscription"]["last_status"] == "error"
    assert "could not be found" in calendar["subscription"]["last_error"]


def test_refresh_interval(admin: TestClient, feed: tuple[Feed, str]) -> None:
    _, base = feed
    calendar = subscribe(admin, f"{base}/a.ics", refresh_interval_minutes=15)
    too_short = admin.post(
        "/api/v1/calendars/subscriptions",
        json={"url": f"{base}/a.ics", "color": "green", "refresh_interval_minutes": 5},
    )
    assert too_short.status_code == 422
    changed = admin.patch(f"/api/v1/calendars/{calendar['id']}", json={"refresh_interval_minutes": 120})
    assert changed.json()["subscription"]["refresh_interval_minutes"] == 120
    local = admin.post("/api/v1/calendars", json={"name": "Local", "color": "red"}).json()
    refused = admin.patch(f"/api/v1/calendars/{local['id']}", json={"refresh_interval_minutes": 120})
    assert refused.json()["code"] == "not_subscription"
    assert admin.post(f"/api/v1/calendars/{local['id']}/refresh").json()["code"] == "not_subscription"


def test_the_background_loop_refreshes_due_subscriptions(
    app: FastAPI, admin: TestClient, feed: tuple[Feed, str], clock: Clock
) -> None:
    state, base = feed
    subscribe(admin, f"{base}/a.ics", refresh_interval_minutes=15)
    db: Database = app.state.db
    settings: Settings = app.state.settings
    scheduler.tick(db, settings)
    assert len(state.requests) == 1  # not due yet
    clock.advance(timedelta(minutes=16))
    scheduler.tick(db, settings)
    assert len(state.requests) == 2


def test_other_users_cannot_refresh(
    admin: TestClient, make_user: Callable[..., TestClient], feed: tuple[Feed, str]
) -> None:
    _, base = feed
    calendar = subscribe(admin, f"{base}/a.ics")
    other = make_user()
    assert other.post(f"/api/v1/calendars/{calendar['id']}/refresh").status_code == 404


# Server-side request forgery


def fake_dns(monkeypatch: pytest.MonkeyPatch, addresses: dict[str, str]) -> None:
    real = socket.getaddrinfo

    def lookup(host: str, port: int, *args: Any, **kwargs: Any) -> Any:
        if host in addresses:
            family = socket.AF_INET6 if ":" in addresses[host] else socket.AF_INET
            return [(family, socket.SOCK_STREAM, 6, "", (addresses[host], port))]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(subscriptions.socket, "getaddrinfo", lookup)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "192.168.1.10",
        "172.20.0.5",
        "169.254.169.254",
        "::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",  # noqa: S104 - an address to refuse, not one to bind
    ],
)
def test_private_addresses_are_refused(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    fake_dns(monkeypatch, {"evil.example": address})
    with pytest.raises(subscriptions.FetchError, match="private network"):
        subscriptions.fetch(
            "http://evil.example/feed.ics", etag=None, last_modified=None, allow_private=False
        )


def test_redirects_are_checked_at_every_hop(monkeypatch: pytest.MonkeyPatch, feed: tuple[Feed, str]) -> None:
    state, base = feed
    port = base.rsplit(":", 1)[1]
    # A host that looks public (really the loopback test server, let through for this test)
    # redirects to the metadata address of a cloud provider, which must be refused.
    fake_dns(monkeypatch, {"public.example": "127.0.0.1", "metadata.example": "169.254.169.254"})

    def allowed(address: object) -> bool:
        return str(address) != "169.254.169.254"

    monkeypatch.setattr(subscriptions, "_allowed", allowed)
    state.redirect_to = f"http://metadata.example:{port}/latest"
    with pytest.raises(subscriptions.FetchError, match="private network"):
        subscriptions.fetch(
            f"http://public.example:{port}/redirect", etag=None, last_modified=None, allow_private=False
        )
    assert len(state.requests) == 1
    assert state.requests[0]["host"] == f"public.example:{port}"


def test_large_bodies_are_cut_off(monkeypatch: pytest.MonkeyPatch, feed: tuple[Feed, str]) -> None:
    state, base = feed
    monkeypatch.setattr(subscriptions, "MAX_BYTES", 1000)
    state.body = b"X" * 5000
    with pytest.raises(subscriptions.FetchError, match="larger than 10 MB"):
        subscriptions.fetch(f"{base}/big.ics", etag=None, last_modified=None, allow_private=True)


def test_loopback_is_refused_without_the_setting(feed: tuple[Feed, str]) -> None:
    _, base = feed
    with pytest.raises(subscriptions.FetchError):
        subscriptions.fetch(f"{base}/a.ics", etag=None, last_modified=None, allow_private=False)
