"""Subscribed calendars: fetching external ICS URLs safely and keeping their events (SPEC 10).

Fetching URLs that users supply is a server-side request forgery risk. Every hop resolves the host,
refuses loopback, private and link-local addresses (unless allowed), and then connects to exactly
the address that was checked, so a second DNS answer cannot point somewhere else.
"""

import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.errors import InvalidInputError
from app.models import Calendar, CalendarSubscription, User
from app.services import calendars, clock, ics, importer
from app.version import VERSION

logger = logging.getLogger(__name__)

MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 30
MAX_REDIRECTS = 5
MIN_INTERVAL_MINUTES = 15
DEFAULT_INTERVAL_MINUTES = 60


class FetchError(Exception):
    pass


def normalize_url(url: str) -> str:
    """webcal:// is https:// for calendars; anything but http and https is refused."""
    value = url.strip()
    if value.lower().startswith("webcal://"):
        value = "https://" + value[len("webcal://") :]
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidInputError("invalid_url", "Enter an http, https or webcal address")
    if parts.username or parts.password:
        raise InvalidInputError("invalid_url", "Addresses with a user name or password are not supported")
    return urlunsplit(parts)


def _allowed(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def resolve(host: str, port: int, allow_private: bool) -> str:
    """One address of host that may be fetched; all of them must pass, or none is used."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise FetchError(f"The host {host} could not be found") from None
    addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses:
        raise FetchError(f"The host {host} could not be found")
    if not allow_private and not all(_allowed(a) for a in addresses):
        raise FetchError("The address points to a private network, which is not allowed")
    return str(addresses[0])


@dataclass
class Fetched:
    body: bytes | None  # None when the server says nothing changed
    etag: str | None
    last_modified: str | None


def fetch(url: str, *, etag: str | None, last_modified: str | None, allow_private: bool) -> Fetched:
    """GET with conditional headers, following redirects one checked hop at a time."""
    deadline = time.monotonic() + TIMEOUT_S
    headers = {
        "User-Agent": f"{get_branding().name}/{VERSION} (calendar subscription)",
        "Accept": "text/calendar, */*;q=0.5",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    current = url
    with httpx2.Client(timeout=TIMEOUT_S, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise FetchError("A redirect led to an address that is not http or https")
            host = parts.hostname
            port = parts.port or (443 if parts.scheme == "https" else 80)
            address = resolve(host, port, allow_private)
            literal = f"[{address}]" if ":" in address else address
            pinned = urlunsplit((parts.scheme, f"{literal}:{port}", parts.path or "/", parts.query, ""))
            host_header = host if parts.port is None else f"{host}:{parts.port}"
            request = client.build_request(
                "GET",
                pinned,
                headers={**headers, "Host": host_header},
                extensions={"sni_hostname": host},
            )
            try:
                response = client.send(request, stream=True)
            except httpx2.HTTPError as exc:
                raise FetchError(f"The server could not be reached: {type(exc).__name__}") from None
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("The server sent a redirect without an address")
                    current = urljoin(current, location)
                    continue
                if response.status_code == 304:
                    return Fetched(None, etag, last_modified)
                if response.status_code != 200:
                    raise FetchError(f"The server answered {response.status_code}")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise FetchError("The calendar is larger than 10 MB")
                    if time.monotonic() > deadline:
                        raise FetchError("The server took longer than 30 seconds")
                return Fetched(
                    bytes(body), response.headers.get("etag"), response.headers.get("last-modified")
                )
            finally:
                response.close()
    raise FetchError("Too many redirects")


def get(db: Session, calendar: Calendar) -> CalendarSubscription:
    subscription = db.get(CalendarSubscription, calendar.id)
    if subscription is None:
        raise InvalidInputError("not_subscription", "This calendar is not a subscription")
    return subscription


def create(db: Session, user: User, *, url: str, name: str, color: str, interval: int) -> Calendar:
    source = normalize_url(url)
    calendar = Calendar(
        user_id=user.id,
        name=name.strip() or urlsplit(source).hostname or "Subscription",
        color=color,
        kind="subscription",
        is_visible=True,
        sort_order=calendars.next_sort_order(db, user),
    )
    db.add(calendar)
    db.flush()
    db.add(
        CalendarSubscription(
            calendar_id=calendar.id,
            source_url=source,
            refresh_interval_minutes=max(interval, MIN_INTERVAL_MINUTES),
            next_fetch_at_utc=clock.now(),
            last_status="pending",
        )
    )
    db.commit()
    return calendar


def refresh(db: Session, settings: Settings, calendar_id: int) -> None:
    """Fetches one subscription and stores the result.

    The fetch happens outside any transaction, so a slow server never holds the database's write
    lock; the new events then replace the old ones in one transaction.
    """
    subscription = db.get(CalendarSubscription, calendar_id)
    calendar = db.get(Calendar, calendar_id)
    if subscription is None or calendar is None:
        return
    user = db.get(User, calendar.user_id)
    assert user is not None
    url, etag, modified = subscription.source_url, subscription.etag, subscription.last_modified
    db.commit()
    now = clock.now()
    try:
        fetched = fetch(
            url,
            etag=etag,
            last_modified=modified,
            allow_private=settings.allow_private_subscription_urls,
        )
        parsed: list[ics.ParsedEvent] | None = None
        if fetched.body is not None:
            parsed, _skipped = ics.parse(fetched.body, user.timezone)
    except (FetchError, InvalidInputError) as exc:
        message = exc.message if isinstance(exc, InvalidInputError) else str(exc)
        # The previous events stay; only the error is recorded.
        subscription = db.get(CalendarSubscription, calendar_id)
        if subscription is not None:
            subscription.last_status = "error"
            subscription.last_error = message[:1000]
            subscription.next_fetch_at_utc = now + timedelta(minutes=subscription.refresh_interval_minutes)
            db.commit()
        logger.info("Subscription %s could not be refreshed: %s", calendar_id, message)
        return
    subscription = db.get(CalendarSubscription, calendar_id)
    calendar = db.get(Calendar, calendar_id)
    if subscription is None or calendar is None:
        return
    if parsed is not None:
        importer.replace_all(db, user, calendar, parsed)
        subscription.etag = fetched.etag
        subscription.last_modified = fetched.last_modified
    subscription.last_status = "ok"
    subscription.last_error = None
    subscription.last_fetched_at_utc = now
    subscription.next_fetch_at_utc = now + timedelta(minutes=subscription.refresh_interval_minutes)
    db.commit()


def due(db: Session) -> list[int]:
    rows = db.scalars(
        select(CalendarSubscription.calendar_id).where(CalendarSubscription.next_fetch_at_utc <= clock.now())
    )
    return list(rows)
