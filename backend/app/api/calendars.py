import re
from urllib.parse import quote

from fastapi import APIRouter, Response, UploadFile, status

from app.api.deps import AppSettings, CurrentAuth
from app.db import DbSession
from app.errors import AppError
from app.schemas.calendar import (
    CalendarCreate,
    CalendarOrder,
    CalendarOut,
    CalendarUpdate,
    ImportResult,
    ImportSkip,
    SubscriptionCreate,
)
from app.services import calendars, ics, importer, subscriptions

router = APIRouter(prefix="/calendars", tags=["calendars"])


@router.get("")
def list_calendars(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> list[CalendarOut]:
    return calendars.list_for(db, auth.user, settings.base_url)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_calendar(
    body: CalendarCreate, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> CalendarOut:
    return calendars.create(db, auth.user, body, settings.base_url)


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def subscribe(
    body: SubscriptionCreate, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> CalendarOut:
    """Adds a read-only calendar that follows an external ICS address, and fetches it at once."""
    calendar = subscriptions.create(
        db,
        auth.user,
        url=body.url,
        name=body.name,
        color=body.color,
        interval=body.refresh_interval_minutes,
    )
    subscriptions.refresh(db, settings, calendar.id)
    return calendars.out(db, calendars.get_owned(db, auth.user, calendar.id), settings.base_url)


@router.put("/order")
def reorder_calendars(
    body: CalendarOrder, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> list[CalendarOut]:
    return calendars.reorder(db, auth.user, body, settings.base_url)


@router.patch("/{calendar_id}")
def update_calendar(
    calendar_id: int, body: CalendarUpdate, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> CalendarOut:
    return calendars.update(db, auth.user, calendar_id, body, settings.base_url)


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(calendar_id: int, auth: CurrentAuth, db: DbSession) -> None:
    """Deletes the calendar and every event in it."""
    calendars.delete(db, auth.user, calendar_id)


@router.post("/{calendar_id}/refresh")
def refresh_subscription(
    calendar_id: int, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> CalendarOut:
    """Fetches a subscribed calendar now, outside its schedule."""
    calendar = calendars.get_owned(db, auth.user, calendar_id)
    subscriptions.get(db, calendar)
    subscriptions.refresh(db, settings, calendar.id)
    return calendars.out(db, calendars.get_owned(db, auth.user, calendar_id), settings.base_url)


@router.put("/{calendar_id}/feed")
def create_feed(calendar_id: int, auth: CurrentAuth, db: DbSession, settings: AppSettings) -> CalendarOut:
    """Switches on the secret feed address, or replaces it so the old one stops working."""
    return calendars.set_feed(db, auth.user, calendar_id, settings.base_url)


@router.delete("/{calendar_id}/feed", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(calendar_id: int, auth: CurrentAuth, db: DbSession) -> None:
    calendars.remove_feed(db, auth.user, calendar_id)


@router.get(
    "/{calendar_id}/export",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}, "description": "The calendar as an .ics file"}},
)
def export_calendar(calendar_id: int, auth: CurrentAuth, db: DbSession) -> Response:
    calendar = calendars.get_owned(db, auth.user, calendar_id)
    return Response(
        ics.serialize(db, calendar),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": _attachment(calendar.name)},
    )


def _attachment(name: str) -> str:
    """The calendar's name as the file name: plain ASCII for old clients, UTF-8 for the rest."""
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "calendar"
    return f"attachment; filename=\"{ascii_name}.ics\"; filename*=UTF-8''{quote(name)}.ics"


@router.post("/{calendar_id}/import")
def import_calendar(calendar_id: int, file: UploadFile, auth: CurrentAuth, db: DbSession) -> ImportResult:
    """Imports an .ics file of at most 10 MB. Events are matched by UID, so importing the same file
    twice changes nothing."""
    calendar = calendars.get_writable(db, auth.user, calendar_id)
    data = file.file.read(ics.MAX_BYTES + 1)
    if len(data) > ics.MAX_BYTES:
        raise AppError(413, "file_too_large", "The file is larger than 10 MB")
    parsed, skipped = ics.parse(data, auth.user.timezone)
    report = importer.apply(db, auth.user, calendar, parsed, skipped)
    db.commit()
    return ImportResult(
        created=report.created,
        updated=report.updated,
        skipped=[ImportSkip(uid=s.uid, title=s.title, reason=s.reason) for s in report.skipped],
    )
