"""
HTTP API around the agent (FastAPI).

The web PWA talks to these endpoints; the agent underneath is the exact same one
the CLI uses. State is kept per session in-process: each session_id maps to one
Agent, so its conversation history persists across requests while the server runs.

Run it:  uv run uvicorn tandem.server:app --reload

Note: approvals use AutoApprove here. A real web approval flow (pause the tool,
ask the browser, resume) is a follow-up; the seam (ApprovalPolicy) already exists.
"""

from __future__ import annotations

import logging
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tandem.db import init_db
from tandem.routers import auth as auth_router
from tandem.routers import workspace as workspace_router

from tandem.agent.agent import Agent
from tandem.app import build_agent
from tandem.config import AppConfig
from tandem.memory.base import MemoryStore
from tandem.approvals import ApprovalBroker, BrokeredApproval
from tandem.skills.base import SkillStore
from tandem.skills.file_store import FileSkillStore

logging.basicConfig(level=logging.INFO)  # surface tandem.* INFO logs (tool calls, errors)


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    init_db()  # create tables on startup
    yield
    # Release all cached agents (MCP subprocesses, DB connections) on shutdown.
    if _state is not None:
        for cached in list(_state.sessions.values()):
            _close_agent(cached)
        _state.sessions.clear()


app = FastAPI(title="Tandem API", lifespan=lifespan)

# Let the local Next.js dev server call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(workspace_router.router)


# --- request/response models --------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    images: list[str] | None = None


class SourceModel(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    session_id: str
    text: str
    steps: int
    sources: list[SourceModel]


class MemoryModel(BaseModel):
    id: str | int | None
    kind: str
    content: str
    created_at: str | None


class SkillModel(BaseModel):
    name: str
    description: str


# --- lazy server state (so importing this module needs no API key) ------------
@dataclass
class _State:
    config: AppConfig
    memory: MemoryStore
    skills: SkillStore
    sessions: dict[str, Agent]


_state: _State | None = None
_state_lock = threading.Lock()
_broker = ApprovalBroker()  # mediates human approval of consequential tool calls
_MAX_SESSIONS = 8  # cap cached agents (each owns MCP subprocesses) — evict oldest


def _close_agent(agent: Agent) -> None:
    """Release an evicted agent's resources (MCP subprocesses, DB connections)."""
    close = getattr(agent, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def _get_state() -> _State:
    global _state
    if _state is None:
        with _state_lock:
            if _state is None:  # double-checked under lock
                from tandem.app import _build_memory  # reuse the composition root's choice

                config = AppConfig.from_env()
                _state = _State(
                    config=config,
                    memory=_build_memory(config),
                    skills=FileSkillStore(config.skills_dir),
                    sessions={},
                )
    return _state


def _agent_for(session_id: str) -> Agent:
    state = _get_state()
    agent = state.sessions.get(session_id)
    if agent is None:
        from tandem.app import build_mac_agent

        # Evict the oldest session(s) first, releasing their MCP subprocesses.
        while len(state.sessions) >= _MAX_SESSIONS:
            old_id, old_agent = next(iter(state.sessions.items()))
            state.sessions.pop(old_id, None)
            _broker.drop(old_id)
            _close_agent(old_agent)

        # The global /chat is the Mac personal AI (controls the local machine's apps).
        # Consequential actions route through the approval broker, scoped to this session.
        agent = build_mac_agent(state.config, approval=BrokeredApproval(session_id, _broker))
        state.sessions[session_id] = agent
    return agent


# --- endpoints ----------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    session_id = body.session_id or uuid.uuid4().hex
    try:
        agent = _agent_for(session_id)
        result = agent.send(body.message, images=body.images)
    except Exception:
        # The model/endpoint can fail unpredictably (bad request, context limit,
        # transient 5xx). Never surface a raw 500 to the command bar — log it and
        # return a graceful turn so the session stays usable.
        logging.getLogger("tandem.server").exception("chat failed for session %s", session_id)
        return ChatResponse(
            session_id=session_id,
            text="Sorry — I hit an error handling that one. Try rephrasing, or ask me something else.",
            steps=0,
            sources=[],
        )
    return ChatResponse(
        session_id=session_id,
        text=result.text,
        steps=result.steps,
        sources=[SourceModel(title=s.title, url=s.url) for s in result.sources],
    )


@app.get("/memory", response_model=list[MemoryModel])
def memory() -> list[MemoryModel]:
    records = _get_state().memory.all()
    return [
        MemoryModel(id=r.id, kind=r.kind, content=r.content, created_at=r.created_at)
        for r in records
    ]


@app.get("/skills", response_model=list[SkillModel])
def skills() -> list[SkillModel]:
    return [
        SkillModel(name=s.name, description=s.description)
        for s in _get_state().skills.all()
    ]


class PendingModel(BaseModel):
    id: str
    tool: str
    description: str


class ApproveIn(BaseModel):
    id: str
    approved: bool


@app.get("/pending/{session_id}")
def pending(session_id: str) -> PendingModel | None:
    """What (if anything) in this session is waiting for the user's approval."""
    p = _broker.pending(session_id)
    return PendingModel(id=p.id, tool=p.tool, description=p.description) if p else None


@app.post("/approve/{session_id}")
def approve(session_id: str, body: ApproveIn) -> dict[str, bool]:
    """Resolve the pending approval — only if the id matches the current action."""
    honored = _broker.resolve(session_id, body.id, body.approved)
    return {"ok": honored}
