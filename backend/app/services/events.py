"""Events and series: creating, reading, and changing them with an edit scope (SPEC 5, 7)."""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import InvalidInputError, NotFoundError
from app.models import Calendar, Event, EventTag, Tag, User
from app.schemas.calendar import EditScope, EventCreate, EventOut, EventUpdate
from app.services import calendars, clock, recurrence, tags, zones


def get_owned(db: Session, user: User, event_id: int) -> tuple[Event, Calendar]:
    """An event in one of this user's calendars. Someone else's is reported as missing."""
    row = db.execute(
        select(Event, Calendar)
        .join(Calendar, Calendar.id == Event.calendar_id)
        .where(Event.id == event_id, Calendar.user_id == user.id)
    ).first()
    if row is None:
        raise NotFoundError()
    return row[0], row[1]


def tags_of(db: Session, event_ids: list[int]) -> dict[int, list[Tag]]:
    result: dict[int, list[Tag]] = {event_id: [] for event_id in event_ids}
    if not event_ids:
        return result
    rows = db.execute(
        select(EventTag.event_id, Tag)
        .join(Tag, Tag.id == EventTag.tag_id)
        .where(EventTag.event_id.in_(event_ids))
        .order_by(Tag.name_key)
    )
    for event_id, tag in rows:
        result[event_id].append(tag)
    return result


def local_text(all_day: bool, value: datetime) -> str:
    return value.date().isoformat() if all_day else zones.format_local(value)


@dataclass(frozen=True)
class Times:
    """When an event or one occurrence happens, in the event's own terms."""

    all_day: bool
    start: datetime
    end: datetime
    timezone: str | None

    @staticmethod
    def of(event: Event) -> Times:
        return Times(event.all_day, event.start_local, event.end_local, event.timezone)

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def apply_to(self, event: Event) -> None:
        event.all_day, event.start_local, event.end_local = self.all_day, self.start, self.end
        event.timezone = self.timezone


def to_out(
    db: Session,
    event: Event,
    calendar: Calendar,
    *,
    master: Event | None = None,
    original_start: datetime | None = None,
    times: Times | None = None,
) -> EventOut:
    """An event, or with master and original_start one occurrence of a series."""
    shown = times or Times.of(event)
    series = master or (event if event.rrule else None)
    return EventOut.model_validate(
        {
            "id": series.id if series else event.id,
            "calendar_id": event.calendar_id,
            "uid": event.uid,
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "color": event.color,
            "all_day": shown.all_day,
            "start": local_text(shown.all_day, shown.start),
            "end": local_text(shown.all_day, shown.end),
            "timezone": shown.timezone,
            "rrule": series.rrule if series else None,
            "recurring": series is not None,
            "occurrence": recurrence.occurrence_key(original_start) if original_start else None,
            "tags": [tags.to_out(t) for t in tags_of(db, [event.id])[event.id]],
            "read_only": calendar.kind == "subscription",
            "created_at_utc": event.created_at_utc,
            "updated_at_utc": event.updated_at_utc,
        }
    )


def derive(event: Event) -> None:
    """Recomputes the UTC columns from what the user entered."""
    if event.all_day:
        event.start_utc, event.end_utc = zones.floating_bounds(event.start_local, event.end_local)
    else:
        assert event.timezone is not None
        event.start_utc = zones.to_utc(event.start_local, event.timezone)
        event.end_utc = zones.to_utc(event.end_local, event.timezone)
    is_master = event.rrule is not None and event.recurring_event_id is None
    event.series_end_utc = recurrence.series_end_utc(event) if is_master else event.end_utc


# Times from input


def _all_day_span(start: str, end: str) -> tuple[datetime, datetime]:
    start_day = zones.parse_local(start).date()
    end_day = zones.parse_local(end).date()
    if end_day <= start_day:
        raise InvalidInputError("invalid_span", "An all-day event ends at least one day after it starts")
    return zones.midnight(start_day), zones.midnight(end_day)


