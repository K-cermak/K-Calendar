"""The words of push notifications and e-mails, in the recipient's language and zone (SPEC 8)."""

from datetime import datetime

from app.i18n import t
from app.models import Event, User
from app.services import zones

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def format_time(user: User, local: datetime) -> str:
    if user.time_format == "12":
        hour = local.hour % 12 or 12
        return t(
            user.locale,
            "time.twelve",
            hour=hour,
            minute=f"{local.minute:02d}",
            half=t(user.locale, "time.am" if local.hour < 12 else "time.pm"),
        )
    return f"{local.hour:02d}:{local.minute:02d}"


def format_day(user: User, local: datetime) -> str:
    return t(
        user.locale,
        "date.day",
        weekday=t(user.locale, f"date.weekday.{WEEKDAYS[local.weekday()]}"),
        day=local.day,
        month=t(user.locale, f"date.month.{MONTHS[local.month - 1]}"),
    )


def when(user: User, event: Event, start_utc: datetime) -> str:
    """ "Mon 23 Nov, 09:00" in the user's zone, or just the day for an all-day event."""
    if event.all_day:
        return format_day(user, event.start_local)
    local = zones.to_local(start_utc, user.timezone)
    return t(user.locale, "date.day_time", day=format_day(user, local), time=format_time(user, local))


def title(user: User, event: Event) -> str:
    return event.title or t(user.locale, "event.no_title")


def reminder_body(user: User, event: Event, start_utc: datetime) -> str:
    text = when(user, event, start_utc)
    return f"{text} · {event.location}" if event.location else text
