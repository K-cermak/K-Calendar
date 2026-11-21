"""The background loop, an asyncio task in the app's lifespan (SPEC 2).

The app runs as exactly one process, so each job runs once. Jobs are sync and run in a thread, as
every other database access does.
"""

import asyncio
import logging

from fastapi import FastAPI

from app.config import Settings
from app.db import Database
from app.services import subscriptions

logger = logging.getLogger(__name__)

TICK_S = 30


def refresh_subscriptions(db: Database, settings: Settings) -> None:
    with db.reader() as session:
        due = subscriptions.due(session)
    for calendar_id in due:
        # Each in its own session: one slow or broken feed must not hold up the others.
        with db.writer() as session:
            try:
                subscriptions.refresh(session, settings, calendar_id)
            except Exception:
                logger.exception("Refreshing subscription %s failed", calendar_id)


def tick(db: Database, settings: Settings) -> None:
    refresh_subscriptions(db, settings)


async def run(app: FastAPI) -> None:
    db: Database = app.state.db
    settings: Settings = app.state.settings
    while True:
        await asyncio.sleep(TICK_S)
        try:
            await asyncio.to_thread(tick, db, settings)
        except Exception:
            logger.exception("Background tick failed")
