"""
Human-in-the-loop approval for consequential actions.

A tool declares `requires_approval = True`; the agent asks an ApprovalPolicy before
running it. The policy is swappable:
  - AutoApprove — tests / non-interactive runs.
  - ConsoleApproval — the CLI (ask on the terminal).
  - BrokeredApproval — the HTTP flow: block the agent's worker thread until the
    command bar approves/denies over /pending + /approve, mediated by ApprovalBroker.

Safety: every pending action carries a unique `id`. An approval is only honored if
its id matches the CURRENTLY pending action, so a stale card can never authorize the
wrong thing. FastAPI runs sync endpoints in a worker pool, so blocking one worker
while others serve /pending and /approve is fine; all shared state is lock-guarded.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from tandem.domain.message import ToolCall
from tandem.tools.base import Tool


class ApprovalPolicy(Protocol):
    """Decides whether a tool call that requires approval may proceed."""

    def approve(self, call: ToolCall, tool: Tool) -> bool: ...


class AutoApprove:
    """Approves everything. For tests and non-interactive runs."""

    def approve(self, call: ToolCall, tool: Tool) -> bool:  # noqa: ARG002
        return True


class ConsoleApproval:
    """Asks the user on the terminal before a consequential action runs."""

    def approve(self, call: ToolCall, tool: Tool) -> bool:  # noqa: ARG002
        print(f"\n[approval needed] {call.name}({call.arguments})")
        answer = input("Approve this action? [y/N] ").strip().lower()
        return answer in {"y", "yes"}


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

    # Argument keys that are noise on an approval card (routing/paging, not content).
    _HIDDEN_ARG_KEYS = frozenset({"operation", "action", "limit", "offset"})

    def __init__(self, session_id: str, broker: ApprovalBroker) -> None:
        self._session_id = session_id
        self._broker = broker

    def approve(self, call: ToolCall, tool: Tool) -> bool:
        return self._broker.request(
            self._session_id,
            PendingApproval(
                tool=call.name,
                arguments=call.arguments,
                description=self._describe(call, tool),
            ),
        )

    def _describe(self, call: ToolCall, tool: Tool) -> str:
        """A clean, human-readable summary for the approval card -- NOT the raw
        function call. Shows what the action will do plus its key details."""
        detail = self._humanize_args(call.arguments)
        return f"{tool.description}\n\n{detail}" if detail else tool.description

    def _humanize_args(self, arguments: dict[str, Any]) -> str:
        """Render arguments as readable 'Label: value' lines, skipping empties and
        internal routing keys. No code syntax."""
        lines: list[str] = []
        for key, value in arguments.items():
            if key in self._HIDDEN_ARG_KEYS or value in (None, "", [], {}):
                continue
            label = key.replace("_", " ").replace("Date", " date").strip().capitalize()
            lines.append(f"{label}: {value}")
        return "\n".join(lines)
