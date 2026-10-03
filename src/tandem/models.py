"""
The multi-tenant data model.

    Organization ──< Membership >── User        (who belongs where, and their role)
         │
         └──< Project (workspace)
                   └──< Integration            (the connected systems — the point)

Roles/kinds/status are stored as plain strings (robust across SQLite/Postgres);
the allowed values are documented next to each field.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_now)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    hashed_password: str
    created_at: datetime = Field(default_factory=_now)


class Membership(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = Field(default="member")  # owner | admin | member
    created_at: datetime = Field(default_factory=_now)


class Project(SQLModel, table=True):
    """A workspace inside an org — where investigations, connections, and the agent live."""

    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    name: str
    key: str  # short handle, e.g. "BAT"
    description: str = ""
    created_at: datetime = Field(default_factory=_now)


class Integration(SQLModel, table=True):
    """A connected external system, scoped to a project."""

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    # benchling | jira | slack | drive | sharepoint | instruments | mcp | web
    kind: str
    name: str
    status: str = "connected"  # connected | available | error
    config_json: str = "{}"    # opaque config (encrypt before hosting)
    created_at: datetime = Field(default_factory=_now)


class Investigation(SQLModel, table=True):
    """
    The unit of technical work, scoped to a project. Rich nested state
    (hypotheses, timeline, evidence, entities, next steps) is stored as JSON —
    pragmatic now, normalizable later without changing the API shape.
    """

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    title: str
    status: str = "active"       # active | awaiting | blocked | resolved
    priority: str = "medium"     # high | medium | low
    owner: str = ""
    summary: str = ""
    updated: str = ""            # human label for the demo, e.g. "20 min ago"
    hypotheses_json: str = "[]"
    timeline_json: str = "[]"
    evidence_json: str = "[]"
    entities_json: str = "[]"
    next_steps_json: str = "[]"
    created_at: datetime = Field(default_factory=_now)
