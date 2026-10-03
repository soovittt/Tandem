"""
HTTP API around the Mac personal-AI agent (FastAPI).

The native command bar talks to these endpoints. State is per session in-process:
each session_id maps to one Agent, so its conversation history + MCP subprocesses
persist across requests while the server runs (capped + LRU-evicted).

Run it:  uv run uvicorn tandem.server:app --reload
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tandem.agent.agent import Agent
from tandem.app import build_mac_agent
from tandem.agent.approval import ApprovalBroker, BrokeredApproval
from tandem.config import AppConfig
from tandem.conversation import ConversationStore
from tandem.whatsapp_bridge import WhatsAppBridge

logging.basicConfig(level=logging.INFO)  # surface tandem.* INFO logs (tool calls, errors)


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    # Reconnect a previously-linked WhatsApp bridge on boot (non-blocking) so WhatsApp
    # just works after a restart; first-time linking starts it via /whatsapp/connect.
    if _whatsapp.has_session():
        threading.Thread(target=_whatsapp.ensure_running, daemon=True).start()
    yield
    # Release cached agents (memory handles), the shared MCP servers, and the bridge.
    if _state is not None:
        for cached in list(_state.sessions.values()):
            _close_agent(cached)
        _state.sessions.clear()
        for integration in _state.mcp[1]:
            _close_agent(integration)  # .close() duck-typed; releases the subprocess
        _state.conversations.close()
    _whatsapp.stop()


app = FastAPI(title="Tandem API", lifespan=lifespan)


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


class PendingModel(BaseModel):
    id: str
    tool: str
    description: str


class ApproveIn(BaseModel):
    id: str
    approved: bool


# --- lazy server state (so importing this module needs no API key) ------------
@dataclass
class _State:
    config: AppConfig
    mcp: tuple  # (tools, integrations) — ONE set of MCP servers shared by all agents
    conversations: ConversationStore  # persisted chat turns per session
    sessions: "OrderedDict[str, Agent]" = field(default_factory=OrderedDict)


_state: _State | None = None
_state_lock = threading.Lock()
_broker = ApprovalBroker()  # mediates human approval of consequential tool calls
_whatsapp = WhatsAppBridge()  # manages the local WhatsApp bridge process + QR status
_MAX_SESSIONS = 8  # cap cached agents (each owns MCP subprocesses) — LRU-evict


def _close_agent(agent: Agent) -> None:
    """Release an evicted agent's resources (MCP subprocesses, memory handles)."""
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
                from tandem.mcp_servers import load_mcp_tools

                config = AppConfig.from_env()
                # Spawn the MCP servers ONCE here; every session agent shares them.
                _state = _State(
                    config=config,
                    mcp=load_mcp_tools(),
                    conversations=ConversationStore(config.data_dir / "conversations.db"),
                )
    return _state


def _agent_for(session_id: str) -> Agent:
    state = _get_state()
    agent = state.sessions.get(session_id)
    if agent is not None:
        state.sessions.move_to_end(session_id)  # mark most-recently-used
        return agent
    # Evict the least-recently-used session(s), releasing their MCP subprocesses.
    while len(state.sessions) >= _MAX_SESSIONS:
        old_id, old_agent = state.sessions.popitem(last=False)
        _broker.drop(old_id)
        _close_agent(old_agent)
    # /chat is the Mac personal AI (controls the local machine's apps). Consequential
    # actions route through the approval broker, scoped to this session. The MCP
    # servers are shared (loaded once), so this is just memory + tool wiring now.
    agent = build_mac_agent(
        state.config, approval=BrokeredApproval(session_id, _broker), mcp=state.mcp
    )
    agent.seed_history(state.conversations.load(session_id))  # restore prior turns
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
    convos = _get_state().conversations
    convos.append(session_id, "user", body.message)
    convos.append(session_id, "assistant", result.text)
    return ChatResponse(
        session_id=session_id,
        text=result.text,
        steps=result.steps,
        sources=[SourceModel(title=s.title, url=s.url) for s in result.sources],
    )


