"""Reminders.app control via AppleScript."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


class ListRemindersTool(Tool):
    name = "mac_reminders_list"
    description = "List open (incomplete) reminders from Reminders.app."
    parameters = {"type": "object", "properties": {}}

    def run(self, **kwargs: Any) -> ToolResult:
        script = """
        set output to ""
        tell application "Reminders"
            repeat with r in (every reminder whose completed is false)
                set output to output & (name of r) & linefeed
            end repeat
        end tell
        return output
        """
        ok, out = run_applescript(script, timeout=40)
        if not ok:
            return ToolResult(content=f"Error: {out}")
        return ToolResult(content=out or "No open reminders.")


class CreateReminderTool(Tool):
    name = "mac_reminders_create"
    description = "Create a reminder in Reminders.app."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The reminder text."}},
        "required": ["text"],
    }
    requires_approval = True

    def run(self, **kwargs: Any) -> ToolResult:
        text = as_applescript_string(kwargs["text"])
        ok, out = run_applescript(
            f'tell application "Reminders" to make new reminder with properties {{name:{text}}}'
        )
        return ToolResult(content=f"Added reminder: {kwargs['text']}" if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [ListRemindersTool(), CreateReminderTool()]
