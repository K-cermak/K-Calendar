from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import READ_METHODS, Database, DbSession
from app.errors import ForbiddenError, UnauthorizedError
from app.models import ApiToken, AuthSession, User
from app.services import limits
from app.services.auth import sessions, tokens
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


def set_session_cookie(response: Response, settings: Settings, db: Session, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(timedelta(days=limits.session_days(db)).total_seconds()),
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
    """The signed-in user from the session cookie, for account, security and admin endpoints.

    API tokens never reach these (SPEC 6): password, TOTP, sessions, tokens, OIDC and users.
    """
    if "authorization" in request.headers:
        raise ForbiddenError("token_not_allowed", "API tokens cannot be used for this")
    token = request.cookies.get(SESSION_COOKIE)
    found = sessions.resolve(db, token) if token else None
    if token is None or found is None:
        raise UnauthorizedError()
    session, user = found
    if sessions.touch_due(session):
        _write(request, db, lambda writer: sessions.touch(writer, session.id))
        set_session_cookie(response, settings, db, token)
    return Auth(user=user, session=session)


CurrentAuth = Annotated[Auth, Depends(get_auth)]


def get_admin(auth: CurrentAuth) -> Auth:
    # The flag comes from the row loaded for this request, so revoking admin rights applies at once.
    if not auth.user.is_admin:
        raise ForbiddenError("not_admin", "Only admins can do this")
    return auth


AdminAuth = Annotated[Auth, Depends(get_admin)]


@dataclass
class ApiAuth:
    """Who is calling a calendar data endpoint: a browser session, or an API token."""

    user: User
    token: ApiToken | None


def get_api_auth(request: Request, response: Response, db: DbSession, settings: AppSettings) -> ApiAuth:
    """A Bearer token within its scope, or the session cookie. Every user-scoped call starts here."""
    header = request.headers.get("authorization")
    if header is None:
        return ApiAuth(user=get_auth(request, response, db, settings).user, token=None)
    scheme, _, secret = header.partition(" ")
    found = tokens.resolve(db, secret.strip()) if scheme.lower() == "bearer" else None
    if found is None:
        raise UnauthorizedError("The token is not valid, has expired or was revoked")
    token, user = found
    if request.method not in READ_METHODS and token.scope != "write":
        raise ForbiddenError("insufficient_scope", "This token can only read")
    if tokens.touch_due(token):
        _write(request, db, lambda writer: tokens.touch(writer, token.id))
    return ApiAuth(user=user, token=token)


CurrentApiAuth = Annotated[ApiAuth, Depends(get_api_auth)]
