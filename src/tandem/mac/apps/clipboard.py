"""Clipboard read/write via pbpaste/pbcopy."""

from __future__ import annotations

import subprocess
from typing import Any

from tandem.domain.tool import ToolResult
from tandem.tools.base import Tool


class ReadClipboardTool(Tool):
    name = "read_clipboard"
    description = "Read the current contents of the Mac clipboard (what the user last copied)."
    parameters = {"type": "object", "properties": {}}

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            out = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout
        except Exception as exc:  # noqa: BLE001
            return ToolResult(content=f"Couldn't read the clipboard: {exc}")
        return ToolResult(content=out if out.strip() else "(clipboard is empty)")


class SetClipboardTool(Tool):
    name = "set_clipboard"
    description = "Copy text to the Mac clipboard so the user can paste it elsewhere."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The text to copy."}},
        "required": ["text"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        text = str(kwargs.get("text", ""))
        try:
            subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(content=f"Couldn't set the clipboard: {exc}")
        return ToolResult(content="Copied to the clipboard.")


def tools() -> list[Tool]:
    return [ReadClipboardTool(), SetClipboardTool()]
