"""Search over the user's events, by FTS5 with prefix matching (SPEC 9)."""

import re
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Calendar, Event, User
from app.schemas.calendar import SearchResult
from app.services import clock, events, recurrence, tags, zones
from app.services.occurrences import overridden_starts

MAX_RESULTS = 50
MAX_MATCHES = 500
# How far a series is searched for its next or last occurrence; within the range limit.
HORIZON = timedelta(days=399)
_TOKEN = re.compile(r"\w+", re.UNICODE)


def fts_query(query: str) -> str | None:
    """Every word as a prefix, all of them required: "den zub" finds "Dentist, Zubař"."""
    words = _TOKEN.findall(query)
    if not words:
        return None
    return " ".join(f'"{word}"*' for word in words[:10])


def _matching_ids(db: Session, user: User, match: str) -> list[int]:
    rows = db.execute(
        text(
            "SELECT events_fts.rowid FROM events_fts "
            "JOIN events e ON e.id = events_fts.rowid "
            "JOIN calendars c ON c.id = e.calendar_id "
            "WHERE events_fts MATCH :match AND c.user_id = :user_id "
            "ORDER BY rank LIMIT :limit"
        ),
        {"match": match, "user_id": user.id, "limit": MAX_MATCHES},
    )
    return [row[0] for row in rows]


def _pick(instances: list[recurrence.Instance], now: datetime) -> tuple[recurrence.Instance, bool] | None:
    """The next occurrence that has not ended, otherwise the last one."""
    upcoming = [i for i in instances if i.end_utc > now]
    if upcoming:
        return min(upcoming, key=lambda i: i.start_utc), True
    if instances:
        return max(instances, key=lambda i: i.start_utc), False
    return None


def _occurrence_for(
    db: Session, event: Event, zone: str, now: datetime
) -> tuple[recurrence.Instance, bool] | None:
    """Where a matching event shows: itself, or for a series its next or last occurrence."""
    if event.recurring_event_id is not None:
        # A matching override stands for its own occurrence of the series.
        instance = recurrence.instants(
            event,
            event.start_local,
            event.end_local,
            zone,
            master_id=event.recurring_event_id,
            original_start=event.original_start,
        )
        return instance, instance.end_utc > now
    if event.rrule is None:
        instance = recurrence.instants(event, event.start_local, event.end_local, zone)
        return instance, instance.end_utc > now
    overridden = overridden_starts(db, [event.id])
    ahead = recurrence.expand([event], now, now + HORIZON, zone, overridden)
    if ahead:
        return _pick(ahead, now)
    # The series is over, or skips the next year: look back for its last occurrence.
    end = event.series_end_utc or now
    behind = recurrence.expand(
        [event], max(event.start_utc, end - HORIZON), end + timedelta(days=1), zone, overridden
    )
    return _pick(behind, now)


def search(db: Session, user: User, query: str, tz: str | None) -> list[SearchResult]:
    zone = zones.check_zone(tz or user.timezone)
    match = fts_query(query)
    if match is None:
        return []
    ids = _matching_ids(db, user, match)
    if not ids:
        return []
    rows = db.execute(
        select(Event, Calendar).join(Calendar, Calendar.id == Event.calendar_id).where(Event.id.in_(ids))
    ).all()
    now = clock.now()
    found: dict[str, tuple[recurrence.Instance, bool, Calendar]] = {}
    for event, calendar in rows:
        picked = _occurrence_for(db, event, zone, now)
        if picked is None:
            continue
        instance, upcoming = picked
        # A series shows once, even when the master and some of its overrides all match.
        series_key = str(instance.master_id or event.id)
        if series_key in found and event.recurring_event_id is not None:
            continue
        found[series_key] = (instance, upcoming, calendar)

    chosen = sorted(
        found.values(),
        key=lambda f: (0, f[0].start_utc.timestamp()) if f[1] else (1, -f[0].start_utc.timestamp()),
    )[:MAX_RESULTS]
    tags_by_event = events.tags_of(db, [i.event.id for i, _, _ in chosen])
    results: list[SearchResult] = []
    for instance, upcoming, calendar in chosen:
        event = instance.event
        if event.all_day:
            start_text = instance.start_local.date().isoformat()
            end_text = instance.end_local.date().isoformat()
        else:
            start_text = zones.format_local(zones.to_local(instance.start_utc, zone))
            end_text = zones.format_local(zones.to_local(instance.end_utc, zone))
        results.append(
            SearchResult.model_validate(
                {
                    "occurrence_id": instance.id,
                    "event_id": instance.master_id or event.id,
                    "occurrence": instance.occurrence_key,
                    "calendar_id": calendar.id,
                    "title": event.title,
                    "location": event.location,
                    "color": event.color or calendar.color,
                    "all_day": event.all_day,
                    "start": start_text,
                    "end": end_text,
                    "start_utc": instance.start_utc,
                    "upcoming": upcoming,
                    "recurring": instance.master_id is not None,
                    "tags": [tags.to_out(t) for t in tags_by_event[event.id]],
                }
            )
        )
    return results
