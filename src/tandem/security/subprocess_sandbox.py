"""
A minimal subprocess-based sandbox for local development.

WARNING: this is NOT strong isolation. It only pins the working directory, drops
`shell=True`, and enforces a timeout -- enough to develop against, but a
determined command could still misbehave. Real isolation is OpenShell (micro-VM
/ kernel-level). This class exists so the tool interface works today and so the
production swap is a one-line change in the composition root.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tandem.security.base import ExecResult


class SubprocessSandbox:
    """Runs a command as a subprocess confined to a working directory."""

    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir
        self._workdir.mkdir(parents=True, exist_ok=True)

    def run(self, command: list[str], *, timeout: float = 30.0) -> ExecResult:
        try:
            completed = subprocess.run(
                command,
                cwd=self._workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,  # never interpret a shell string
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(stdout="", stderr="Command timed out.", exit_code=124)
        except FileNotFoundError:
            return ExecResult(stdout="", stderr=f"Command not found: {command[0]}", exit_code=127)
        return ExecResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )
