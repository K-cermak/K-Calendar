from fastapi import APIRouter, status

from app.api.deps import CurrentAuth
from app.db import DbSession
from app.schemas.calendar import CalendarCreate, CalendarOrder, CalendarOut, CalendarUpdate
from app.services import calendars

router = APIRouter(prefix="/calendars", tags=["calendars"])


@router.get("")
def list_calendars(auth: CurrentAuth, db: DbSession) -> list[CalendarOut]:
    return calendars.list_for(db, auth.user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_calendar(body: CalendarCreate, auth: CurrentAuth, db: DbSession) -> CalendarOut:
    return calendars.create(db, auth.user, body)


@router.put("/order")
def reorder_calendars(body: CalendarOrder, auth: CurrentAuth, db: DbSession) -> list[CalendarOut]:
    return calendars.reorder(db, auth.user, body)


@router.patch("/{calendar_id}")
def update_calendar(calendar_id: int, body: CalendarUpdate, auth: CurrentAuth, db: DbSession) -> CalendarOut:
    return calendars.update(db, auth.user, calendar_id, body)


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(calendar_id: int, auth: CurrentAuth, db: DbSession) -> None:
    """Deletes the calendar and every event in it."""
    calendars.delete(db, auth.user, calendar_id)
