"""Web Push end to end against a local push service: VAPID signature and payload encryption."""

import base64
import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import http_ece
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.services.notify import devices, push


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class PushService:
    def __init__(self) -> None:
        self.requests: list[tuple[dict[str, str], bytes]] = []
        self.status = 201


@pytest.fixture
def service() -> Iterator[tuple[PushService, str]]:
    state = PushService()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            state.requests.append(({k.lower(): v for k, v in self.headers.items()}, body))
            self.send_response(state.status)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # The local push service listens on loopback, which is normally refused.
    return Settings(
        base_url="http://testserver", data_dir=tmp_path / "data", allow_private_subscription_urls=True
    )


def test_payload_is_encrypted_for_the_device_and_signed(
    app: FastAPI, admin: TestClient, settings: Settings, service: tuple[PushService, str]
) -> None:
    state, base = service
    device_key = ec.generate_private_key(ec.SECP256R1())
    device_public = device_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    auth_secret = b"0123456789abcdef"
    subscribed = admin.post(
        "/api/v1/me/push-subscriptions",
        json={"endpoint": f"{base}/device", "keys": {"p256dh": b64(device_public), "auth": b64(auth_secret)}},
    )
    assert subscribed.status_code == 204, subscribed.text
    db: Database = app.state.db
    with db.writer() as session:
        sent = push.send_payload(
            session, settings, admin.get("/api/v1/me").json()["id"], {"title": "Dentist"}
        )
        session.commit()
    assert sent == 1
    headers, body = state.requests[0]
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].startswith("vapid t=")
    vapid_key = admin.get("/api/v1/config").json()["vapid_public_key"]
    assert f"k={vapid_key}" in headers["authorization"]
    plain = http_ece.decrypt(  # pyright: ignore[reportUnknownMemberType]
        body, private_key=device_key, auth_secret=auth_secret, version="aes128gcm"
    )
    assert json.loads(plain) == {"title": "Dentist"}


def test_gone_devices_are_removed(
    app: FastAPI, admin: TestClient, settings: Settings, service: tuple[PushService, str]
) -> None:
    state, base = service
    state.status = 410
    key = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    endpoint = f"{base}/gone"
    admin.post(
        "/api/v1/me/push-subscriptions",
        json={"endpoint": endpoint, "keys": {"p256dh": b64(key), "auth": b64(b"x" * 16)}},
    )
    db: Database = app.state.db
    with db.writer() as session:
        assert push.send_payload(session, settings, admin.get("/api/v1/me").json()["id"], {"title": "x"}) == 0
        session.commit()
    assert admin.post("/api/v1/me/push-subscriptions/check", json={"endpoint": endpoint}).json() is False


def test_push_endpoints_must_be_public_https(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    strict = Settings(base_url="http://x", data_dir=tmp_path)
    real = socket.getaddrinfo

    def lookup(host: str, port: int, *args: Any, **kwargs: Any) -> Any:
        fake = {"fcm.googleapis.com": "142.250.180.10", "metadata.internal": "169.254.169.254"}
        if host in fake:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (fake[host], port))]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    assert devices.endpoint_allowed(strict, "https://fcm.googleapis.com/fcm/send/abc")
    assert not devices.endpoint_allowed(strict, "http://fcm.googleapis.com/fcm/send/abc")
    assert not devices.endpoint_allowed(strict, "https://metadata.internal/latest")
    assert not devices.endpoint_allowed(strict, "https://127.0.0.1/x")
    assert not devices.endpoint_allowed(strict, "ftp://fcm.googleapis.com/x")
