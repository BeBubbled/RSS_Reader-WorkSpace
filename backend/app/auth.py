from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

COOKIE_NAME = "rss_ai_session"
SESSION_SALT = "rss-ai-session-v1"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class CurrentUser(BaseModel):
    username: str


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.app_session_secret, salt=SESSION_SALT)


def authenticate(credentials: LoginRequest, settings: Settings) -> CurrentUser | None:
    valid_username = hmac.compare_digest(credentials.username, settings.admin_username)
    valid_password = hmac.compare_digest(credentials.password, settings.admin_password)
    if valid_username and valid_password:
        return CurrentUser(username=settings.admin_username)
    return None


def create_session(response: Response, user: CurrentUser, settings: Settings) -> None:
    token = _serializer(settings).dumps({"username": user.username})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_cookie_max_age_seconds,
        path="/",
    )


def clear_session(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def get_current_user(
    session_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> CurrentUser:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = _serializer(settings).loads(
            session_token, max_age=settings.session_cookie_max_age_seconds
        )
    except (BadSignature, SignatureExpired) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from error
    if payload.get("username") != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return CurrentUser(username=settings.admin_username)
