"""
Auth primitives: password hashing (bcrypt), JWT tokens, and the current-user
dependency. We use the `bcrypt` and `pyjwt` libraries directly — small, standard,
and no crypto is hand-rolled.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from tandem.db import get_session
from tandem.models import User

_SECRET = os.getenv("JWT_SECRET", "dev-insecure-change-me")
_ALGO = "HS256"
_TOKEN_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    # bcrypt caps input at 72 bytes; truncate defensively.
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=_TOKEN_DAYS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credentials_error
    user = session.get(User, user_id)
    if user is None:
        raise credentials_error
    return user
