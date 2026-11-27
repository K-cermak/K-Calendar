from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import scheduler
from app.branding import get_branding
from app.config import Settings
from app.db import Database
from app.models import NotificationLog, Reminder
from app.services.reminders import Delivery, DeliveryError, Sender
from tests.helpers import create_event, personal


class Outbox:
    """Stands in for push and SMTP: records what would have been sent, or fails on request."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.failing: set[str] = set()

    def sender(self, channel: str) -> Sender:
        def send(_db: Any, _settings: Settings, delivery: Delivery) -> None:
            if channel in self.failing:
                raise DeliveryError(f"{channel} is down")
            self.sent.append((channel, delivery.occurrence_id, delivery.shown.title))

        return send

    def senders(self) -> dict[str, Sender]:
        return {"push": self.sender("push"), "email": self.sender("email")}


@pytest.fixture(autouse=True)
def public_push_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """The made-up push hosts in these tests do not resolve; the address check has its own tests."""
    from app.services.notify import devices

    monkeypatch.setattr(devices, "endpoint_allowed", lambda _settings, _endpoint: True)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]


@pytest.fixture
def travel(time_machine: time_machine.TimeMachineFixture) -> Callable[[str], None]:
    """Moves the frozen clock to a UTC moment given as text."""

    def to(moment: str) -> None:
        time_machine.move_to(datetime.fromisoformat(moment).replace(tzinfo=UTC), tick=False)

    to("2026-11-20T12:00:00")
    return to


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


@pytest.fixture
def run(app: FastAPI, settings: Settings, outbox: Outbox) -> Callable[[], None]:
    def tick() -> None:
        db: Database = app.state.db
        scheduler.send_reminders(db, settings, outbox.senders())

    return tick


MAIL_SERVER = {
    "host": "mail.example.com",
    "username": "calendar",
    "password": "mail-password",
    "from_address": "calendar@example.com",
}


@pytest.fixture
def mail_server(admin: TestClient) -> None:
    """E-mail set up in the administration, as an admin does."""
    assert admin.put("/api/v1/admin/smtp", json=MAIL_SERVER).status_code == 200


@pytest.fixture
def channels(admin: TestClient, mail_server: None) -> Iterator[TestClient]:
    """The admin with a phone subscribed for push and e-mail reminders switched on."""
    admin.post(
        "/api/v1/me/push-subscriptions",
        json={"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "key", "auth": "secret"}},
    )
    admin.patch("/api/v1/me", json={"email_reminders_enabled": True})
    yield admin


def next_fire(app: FastAPI) -> list[str | None]:
    db: Database = app.state.db
    with db.reader() as session:
        return [
            r.next_fire_at_utc.isoformat() if r.next_fire_at_utc else None
            for r in session.scalars(select(Reminder).order_by(Reminder.id))
        ]


def test_reminder_is_sent_once_on_each_channel(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    # 09:00 in Prague is 08:00 UTC; a five-minute reminder is due at 07:55 UTC.
    event = create_event(
        channels, title="Dentist", start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5]
    )
    assert event["reminders"] == [5]
    assert next_fire(app) == ["2026-11-23T07:55:00+00:00"]
    travel("2026-11-23T07:54:30")
    run()
    assert outbox.sent == []
    travel("2026-11-23T07:55:10")
    run()
    run()
    assert sorted(outbox.sent) == [
        ("email", str(event["id"]), "Dentist"),
        ("push", str(event["id"]), "Dentist"),
    ]
    assert next_fire(app) == [None]


def test_a_weekly_series_reminds_every_week_at_local_time_across_dst(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    channels.patch("/api/v1/me", json={"email_reminders_enabled": False})
    event = create_event(
        channels,
        title="Sync",
        rrule="FREQ=WEEKLY;COUNT=3",
        start="2026-10-19T09:00",
        end="2026-10-19T10:00",
        reminders=[10],
    )
    travel("2026-10-18T12:00:00")
    channels.patch(f"/api/v1/events/{event['id']}", json={"reminders": [10]})
    # Before the change Prague is UTC+2, after it UTC+1: 08:50 local is 06:50 then 07:50 UTC.
    assert next_fire(app) == ["2026-10-19T06:50:00+00:00"]
    for moment in ("2026-10-19T06:50:05", "2026-10-26T07:50:05", "2026-11-02T07:50:05"):
        travel(moment)
        run()
    assert [occurrence for _, occurrence, _ in outbox.sent] == [
        f"{event['id']}_20261019T090000",
        f"{event['id']}_20261026T090000",
        f"{event['id']}_20261102T090000",
    ]
    assert next_fire(app) == [None]


def test_new_york_reminders_across_dst(
    app: FastAPI, channels: TestClient, travel: Callable[[str], None]
) -> None:
    travel("2026-10-30T12:00:00")
    event = create_event(
        channels,
        rrule="FREQ=DAILY;COUNT=4",
        start="2026-10-31T09:00",
        end="2026-10-31T10:00",
        timezone="America/New_York",
        reminders=[0],
    )
    assert next_fire(app) == ["2026-10-31T13:00:00+00:00"]
    travel("2026-11-01T12:00:00")
    channels.patch(f"/api/v1/events/{event['id']}", json={"reminders": [0]})
    # Clocks went back on 1 November: 09:00 is now 14:00 UTC.
    assert next_fire(app) == ["2026-11-01T14:00:00+00:00"]


def test_late_reminders_are_skipped_not_sent(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    create_event(
        channels, rrule="FREQ=DAILY;COUNT=3", start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5]
    )
    # The server was down from before the first reminder until 08:20 UTC, well past the start.
    travel("2026-11-23T08:20:00")
    run()
    assert outbox.sent == []
    assert next_fire(app) == ["2026-11-24T07:55:00+00:00"]


def test_a_reminder_up_to_15_minutes_into_the_event_is_still_sent(
    channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    create_event(channels, start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5])
    travel("2026-11-23T08:10:00")
    run()
    assert len(outbox.sent) == 2


def test_failed_channels_are_retried_three_times(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    create_event(channels, start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5])
    outbox.failing = {"email"}
    travel("2026-11-23T07:55:00")
    run()
    assert [c for c, _, _ in outbox.sent] == ["push"]
    assert next_fire(app) == ["2026-11-23T07:55:00+00:00"]  # waits for the retry
    run()
    outbox.failing = set()
    run()
    assert sorted(c for c, _, _ in outbox.sent) == ["email", "push"]
    db: Database = app.state.db
    with db.reader() as session:
        log = {e.channel: (e.status, e.attempts) for e in session.scalars(select(NotificationLog))}
    assert log == {"push": ("sent", 1), "email": ("sent", 3)}
    assert next_fire(app) == [None]


def test_a_channel_that_keeps_failing_gives_up(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    create_event(channels, start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5])
    outbox.failing = {"push", "email"}
    travel("2026-11-23T07:55:00")
    for _ in range(5):
        run()
    db: Database = app.state.db
    with db.reader() as session:
        log = {e.channel: (e.status, e.attempts) for e in session.scalars(select(NotificationLog))}
    assert log == {"push": ("failed", 3), "email": ("failed", 3)}
    assert next_fire(app) == [None]


def test_delivery_is_idempotent_after_a_crash(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    event = create_event(channels, start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5])
    travel("2026-11-23T07:55:00")
    run()
    # As if the process died after sending but before moving the reminder on.
    db: Database = app.state.db
    with db.writer() as session:
        reminder = session.scalars(select(Reminder)).one()
        reminder.next_fire_at_utc = datetime(2026, 11, 23, 7, 55, tzinfo=UTC)
        reminder.next_occurrence_start = datetime(2026, 11, 23, 9, 0)
        session.commit()
    channels.patch(f"/api/v1/events/{event['id']}", json={"title": "Edited"})
    run()
    assert len(outbox.sent) == 2


def test_edits_move_the_reminder(app: FastAPI, channels: TestClient, travel: Callable[[str], None]) -> None:
    event = create_event(channels, start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[15, 60])
    assert next_fire(app) == ["2026-11-23T07:00:00+00:00", "2026-11-23T07:45:00+00:00"]
    channels.patch(
        f"/api/v1/events/{event['id']}", json={"start": "2026-11-24T12:00", "end": "2026-11-24T13:00"}
    )
    assert sorted(f for f in next_fire(app) if f) == [
        "2026-11-24T10:00:00+00:00",
        "2026-11-24T10:45:00+00:00",
    ]
    changed = channels.patch(f"/api/v1/events/{event['id']}", json={"reminders": []}).json()
    assert changed["reminders"] == []
    assert next_fire(app) == []


def test_reminders_follow_a_moved_occurrence(
    app: FastAPI, channels: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    event = create_event(
        channels, rrule="FREQ=DAILY;COUNT=2", start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5]
    )
    channels.patch(
        f"/api/v1/events/{event['id']}",
        params={"scope": "this", "occurrence": "20261123T090000"},
        json={"title": "Moved", "start": "2026-11-23T14:00", "end": "2026-11-23T15:00"},
    )
    assert next_fire(app) == ["2026-11-23T12:55:00+00:00"]
    travel("2026-11-23T12:55:00")
    run()
    assert {(o, t) for _, o, t in outbox.sent} == {(f"{event['id']}_20261123T090000", "Moved")}


def test_all_day_reminders_count_from_midnight_in_the_users_zone(
    app: FastAPI, channels: TestClient, travel: Callable[[str], None]
) -> None:
    # "The day before at 18:00" (360) and "on the day at 09:00" (-540), for 3 December in Prague.
    create_event(channels, all_day=True, start="2026-12-03", end="2026-12-04", reminders=[360, -540])
    assert next_fire(app) == ["2026-12-02T17:00:00+00:00", "2026-12-03T08:00:00+00:00"]
    channels.patch("/api/v1/me", json={"timezone": "America/New_York"})
    assert next_fire(app) == ["2026-12-02T23:00:00+00:00", "2026-12-03T14:00:00+00:00"]


def test_the_calendars_default_reminder_is_used_for_new_events(app: FastAPI, admin: TestClient) -> None:
    admin.patch(f"/api/v1/calendars/{personal(admin)}", json={"default_reminder_minutes": 30})
    assert create_event(admin)["reminders"] == [30]
    assert create_event(admin, reminders=[])["reminders"] == []
    assert create_event(admin, reminders=[5, 5, 60])["reminders"] == [60, 5]


def test_reminder_values_are_validated(admin: TestClient) -> None:
    cal = personal(admin)
    for value in (-2000, 50_000):
        response = admin.post(
            "/api/v1/events",
            json={
                "calendar_id": cal,
                "start": "2026-11-23T09:00",
                "end": "2026-11-23T10:00",
                "reminders": [value],
            },
        )
        assert response.json()["code"] == "invalid_reminder"


def test_no_channels_means_nothing_is_sent_but_it_moves_on(
    app: FastAPI, admin: TestClient, outbox: Outbox, run: Callable[[], None], travel: Callable[[str], None]
) -> None:
    create_event(
        admin, rrule="FREQ=DAILY;COUNT=2", start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5]
    )
    travel("2026-11-23T07:55:00")
    run()
    assert outbox.sent == []
    assert next_fire(app) == ["2026-11-24T07:55:00+00:00"]


def test_subscriptions_and_imports_of_alarms(admin: TestClient) -> None:
    ics = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:a1\r\nDTSTART:20261201T090000Z\r\n"
        b"DTEND:20261201T100000Z\r\nSUMMARY:With alarms\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\n"
        b"DESCRIPTION:x\r\nTRIGGER:-PT30M\r\nEND:VALARM\r\nBEGIN:VALARM\r\nACTION:AUDIO\r\n"
        b"TRIGGER:-PT5M\r\nEND:VALARM\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:x\r\n"
        b"TRIGGER;VALUE=DATE-TIME:20261201T080000Z\r\nEND:VALARM\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    cal = personal(admin)
    admin.post(f"/api/v1/calendars/{cal}/import", files={"file": ("a.ics", ics, "text/calendar")})
    items = admin.get("/api/v1/occurrences", params={"start": "2026-12-01", "end": "2026-12-02"}).json()[
        "items"
    ]
    assert admin.get(f"/api/v1/events/{items[0]['event_id']}").json()["reminders"] == [30]
    exported = admin.get(f"/api/v1/calendars/{cal}/export").content
    assert b"BEGIN:VALARM" in exported
    assert b"TRIGGER:-PT30M" in exported


# Push subscriptions


def test_push_subscriptions_per_user(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    body = {"endpoint": "https://push.example.com/device-1", "keys": {"p256dh": "p", "auth": "a"}}
    assert admin.post("/api/v1/me/push-subscriptions", json=body).status_code == 204
    endpoint = {"endpoint": body["endpoint"]}
    assert admin.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is True
    other = make_user()
    assert other.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is False
    # Removing someone else's subscription does nothing.
    other.post("/api/v1/me/push-subscriptions/remove", json=endpoint)
    assert admin.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is True
    # The same browser signed in as someone else now belongs to them.
    other.post("/api/v1/me/push-subscriptions", json=body)
    assert admin.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is False
    other.post("/api/v1/me/push-subscriptions/remove", json=endpoint)
    assert other.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is False


def test_dead_push_subscriptions_are_removed(
    app: FastAPI, admin: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.notify import push

    admin.post(
        "/api/v1/me/push-subscriptions",
        json={"endpoint": "https://push.example.com/gone", "keys": {"p256dh": "p", "auth": "a"}},
    )

    class Gone:
        status_code = 410

    def webpush(**_kwargs: Any) -> None:
        raise push.WebPushException("gone", response=Gone())

    monkeypatch.setattr(push, "webpush", webpush)
    db: Database = app.state.db
    user_id = admin.get("/api/v1/me").json()["id"]
    with db.writer() as session:
        assert push.send_payload(session, settings, user_id, {"title": "x"}) == 0
        session.commit()
    endpoint = {"endpoint": "https://push.example.com/gone"}
    assert admin.post("/api/v1/me/push-subscriptions/check", json=endpoint).json() is False


def test_push_payload(
    app: FastAPI,
    channels: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    travel: Callable[[str], None],
) -> None:
    from app.services.notify import push

    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(push, "webpush", lambda **kwargs: sent.append(kwargs))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    event = create_event(
        channels,
        title="Dentist",
        location="Klinika",
        start="2026-11-23T09:00",
        end="2026-11-23T10:00",
        reminders=[5],
    )
    travel("2026-11-23T07:55:00")
    channels.patch("/api/v1/me", json={"email_reminders_enabled": False})
    db: Database = app.state.db
    scheduler.send_reminders(db, settings)
    import json

    payload = json.loads(sent[0]["data"])
    assert payload == {
        "title": "Dentist",
        "body": "Mon 23 Nov, 09:00 · Klinika",
        "occurrence_id": str(event["id"]),
        "url": f"/event/{event['id']}",
        "tag": f"reminder-{event['id']}",
    }
    assert sent[0]["vapid_claims"] == {"sub": "mailto:calendar@example.com"}


# E-mail


class FakeSmtp:
    messages: ClassVar[list[Any]] = []
    connections: ClassVar[list[tuple[str, int, str | None]]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        FakeSmtp.connections.append((host, port, None))

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def starttls(self, context: object) -> None:
        pass

    def login(self, user: str, password: str) -> None:
        FakeSmtp.connections[-1] = (self.host, self.port, f"{user}:{password}")

    def send_message(self, message: Any) -> None:
        FakeSmtp.messages.append(message)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch, mail_server: None) -> type[FakeSmtp]:
    from app.services.notify import email

    FakeSmtp.messages = []
    FakeSmtp.connections = []
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSmtp)
    return FakeSmtp


def test_reminder_email(
    app: FastAPI, admin: TestClient, settings: Settings, smtp: type[FakeSmtp], travel: Callable[[str], None]
) -> None:
    admin.patch("/api/v1/me", json={"email_reminders_enabled": True})
    create_event(admin, title="Dentist <3", start="2026-11-23T09:00", end="2026-11-23T10:00", reminders=[5])
    travel("2026-11-23T07:55:00")
    db: Database = app.state.db
    scheduler.send_reminders(db, settings)
    message = smtp.messages[0]
    assert message["To"] == "admin@example.com"
    assert message["Subject"] == "Reminder: Dentist <3"
    text = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Mon 23 Nov, 09:00" in text
    assert "Dentist &lt;3" in html and "<3" not in html.replace("&lt;3", "")
    assert "Open in" in text and "/event/" in text
    # The logo travels inside the message; nothing is fetched from the network when it is read.
    logo = next(part for part in message.walk() if part.get_content_type() == "image/png")
    assert f'src="cid:{logo["Content-ID"][1:-1]}"' in html
    assert 'src="http' not in html


def test_invite_and_reset_emails(
    admin: TestClient, new_client: Callable[[], TestClient], smtp: type[FakeSmtp]
) -> None:
    link = admin.post("/api/v1/admin/invites", json={"email": "friend@example.com"}).json()
    assert link["emailed"] is True
    assert smtp.messages[-1]["To"] == "friend@example.com"
    assert link["url"] in smtp.messages[-1].get_body(preferencelist=("plain",)).get_content()
    visitor = new_client()
    assert (
        visitor.post("/api/v1/auth/password-reset/request", json={"email": "admin@example.com"}).status_code
        == 204
    )
    reset = smtp.messages[-1]
    assert reset["To"] == "admin@example.com"
    assert "/reset/" in reset.get_body(preferencelist=("plain",)).get_content()
    count = len(smtp.messages)
    unknown = visitor.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert unknown.status_code == 204
    assert len(smtp.messages) == count
    assert admin.post("/api/v1/admin/test-email").status_code == 204
    assert smtp.messages[-1]["Subject"] == f"{get_branding().name}: test e-mail"
    assert smtp.messages[-1]["From"] == "calendar@example.com"
    # The saved password reaches the mail server, though the administration never shows it.
    assert smtp.connections[-1] == ("mail.example.com", 587, "calendar:mail-password")


def test_reset_request_without_smtp(admin: TestClient) -> None:
    response = admin.post("/api/v1/auth/password-reset/request", json={"email": "admin@example.com"})
    assert response.json()["code"] == "email_disabled"
    assert admin.post("/api/v1/admin/test-email").json()["code"] == "email_disabled"


def test_failed_smtp_is_reported_to_the_admin(
    admin: TestClient, monkeypatch: pytest.MonkeyPatch, mail_server: None
) -> None:
    from app.services.notify import email

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(email.smtplib, "SMTP", refuse)
    response = admin.post("/api/v1/admin/test-email")
    assert response.status_code == 502
    assert "could not be sent" in response.json()["message"]
