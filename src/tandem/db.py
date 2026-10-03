"""
Database layer (SQLModel + SQLite for now, Postgres-ready later).

One engine, a session dependency, and a create-tables call. Swapping to a hosted
Postgres is only a DATABASE_URL change — no model or query changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

_DATA_DIR = Path(os.getenv("TANDEM_DATA_DIR", ".tandem"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DATA_DIR / 'tandem.db'}")

# check_same_thread=False lets FastAPI's threads share the SQLite connection.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables. Import models first so they're registered on the metadata."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    import tandem.models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a session, closed after the request."""
    with Session(engine) as session:
        yield session
