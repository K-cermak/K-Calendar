from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.palette import PaletteColor

CalendarKind = Literal["local", "subscription"]
EditScope = Literal["this", "following", "all"]
Rule = Annotated[
    str,
    Field(
        max_length=1000, description="An RFC 5545 RRULE without DTSTART", examples=["FREQ=WEEKLY;BYDAY=MO"]
    ),
]
# Wall-clock: "2026-11-23T09:00:00" for timed events, "2026-11-23" for all-day ones; never an offset.
LocalDateTime = Annotated[str, Field(max_length=32, examples=["2026-11-23T09:00:00", "2026-11-23"])]
ZoneName = Annotated[str, Field(max_length=64, examples=["Europe/Prague"])]
ReminderMinutes = Annotated[int, Field(ge=0, le=60 * 24 * 28)]


class CalendarOut(BaseModel):
    id: int
    name: str
    color: PaletteColor
    kind: CalendarKind
    is_visible: bool
    sort_order: int
    default_reminder_minutes: int | None
    read_only: bool


class CalendarCreate(BaseModel):
    name: str = Field(max_length=100)
    color: PaletteColor
    default_reminder_minutes: ReminderMinutes | None = None


class CalendarUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    color: PaletteColor | None = None
    is_visible: bool | None = None
    # Sent as null it removes the default; left out it stays as it is.
    default_reminder_minutes: ReminderMinutes | None = None


class CalendarOrder(BaseModel):
    ids: list[int] = Field(max_length=1000, description="Every calendar of the user, in the new order")


class TagOut(BaseModel):
    id: int
    name: str
    color: PaletteColor


class TagCreate(BaseModel):
    name: str = Field(max_length=100)
    color: PaletteColor | None = Field(default=None, description="Left out: the least used colour")


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    color: PaletteColor | None = None


class EventCreate(BaseModel):
    calendar_id: int
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=20_000)
    location: str = Field(default="", max_length=500)
    color: PaletteColor | None = None
    all_day: bool = False
    start: LocalDateTime
    end: LocalDateTime = Field(description="Exclusive: an all-day event on 3 May ends on 4 May")
    timezone: ZoneName | None = Field(
        default=None, description="The event's zone for timed events; the profile's zone if left out"
    )
    input_timezone: ZoneName | None = Field(
        default=None,
        description="The zone start and end are written in, if not the event's own (after a drag)",
    )
    tags: list[Annotated[str, Field(max_length=100)]] = Field(default=[], max_length=50)
    rrule: Rule | None = None


class EventUpdate(BaseModel):
    calendar_id: int | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    location: str | None = Field(default=None, max_length=500)
    color: PaletteColor | None = None
    all_day: bool | None = None
    start: LocalDateTime | None = None
    end: LocalDateTime | None = None
    timezone: ZoneName | None = None
    input_timezone: ZoneName | None = None
    tags: list[Annotated[str, Field(max_length=100)]] | None = Field(default=None, max_length=50)
    rrule: Rule | None = Field(default=None, description="Sent as null it ends the repetition")


class EventOut(BaseModel):
    id: int
    calendar_id: int
    uid: str
    title: str
    description: str
    location: str
    color: PaletteColor | None
    all_day: bool
    start: str = Field(description="Wall-clock in the event's zone, or a date for all-day events")
    end: str
    timezone: str | None
    rrule: str | None = Field(description="The series' rule, also for one of its occurrences")
    recurring: bool
    occurrence: str | None = Field(description="Which occurrence of the series this describes")
    tags: list[TagOut]
    read_only: bool
    created_at_utc: datetime
    updated_at_utc: datetime


class Occurrence(BaseModel):
    id: str = Field(description="The event id, or {master id}_{original start} for one of a series")
    event_id: int = Field(description="The event, or the master of the series this occurrence is in")
    occurrence: str | None = Field(
        description="For a series, the original start (YYYYMMDDTHHMMSS) to send as ?occurrence="
    )
    calendar_id: int
    title: str
    location: str
    color: PaletteColor = Field(description="The event's own colour, otherwise its calendar's")
    all_day: bool
    start: str = Field(description="Wall-clock in the display zone; a date for all-day events")
    end: str = Field(description="Exclusive, like start")
    start_utc: datetime
    end_utc: datetime
    tags: list[TagOut]
    recurring: bool
    read_only: bool


class OccurrenceList(BaseModel):
    timezone: str
    now: str = Field(description="The current wall-clock time in the display zone")
    items: list[Occurrence]