def _timed_span(start: str, end: str, zone: str, input_zone: str | None) -> tuple[datetime, datetime]:
    start_local, end_local = zones.parse_local(start), zones.parse_local(end)
    if input_zone and input_zone != zone:
        # Values from a grid shown in another zone: the same instants, written in the event's zone.
        start_local = zones.to_local(zones.to_utc(start_local, input_zone), zone)
        end_local = zones.to_local(zones.to_utc(end_local, input_zone), zone)
    if end_local < start_local:
        raise InvalidInputError("invalid_span", "The end must not be before the start")
    return start_local, end_local


def resolve_times(current: Times, user: User, body: EventUpdate) -> Times:
    """The times after applying a change to the current ones."""
    all_day = current.all_day if body.all_day is None else body.all_day
    if all_day != current.all_day and (body.start is None or body.end is None):
        raise InvalidInputError("times_required", "Send start and end when switching all-day on or off")
    if body.input_timezone:
        zones.check_zone(body.input_timezone)
    if all_day:
        start, end = current.start, current.end
        if body.start is not None or body.end is not None:
            start, end = _all_day_span(
                body.start or current.start.date().isoformat(),
                body.end or current.end.date().isoformat(),
            )
        return Times(True, start, end, None)
    zone = zones.check_zone(body.timezone or current.timezone or user.timezone)
    start, end = current.start, current.end
    if body.start is not None or body.end is not None:
        input_zone = body.input_timezone or (zone if current.all_day else current.timezone)
        start, end = _timed_span(
            body.start or zones.format_local(current.start),
            body.end or zones.format_local(current.end),
            zone,
            input_zone,
        )
    # A new zone without new times keeps the wall-clock times: "9:00" stays 9:00, in the new zone.
    return Times(False, start, end, zone)


def _rule(text: str | None, times: Times) -> str | None:
    if text is None:
        return None
    return recurrence.normalize_rule(text, all_day=times.all_day, zone=times.timezone)


def _set_tags(db: Session, user: User, event: Event, names: list[str]) -> None:
    db.execute(sql_delete(EventTag).where(EventTag.event_id == event.id))
    for tag in tags.resolve(db, user, names):
        db.add(EventTag(event_id=event.id, tag_id=tag.id))


def _copy_tags(db: Session, source: Event, target: Event) -> None:
    for tag in tags_of(db, [source.id])[source.id]:
        db.add(EventTag(event_id=target.id, tag_id=tag.id))


def _apply_fields(event: Event, body: EventUpdate) -> None:
    if body.title is not None:
        event.title = body.title.strip()
    if body.description is not None:
        event.description = body.description
    if body.location is not None:
        event.location = body.location.strip()
    if "color" in body.model_fields_set:
        event.color = body.color


def _touched(event: Event) -> None:
    event.sequence += 1
    event.updated_at_utc = clock.now()


# Create and read


def create(db: Session, user: User, body: EventCreate) -> EventOut:
    calendar = calendars.get_writable(db, user, body.calendar_id)
    seed = Times(False, datetime(2000, 1, 1), datetime(2000, 1, 1), body.timezone or user.timezone)
    times = resolve_times(
        seed,
        user,
        EventUpdate(
            all_day=body.all_day,
            start=body.start,
            end=body.end,
            timezone=body.timezone,
            input_timezone=body.input_timezone,
        ),
    )
    now = clock.now()
    event = Event(
        calendar_id=calendar.id,
        uid=str(uuid.uuid4()),
        title=body.title.strip(),
        description=body.description,
        location=body.location.strip(),
        color=body.color,
        rrule=_rule(body.rrule, times),
        exdates=[],
        sequence=0,
        created_at_utc=now,
        updated_at_utc=now,
    )
    times.apply_to(event)
    derive(event)
    db.add(event)
    db.flush()
    _set_tags(db, user, event, body.tags)
    db.commit()
    return to_out(db, event, calendar)


