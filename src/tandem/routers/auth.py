"""Auth endpoints: register (creates a user + their org), login, and /me."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from tandem.db import get_session
from tandem.models import Membership, Organization, User
from tandem.authn import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    name: str
    password: str
    org_name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    name: str


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "org"
    return base


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, session: Session = Depends(get_session)) -> TokenOut:
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=body.email, name=body.name, hashed_password=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create the org and make the new user its owner.
    slug = _slugify(body.org_name)
    if session.exec(select(Organization).where(Organization.slug == slug)).first():
        slug = f"{slug}-{user.id}"
    org = Organization(name=body.org_name, slug=slug)
    session.add(org)
    session.commit()
    session.refresh(org)

    session.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    session.commit()

    # Give the new org a live demo workspace so the app isn't empty on first login.
    from tandem.seed import seed_demo

    seed_demo(session, org.id)

    return TokenOut(access_token=create_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenOut:
    # OAuth2 form uses `username`; we treat it as the email.
    user = session.exec(select(User).where(User.email == form.username)).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)
