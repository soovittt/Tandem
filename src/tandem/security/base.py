"""The sandbox interface: where the agent is allowed to run commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExecResult:
    """The outcome of running a command in a sandbox."""

    stdout: str
    stderr: str
    exit_code: int


class Sandbox(Protocol):
    """
    Runs a command in a controlled environment.

    Our dev implementation (SubprocessSandbox) gives basic containment; the
    production implementation is NVIDIA OpenShell, which adds kernel-level
    isolation, a declarative policy, and credential brokering. Because both
    satisfy this protocol, swapping dev->prod is a composition-root change.
    """

    def run(self, command: list[str], *, timeout: float = 30.0) -> ExecResult: ...