def _override(db: Session, master: Event, original_start: datetime) -> Event | None:
    return db.scalar(
        select(Event).where(Event.recurring_event_id == master.id, Event.original_start == original_start)
    )


@dataclass
class Target:
    """What a request addresses: a plain event, a whole series, or one occurrence of a series."""

    event: Event
    calendar: Calendar
    original_start: datetime | None = None
    override: Event | None = None

    @property
    def is_series(self) -> bool:
        return self.event.rrule is not None

    def occurrence_times(self) -> Times:
        """The occurrence as the rule makes it, before any override moved it."""
        assert self.original_start is not None
        master = Times.of(self.event)
        return replace(master, start=self.original_start, end=self.original_start + master.duration)


def resolve_target(db: Session, user: User, event_id: int, occurrence: str | None) -> Target:
    event, calendar = get_owned(db, user, event_id)
    if event.recurring_event_id is not None:
        # An override addressed by its own id stands for that occurrence of its series.
        master = db.get(Event, event.recurring_event_id)
        assert master is not None and event.original_start is not None
        return Target(master, calendar, event.original_start, event)
    if occurrence is None or event.rrule is None:
        return Target(event, calendar)
    original_start = recurrence.parse_occurrence_key(occurrence)
    override = _override(db, event, original_start)
    if override is None and not recurrence.is_occurrence(event, original_start):
        raise NotFoundError("This occurrence does not exist")
    return Target(event, calendar, original_start, override)


def get(db: Session, user: User, event_id: int, occurrence: str | None = None) -> EventOut:
    target = resolve_target(db, user, event_id, occurrence)
    if target.original_start is None:
        return to_out(db, target.event, target.calendar)
    if target.override is not None:
        return to_out(
            db,
            target.override,
            target.calendar,
            master=target.event,
            original_start=target.original_start,
        )
    return to_out(
        db,
        target.event,
        target.calendar,
        master=target.event,
        original_start=target.original_start,
        times=target.occurrence_times(),
    )


# Update


def _timing_changed(before: Times, after: Times, rule_before: str | None, rule_after: str | None) -> bool:
    return (
        before.all_day != after.all_day
        or before.timezone != after.timezone
        or before.duration != after.duration
        or before.start.time() != after.start.time()
        or before.start != after.start
        or rule_before != rule_after
    )


def _drop_exceptions(db: Session, master: Event, *, from_start: datetime | None = None) -> None:
    """Overrides and exdates no longer match the occurrences after a change to the series' timing."""
    condition = Event.recurring_event_id == master.id
    if from_start is not None:
        condition = condition & (Event.original_start >= from_start)
    db.execute(sql_delete(Event).where(condition))
    master.exdates = (
        [] if from_start is None else [v for v in master.exdates if datetime.fromisoformat(v) < from_start]
    )


def _update_plain(db: Session, user: User, target: Target, body: EventUpdate) -> Event:
    """A single event, or a whole series addressed without an occurrence."""
    event = target.event
    before = Times.of(event)
    after = resolve_times(before, user, body)
    rule_before = event.rrule
    if "rrule" in body.model_fields_set:
        event.rrule = _rule(body.rrule, after)
    elif event.rrule is not None and (after.all_day != before.all_day or after.timezone != before.timezone):
        event.rrule = _rule(event.rrule, after)
    if rule_before is not None and _timing_changed(before, after, rule_before, event.rrule):
        _drop_exceptions(db, event)
    _apply_fields(event, body)
    after.apply_to(event)
    derive(event)
    if body.tags is not None:
        _set_tags(db, user, event, body.tags)
    _touched(event)
    return event


