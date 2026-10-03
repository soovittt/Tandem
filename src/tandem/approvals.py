"""
Human-in-the-loop approval over HTTP.

A consequential tool (send a message, create an event, run a shortcut, drive an
app) must not run until the user says yes. The agent runs inside a long-lived
/chat request; when it hits such a tool, `BrokeredApproval.approve()` registers a
pending request and BLOCKS that request's worker thread on an Event. Meanwhile the
client polls GET /pending/{session} and POSTs /approve/{session}; that resolves the
Event and the agent continues (or skips the action).

Safety: every pending action carries a unique `id`. An approval is only honored if
its id matches the CURRENTLY pending action — so a stale card (for a previous or
different action) can never authorize the wrong thing.

Thread model: FastAPI runs sync endpoints in a worker pool, so blocking one worker
while others serve /pending and /approve is fine. All shared state is lock-guarded.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from tandem.domain.message import ToolCall
from tandem.tools.base import Tool


@dataclass
class PendingApproval:
    tool: str
    arguments: dict[str, Any]
    description: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class _SessionState:
    pending: PendingApproval | None = None
    decision: bool | None = None
    event: threading.Event = field(default_factory=threading.Event)


class ApprovalBroker:
    """Mediates approval between the blocked agent thread and the client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, _SessionState] = {}

    def request(self, session_id: str, approval: PendingApproval, *, timeout: float = 150.0) -> bool:
        """Block until the client approves/denies THIS action, or deny on timeout."""
        with self._lock:
            state = self._states.setdefault(session_id, _SessionState())
            state.pending = approval
            state.decision = None
            state.event.clear()
            event = state.event

        granted = event.wait(timeout)

        with self._lock:
            state = self._states.get(session_id)
            decision = bool(state.decision) if (granted and state) else False
            if state:
                state.pending = None
                state.decision = None
        return decision

    def pending(self, session_id: str) -> PendingApproval | None:
        with self._lock:
            state = self._states.get(session_id)
            return state.pending if state else None

    def resolve(self, session_id: str, approval_id: str, approved: bool) -> bool:
        """Honor a decision only if it targets the currently pending action."""
        with self._lock:
            state = self._states.get(session_id)
            if state is not None and state.pending is not None and state.pending.id == approval_id:
                state.decision = approved
                state.event.set()
                return True
        return False  # stale/mismatched id — ignored (the real action still waits)

    def drop(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)


class BrokeredApproval:
    """ApprovalPolicy that routes consequential tool calls through the broker."""

    def __init__(self, session_id: str, broker: ApprovalBroker) -> None:
        self._session_id = session_id
        self._broker = broker

    def approve(self, call: ToolCall, tool: Tool) -> bool:
        return self._broker.request(
            self._session_id,
            PendingApproval(tool=call.name, arguments=call.arguments, description=_describe(call, tool)),
        )


def _describe(call: ToolCall, tool: Tool) -> str:
    """A clean, human-readable summary for the approval card -- NOT the raw
    function call. Shows what the action will do plus its key details."""
    detail = _humanize_args(call.arguments)
    return f"{tool.description}\n\n{detail}" if detail else tool.description


# Argument keys that are noise on an approval card (routing/paging, not content).
_HIDDEN_ARG_KEYS = frozenset({"operation", "action", "limit", "offset"})


def _humanize_args(arguments: dict[str, Any]) -> str:
    """Render arguments as readable 'Label: value' lines, skipping empties and
    internal routing keys. No code syntax."""
    lines: list[str] = []
    for key, value in arguments.items():
        if key in _HIDDEN_ARG_KEYS or value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").replace("Date", " date").strip().capitalize()
        lines.append(f"{label}: {value}")
    return "\n".join(lines)
