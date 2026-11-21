from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentAuth
from app.db import DbSession
from app.schemas.calendar import (
    EditScope,
    EventCreate,
    EventOut,
    EventUpdate,
    Occurrence,
    OccurrenceList,
    SearchResult,
)
from app.services import events, occurrences, search

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


@router.get("/occurrences/{occurrence_id}")
def get_occurrence(
    occurrence_id: str,
    auth: CurrentAuth,
    db: DbSession,
    tz: Annotated[
        str | None, Query(max_length=64, description="Display zone; the profile's if left out")
    ] = None,
) -> Occurrence:
    """One occurrence by its id from the occurrence list, as /event/{id} links use it."""
    return occurrences.get_one(db, auth.user, occurrence_id, tz)


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, auth: CurrentAuth, db: DbSession) -> EventOut:
    return events.create(db, auth.user, body)


OccurrenceKey = Annotated[
    str | None,
    Query(
        max_length=15,
        pattern=r"^\d{8}T\d{6}$",
        description="One occurrence of a series: its original start, as YYYYMMDDTHHMMSS",
    ),
]
Scope = Annotated[
    EditScope | None,
    Query(description="For an occurrence of a series: this one, this and following, or all"),
]


@router.get("/events/{event_id}")
def get_event(event_id: int, auth: CurrentAuth, db: DbSession, occurrence: OccurrenceKey = None) -> EventOut:
    """An event, or one occurrence of a series with its own values."""
    return events.get(db, auth.user, event_id, occurrence)


@router.patch("/events/{event_id}")
def update_event(
    event_id: int,
    body: EventUpdate,
    auth: CurrentAuth,
    db: DbSession,
    scope: Scope = None,
    occurrence: OccurrenceKey = None,
) -> EventOut:
    """Changes an event. For an occurrence of a series, scope says which occurrences change."""
    return events.update(db, auth.user, event_id, body, scope=scope, occurrence=occurrence)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int, auth: CurrentAuth, db: DbSession, scope: Scope = None, occurrence: OccurrenceKey = None
) -> None:
    events.delete(db, auth.user, event_id, scope=scope, occurrence=occurrence)


@router.get("/search")
def search_events(
    auth: CurrentAuth,
    db: DbSession,
    q: Annotated[str, Query(max_length=200, description="Words to find; each may be the start of a word")],
    tz: Annotated[
        str | None, Query(max_length=64, description="Display zone; the profile's if left out")
    ] = None,
) -> list[SearchResult]:
    """Events whose title, description, location or tags match, in all calendars, hidden ones too.
    Upcoming ones come first, nearest first, then past ones, most recent first."""
    return search.search(db, auth.user, q, tz)