def _update_this(db: Session, user: User, target: Target, body: EventUpdate) -> Event:
    """One occurrence: changes go to an override row, created on the first change."""
    if "rrule" in body.model_fields_set:
        raise InvalidInputError("rule_for_series", "Change the repetition for the whole series")
    if body.calendar_id is not None and body.calendar_id != target.calendar.id:
        raise InvalidInputError("calendar_for_series", "Move the whole series to another calendar")
    master = target.event
    assert target.original_start is not None
    override = target.override
    if override is None:
        times = target.occurrence_times()
        now = clock.now()
        override = Event(
            calendar_id=master.calendar_id,
            uid=master.uid,
            title=master.title,
            description=master.description,
            location=master.location,
            color=master.color,
            exdates=[],
            recurring_event_id=master.id,
            original_start=target.original_start,
            sequence=0,
            created_at_utc=now,
            updated_at_utc=now,
        )
        times.apply_to(override)
        derive(override)
        db.add(override)
        db.flush()
        _copy_tags(db, master, override)
    resolve_times(Times.of(override), user, body).apply_to(override)
    _apply_fields(override, body)
    derive(override)
    if body.tags is not None:
        _set_tags(db, user, override, body.tags)
    _touched(override)
    return override


def _shifted(master: Event, base: Times, after: Times) -> Times:
    """The master's times after one occurrence changed from base to after: every occurrence moves
    by the same amount. It also holds when all-day is switched, as midnight is then the start."""
    start = master.start_local + (after.start - base.start)
    return Times(after.all_day, start, start + after.duration, after.timezone)


def _update_all(db: Session, user: User, target: Target, body: EventUpdate) -> Event:
    """The whole series, from an occurrence: its time change shifts every occurrence alike."""
    master = target.event
    base = target.occurrence_times()
    after = resolve_times(base, user, body)
    new_times = _shifted(master, base, after)
    rule_before = master.rrule
    new_rule = _rule(body.rrule, new_times) if "rrule" in body.model_fields_set else master.rrule
    if new_rule is not None and (new_times.all_day != base.all_day or new_times.timezone != base.timezone):
        new_rule = _rule(new_rule, new_times)
    if _timing_changed(Times.of(master), new_times, rule_before, new_rule):
        _drop_exceptions(db, master)
    if body.calendar_id is not None and body.calendar_id != master.calendar_id:
        master.calendar_id = calendars.get_writable(db, user, body.calendar_id).id
        for override in db.scalars(select(Event).where(Event.recurring_event_id == master.id)):
            override.calendar_id = master.calendar_id
    master.rrule = new_rule
    new_times.apply_to(master)
    _apply_fields(master, body)
    derive(master)
    if body.tags is not None:
        _set_tags(db, user, master, body.tags)
    _touched(master)
    return master


def _truncate(master: Event, original_start: datetime) -> int | None:
    """Ends the series just before original_start. Returns the occurrences a COUNT had left."""
    assert master.rrule is not None
    parts = recurrence.rule_parts(master.rrule)
    if "COUNT" in parts:
        before = recurrence.starts_before(master, original_start)
        master.rrule = recurrence.with_parts(master.rrule, COUNT=str(before))
        return max(int(parts["COUNT"]) - before, 0)
    until = (
        (original_start - timedelta(days=1)).strftime("%Y%m%d")
        if master.all_day
        else (original_start - timedelta(seconds=1)).strftime(recurrence.KEY_FORMAT)
    )
    master.rrule = recurrence.with_parts(master.rrule, UNTIL=until)
    return None


