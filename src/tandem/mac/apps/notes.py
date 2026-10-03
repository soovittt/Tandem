"""Notes.app control via AppleScript."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


class CreateNoteTool(Tool):
    name = "mac_notes_create"
    description = "Create a note in Notes.app with a title and body."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["title", "body"],
    }
    requires_approval = True

    def run(self, **kwargs: Any) -> ToolResult:
        # Notes treats the first line as the title; combine into HTML-ish body.
        combined = as_applescript_string(f"{kwargs['title']}\n{kwargs['body']}")
        ok, out = run_applescript(
            f'tell application "Notes" to make new note at folder "Notes" with properties {{body:{combined}}}'
        )
        return ToolResult(content=f"Created note '{kwargs['title']}'." if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [CreateNoteTool()]
