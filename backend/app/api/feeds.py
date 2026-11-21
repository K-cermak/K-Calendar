from fastapi import APIRouter, Response

from app.db import DbSession
from app.errors import NotFoundError
from app.services import calendars, ics

router = APIRouter(tags=["feeds"])


@router.get("/feeds/{token}.ics", response_class=Response, include_in_schema=False)
def feed(token: str, db: DbSession) -> Response:
    """A calendar's secret read-only address for other calendar apps; no login (SPEC 10)."""
    calendar = calendars.by_feed_token(db, token)
    if calendar is None:
        raise NotFoundError()
    return Response(
        ics.serialize(db, calendar),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )
