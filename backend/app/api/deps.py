"""Shared API dependencies: session authentication, CSRF and role checks."""

from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import tokens_match
from app.db.enums import UserRole
from app.db.models import User, UserSession
from app.db.session import get_db
from app.db.types import utcnow
from app.services import auth as auth_service

SESSION_COOKIE = "lf_session"
# Angular's HttpClient reads this cookie and echoes it in the header below by default.
CSRF_COOKIE = "XSRF-TOKEN"
CSRF_HEADER = "X-XSRF-TOKEN"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def set_session_cookies(response: Response, settings: Settings, session_token: str, csrf_token: str,
                        expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - utcnow()).total_seconds()))
    common = {"max_age": max_age, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **common)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="lax")


def get_current_session(request: Request, db: DbSession) -> UserSession:
    raw = request.cookies.get(SESSION_COOKIE)
    session = auth_service.resolve_session(db, raw) if raw else None
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    if request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER)
        if not header or not tokens_match(header, session.csrf_token_hash):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token.")
    return session


CurrentSession = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return user

    return dependency


StaffUser = Annotated[User, Depends(require_roles(UserRole.STAFF, UserRole.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
