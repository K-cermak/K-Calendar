from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import scheduler
from app.config import Settings
from app.db import Database
from app.models import NotificationLog, Reminder
from tests.conftest import Clock, count_rows, invite_url
from tests.helpers import create_event


def clean(app: FastAPI) -> None:
    scheduler.clean_up(app.state.db)


def test_used_and_expired_invites_go(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient], clock: Clock
) -> None:
    make_user()
    invite_url(admin)
    clean(app)
    assert count_rows(app, "invites") == 1
    clock.advance(timedelta(days=8))
    clean(app)
    assert count_rows(app, "invites") == 0


def test_expired_sessions_go_and_live_ones_stay(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient], clock: Clock
) -> None:
    make_user()
    clean(app)
    assert count_rows(app, "sessions") == 2
    clock.advance(timedelta(days=181))
    clean(app)
    assert count_rows(app, "sessions") == 0


def test_old_reminder_log_goes_whatever_its_status(app: FastAPI, admin: TestClient, clock: Clock) -> None:
    create_event(admin, reminders=[10])
    db: Database = app.state.db
    with db.writer() as session:
        reminder_id = session.scalars(select(Reminder.id)).one()
        for start, status in [
            ("2026-09-01T09:00", "failed"),
            ("2026-09-02T09:00", "sent"),
            ("2026-11-10T09:00", "sent"),
        ]:
            session.add(
                NotificationLog(
                    reminder_id=reminder_id,
                    occurrence_start=datetime.fromisoformat(start),
                    channel="push",
                    status=status,
                    attempts=1,
                )
            )
        session.commit()
    clean(app)
    with db.reader() as session:
        left = session.scalars(select(NotificationLog.occurrence_start)).all()
    assert left == [datetime(2026, 11, 10, 9, 0)]


def test_clean_up_runs_once_a_night(
    app: FastAPI, admin: TestClient, settings: Settings, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[datetime] = []
    loop = scheduler.Loop()
    original = scheduler.clean_up

    def counting(db: Database) -> None:
        runs.append(datetime.now(UTC))
        original(db)

    monkeypatch.setattr(scheduler, "clean_up", counting)
    db: Database = app.state.db
    for _ in range(4 * 24):
        loop.tick(db, settings)
        clock.advance(timedelta(minutes=30))
    assert [r.date() for r in runs] == [date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)]
    assert all(r.hour == scheduler.CLEANUP_HOUR_UTC for r in runs[1:])


def test_clean_up_waits_for_the_night() -> None:
    assert not scheduler.cleanup_due(None, datetime(2026, 11, 20, 1, 59, tzinfo=UTC))
    assert scheduler.cleanup_due(None, datetime(2026, 11, 20, 2, 0, tzinfo=UTC))
    assert not scheduler.cleanup_due(date(2026, 11, 20), datetime(2026, 11, 20, 23, 0, tzinfo=UTC))
