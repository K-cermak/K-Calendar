from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentAuth
from app.db import DbSession
from app.schemas.calendar import EventCreate, EventOut, EventUpdate, OccurrenceList
from app.services import events, occurrences

router = APIRouter(tags=["events"])


@router.get("/occurrences")
def list_occurrences(
    auth: CurrentAuth,
    db: DbSession,
    start: Annotated[str, Query(max_length=40, description="Wall-clock in tz, or an ISO instant")],
    end: Annotated[str, Query(max_length=40, description="Exclusive; at most 400 days after start")],
    tz: Annotated[
        str | None, Query(max_length=64, description="Display zone; the profile's if left out")
    ] = None,
) -> OccurrenceList:
    """Everything a view shows: ready-made occurrences with wall-clock times in the display zone."""
    return occurrences.list_for(db, auth.user, start, end, tz)


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, auth: CurrentAuth, db: DbSession) -> EventOut:
    return events.create(db, auth.user, body)


@router.get("/events/{event_id}")
def get_event(event_id: int, auth: CurrentAuth, db: DbSession) -> EventOut:
    return events.get(db, auth.user, event_id)


@router.patch("/events/{event_id}")
def update_event(event_id: int, body: EventUpdate, auth: CurrentAuth, db: DbSession) -> EventOut:
    return events.update(db, auth.user, event_id, body)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, auth: CurrentAuth, db: DbSession) -> None:
    events.delete(db, auth.user, event_id)