def _update_following(db: Session, user: User, target: Target, body: EventUpdate) -> Event:
    """This and the following occurrences: the series splits into two at the occurrence."""
    master = target.event
    assert target.original_start is not None and master.rrule is not None
    if target.original_start <= master.start_local:
        return _update_all(db, user, target, body)
    split = target.original_start
    base = target.occurrence_times()
    after = resolve_times(base, user, body)
    old_rule = master.rrule
    remaining = _truncate(master, split)
    # The rule the second half gets when only other things change: the rest of a COUNT.
    continued = old_rule if remaining is None else recurrence.with_parts(old_rule, COUNT=str(remaining))
    continued = _rule(continued, base)
    new_rule = _rule(body.rrule, after) if "rrule" in body.model_fields_set else _rule(continued, after)
    now = clock.now()
    calendar_id = master.calendar_id
    if body.calendar_id is not None and body.calendar_id != calendar_id:
        calendar_id = calendars.get_writable(db, user, body.calendar_id).id
    follower = Event(
        calendar_id=calendar_id,
        uid=str(uuid.uuid4()),
        title=master.title,
        description=master.description,
        location=master.location,
        color=master.color,
        rrule=new_rule,
        exdates=[],
        sequence=0,
        created_at_utc=now,
        updated_at_utc=now,
    )
    after.apply_to(follower)
    _apply_fields(follower, body)
    derive(follower)
    db.add(follower)
    db.flush()
    if body.tags is not None:
        _set_tags(db, user, follower, body.tags)
    else:
        _copy_tags(db, master, follower)

    later_exdates = [v for v in master.exdates if datetime.fromisoformat(v) >= split]
    if not _timing_changed(base, after, continued, new_rule) and calendar_id == master.calendar_id:
        # Nothing about the timing changed, so the later exceptions still fit the new series.
        for override in db.scalars(
            select(Event).where(Event.recurring_event_id == master.id, Event.original_start >= split)
        ):
            override.recurring_event_id = follower.id
            override.uid = follower.uid
        follower.exdates = later_exdates
    else:
        db.execute(
            sql_delete(Event).where(Event.recurring_event_id == master.id, Event.original_start >= split)
        )
    master.exdates = [v for v in master.exdates if datetime.fromisoformat(v) < split]
    derive(master)
    _touched(master)
    return follower


def update(
    db: Session,
    user: User,
    event_id: int,
    body: EventUpdate,
    *,
    scope: EditScope | None = None,
    occurrence: str | None = None,
) -> EventOut:
    target = resolve_target(db, user, event_id, occurrence)
    calendars.get_writable(db, user, target.calendar.id)
    if not target.is_series or target.original_start is None:
        if body.calendar_id is not None and body.calendar_id != target.calendar.id:
            moved_to = calendars.get_writable(db, user, body.calendar_id)
            target.event.calendar_id = moved_to.id
            for override in db.scalars(select(Event).where(Event.recurring_event_id == target.event.id)):
                override.calendar_id = moved_to.id
        changed = _update_plain(db, user, target, body)
        db.commit()
        return get(db, user, changed.id)
    if scope is None:
        raise InvalidInputError("scope_required", "Say whether to change this, following or all events")
    if scope == "this":
        _update_this(db, user, target, body)
        db.commit()
        return get(db, user, target.event.id, recurrence.occurrence_key(target.original_start))
    changed = (
        _update_all(db, user, target, body) if scope == "all" else _update_following(db, user, target, body)
    )
    db.commit()
    return get(db, user, changed.id)


# Delete


def delete(
    db: Session,
    user: User,
    event_id: int,
    *,
    scope: EditScope | None = None,
    occurrence: str | None = None,
) -> None:
    target = resolve_target(db, user, event_id, occurrence)
    calendars.get_writable(db, user, target.calendar.id)
    master = target.event
    if not target.is_series or target.original_start is None or scope == "all":
        # Overrides of a series go with it through ON DELETE CASCADE.
        db.delete(master)
        db.commit()
        return
    if scope is None:
        raise InvalidInputError("scope_required", "Say whether to delete this, following or all events")
    split = target.original_start
    if scope == "this":
        if target.override is not None:
            db.delete(target.override)
        master.exdates = sorted({*master.exdates, split.isoformat()})
    elif split <= master.start_local:
        db.delete(master)
        db.commit()
        return
    else:
        _truncate(master, split)
        _drop_exceptions(db, master, from_start=split)
    derive(master)
    _touched(master)
    db.commit()
