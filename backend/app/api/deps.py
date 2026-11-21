from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import READ_METHODS, Database, DbSession
from app.errors import ForbiddenError, UnauthorizedError
from app.models import AuthSession, User
from app.services.auth import sessions
from app.services.auth.throttle import LoginThrottle

SESSION_COOKIE = "session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_throttle(request: Request) -> LoginThrottle:
    return request.app.state.throttle


AppSettings = Annotated[Settings, Depends(get_settings)]
Throttle = Annotated[LoginThrottle, Depends(get_throttle)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(timedelta(days=settings.session_days).total_seconds()),
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/"
    )


@dataclass
class Auth:
    user: User
    session: AuthSession


def _write(request: Request, db: Session, work: Callable[[Session], None]) -> None:
    """Runs a small bookkeeping write while authenticating.

    A read request gets its own short write transaction, so it keeps its read-only one. A write
    request already holds the write lock through db, and a second writer would wait for it in vain.
    """
    if request.method in READ_METHODS:
        database: Database = request.app.state.db
        with database.writer() as writer:
            work(writer)
    else:
        work(db)


def get_auth(request: Request, response: Response, db: DbSession, settings: AppSettings) -> Auth:
    """The signed-in user from the session cookie. Every user-scoped service call starts here."""
    token = request.cookies.get(SESSION_COOKIE)
    found = sessions.resolve(db, token) if token else None
    if token is None or found is None:
        raise UnauthorizedError()
    session, user = found
    if sessions.touch_due(session):
        _write(request, db, lambda writer: sessions.touch(writer, settings, session.id))
        set_session_cookie(response, settings, token)
    return Auth(user=user, session=session)


CurrentAuth = Annotated[Auth, Depends(get_auth)]


def get_admin(auth: CurrentAuth) -> Auth:
    # The flag comes from the row loaded for this request, so revoking admin rights applies at once.
    if not auth.user.is_admin:
        raise ForbiddenError("not_admin", "Only admins can do this")
    return auth


AdminAuth = Annotated[Auth, Depends(get_admin)]