@app.post("/chat/stream")
def chat_stream(body: ChatRequest) -> StreamingResponse:
    """Same turn as /chat, streamed as Server-Sent Events: a `session` event, then
    `token`/`tool` events as the agent works, and a final `done` event with the
    authoritative answer. Approval still flows over /pending + /approve meanwhile."""
    session_id = body.session_id or uuid.uuid4().hex

    def events():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        final_text = ""
        try:
            for event in _agent_for(session_id).stream(body.message, images=body.images):
                if event.get("type") == "done":
                    final_text = event.get("text", "")
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            logging.getLogger("tandem.server").exception("stream failed for %s", session_id)
            done = {"type": "done", "text": "Sorry — I hit an error handling that one.",
                    "steps": 0, "sources": []}
            yield f"data: {json.dumps(done)}\n\n"
            return
        convos = _get_state().conversations
        convos.append(session_id, "user", body.message)
        convos.append(session_id, "assistant", final_text)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/integrations")
def integrations() -> list[dict]:
    """Everything the Control Center shows: connected core integrations + what's next."""
    from tandem.mcp_servers import enabled_server_names

    enabled = set(enabled_server_names())
    wa = _whatsapp.status()
    wa_status = "connected" if wa["connected"] else ("linking" if wa["qr"] else "disconnected")

    # Only EXTERNAL things you actually connect. Built-ins (Mac control, memory,
    # skills) are always-on and aren't listed as connectable integrations.
    items = [
        {"id": "apple", "name": "Apple Apps", "icon": "apple.logo",
         "desc": "Messages, Notes, Mail, Reminders, Calendar, Contacts, Maps",
         "status": "connected" if "apple-mcp" in enabled else "available"},
        {"id": "whatsapp", "name": "WhatsApp", "icon": "bubble.left.and.bubble.right.fill",
         "desc": "Read & send chats and groups", "status": wa_status},
    ]
    for sid, name, icon, desc in [
        ("slack", "Slack", "number", "Channels & DMs"),
        ("gmail", "Gmail", "envelope.fill", "Email"),
        ("notion", "Notion", "doc.text.fill", "Docs & databases"),
        ("drive", "Google Drive", "folder.fill", "Files"),
    ]:
        items.append({"id": sid, "name": name, "icon": icon, "desc": desc, "status": "coming_soon"})
    return items


@app.get("/model")
def model_info() -> dict:
    """The serving model + a live reachability check, for the Model pane."""
    cfg = AppConfig.from_env()
    reachable = False
    try:
        import urllib.request

        with urllib.request.urlopen(cfg.llm.base_url.rstrip("/") + "/models", timeout=4) as r:
            reachable = r.status == 200
    except Exception:
        reachable = False
    return {
        "model": cfg.llm.model,
        "base_url": cfg.llm.base_url,
        "reachable": reachable,
        "reasoning": cfg.reasoning,
        "tool_mode": cfg.tool_mode,
    }


@app.get("/whatsapp/status")
def whatsapp_status() -> dict:
    """{running, connected, qr}. The app polls this to drive Connect WhatsApp."""
    return _whatsapp.status()


@app.post("/whatsapp/connect")
def whatsapp_connect() -> dict:
    """Start the bridge (if needed) so a QR appears / it reconnects. Returns status."""
    return _whatsapp.ensure_running()


@app.get("/conversations")
def conversations_list() -> list[dict]:
    """All past chats (most recent first) for the history list."""
    return _get_state().conversations.list_sessions()


@app.get("/conversation/{session_id}")
def conversation(session_id: str) -> list[dict]:
    """The persisted thread for a session, so the app restores it on open."""
    return _get_state().conversations.load(session_id)


@app.post("/conversation/{session_id}/clear")
def conversation_clear(session_id: str) -> dict[str, bool]:
    """Start a fresh chat: wipe the saved turns and drop the seeded agent."""
    state = _get_state()
    state.conversations.clear(session_id)
    agent = state.sessions.pop(session_id, None)
    if agent is not None:
        _broker.drop(session_id)
        _close_agent(agent)
    return {"ok": True}


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
