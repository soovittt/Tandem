"""
Human-in-the-loop approval for consequential actions.

Some tools (sending a message, changing a system) must not run without a human's
okay. A tool declares `requires_approval = True`; the agent asks an ApprovalPolicy
before running it. The policy is swappable: auto-approve in tests, ask on the
console in the CLI, or (later) push a confirmation to the web UI.
"""

from __future__ import annotations

from typing import Protocol

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
