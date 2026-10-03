"""A tool that runs a shell command inside a sandbox (with human approval)."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.security.base import Sandbox
from tandem.tools.base import Tool


class RunCommandTool(Tool):
    """Run a command in the sandbox. Consequential, so it requires approval."""

    name = "run_command"
    description = (
        "Run a shell command in a sandboxed working directory and return its "
        "output. Use for computations, file processing, and scripts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The command and its args, e.g. ['python', 'plot.py'].",
            }
        },
        "required": ["command"],
    }
    requires_approval = True  # never run code without the human's okay

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def run(self, **kwargs: Any) -> ToolResult:
        command = kwargs["command"]
        if not isinstance(command, list) or not command:
            return ToolResult(content="Error: `command` must be a non-empty list.")
        result = self._sandbox.run(command)
        body = (
            f"exit_code={result.exit_code}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        return ToolResult(content=body)
