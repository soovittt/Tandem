"""
Workspace endpoints: organizations, projects, and integrations — all tenant-scoped
by the caller's memberships. This is the Linear-style structure (org → workspace →
connections), not ticket tracking.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from tandem.db import get_session
from tandem.models import Integration, Investigation, Membership, Organization, Project, User
from tandem.authn import get_current_user

router = APIRouter(tags=["workspace"])


# --- schemas ------------------------------------------------------------------
class OrgOut(BaseModel):
    id: int
    name: str
    slug: str
    role: str


class ProjectIn(BaseModel):
    name: str
    key: str
    description: str = ""


class ProjectOut(BaseModel):
    id: int
    org_id: int
    name: str
    key: str
    description: str


class IntegrationIn(BaseModel):
    kind: str
    name: str
    status: str = "connected"


class IntegrationOut(BaseModel):
    id: int
    project_id: int
    kind: str
    name: str
    status: str


# --- tenancy guards -----------------------------------------------------------
def _membership(org_id: int, user: User, session: Session) -> Membership:
    m = session.exec(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)
    ).first()
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    return m


def _project_for(project_id: int, user: User, session: Session) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    _membership(project.org_id, user, session)  # authorizes access
    return project


# --- organizations ------------------------------------------------------------
@router.get("/orgs", response_model=list[OrgOut])
def list_orgs(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Membership).where(Membership.user_id == user.id)).all()
    out: list[OrgOut] = []
    for m in rows:
        org = session.get(Organization, m.org_id)
        if org:
            out.append(OrgOut(id=org.id, name=org.name, slug=org.slug, role=m.role))
    return out


# --- projects -----------------------------------------------------------------
@router.get("/orgs/{org_id}/projects", response_model=list[ProjectOut])
def list_projects(org_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _membership(org_id, user, session)
    projects = session.exec(select(Project).where(Project.org_id == org_id)).all()
    return [ProjectOut(**p.model_dump()) for p in projects]


@router.post("/orgs/{org_id}/projects", response_model=ProjectOut)
def create_project(
    org_id: int,
    body: ProjectIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _membership(org_id, user, session)
    project = Project(org_id=org_id, name=body.name, key=body.key, description=body.description)
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectOut(**project.model_dump())


# --- integrations -------------------------------------------------------------
@router.get("/projects/{project_id}/integrations", response_model=list[IntegrationOut])
def list_integrations(project_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _project_for(project_id, user, session)
    items = session.exec(select(Integration).where(Integration.project_id == project_id)).all()
    return [IntegrationOut(**i.model_dump()) for i in items]


@router.post("/projects/{project_id}/integrations", response_model=IntegrationOut)
def add_integration(
    project_id: int,
    body: IntegrationIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _project_for(project_id, user, session)
    integration = Integration(project_id=project_id, kind=body.kind, name=body.name, status=body.status)
    session.add(integration)
    session.commit()
    session.refresh(integration)
    return IntegrationOut(**integration.model_dump())


# --- investigations -----------------------------------------------------------
def _investigation_out(inv: Investigation) -> dict[str, Any]:
    """Merge core columns with the parsed JSON state into the frontend shape."""
    return {
        "id": str(inv.id),
        "title": inv.title,
        "status": inv.status,
        "priority": inv.priority,
        "owner": inv.owner,
        "summary": inv.summary,
        "updated": inv.updated,
        "hypotheses": json.loads(inv.hypotheses_json),
        "timeline": json.loads(inv.timeline_json),
        "evidence": json.loads(inv.evidence_json),
        "entities": json.loads(inv.entities_json),
        "nextSteps": json.loads(inv.next_steps_json),
    }


@router.get("/projects/{project_id}/investigations")
def list_investigations(
    project_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    _project_for(project_id, user, session)
    rows = session.exec(select(Investigation).where(Investigation.project_id == project_id)).all()
    return [_investigation_out(i) for i in rows]


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    inv = session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    _project_for(inv.project_id, user, session)  # authorize via the project's org
    return _investigation_out(inv)


# --- project-scoped assistant -------------------------------------------------
class ChatIn(BaseModel):
    message: str
    session_id: str | None = None
    images: list[str] | None = None


# Live agents, keyed by "<project_id>:<session_id>". Each holds its conversation;
# all sessions of a project share that project's isolated memory store.
_project_agents: dict[str, Any] = {}


@router.post("/projects/{project_id}/chat")
def project_chat(
    project_id: int,
    body: ChatIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    project = _project_for(project_id, user, session)
    session_id = body.session_id or uuid.uuid4().hex
    key = f"{project_id}:{session_id}"

    agent = _project_agents.get(key)
    if agent is None:
        from tandem.app import build_project_agent
        from tandem.config import AppConfig

        integrations = session.exec(
            select(Integration).where(Integration.project_id == project_id)
        ).all()
        agent = build_project_agent(
            AppConfig.from_env(),
            project_id=project_id,
            project_name=project.name,
            integration_names=[i.name for i in integrations],
        )
        _project_agents[key] = agent

    result = agent.send(body.message, images=body.images)
    return {
        "session_id": session_id,
        "text": result.text,
        "steps": result.steps,
        "sources": [{"title": s.title, "url": s.url} for s in result.sources],
    }
