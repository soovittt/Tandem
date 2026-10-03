"""Messages.app (iMessage) control via AppleScript."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


class SendMessageTool(Tool):
    name = "mac_messages_send"
    description = "Send an iMessage/SMS to a phone number or Apple ID via Messages.app."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Phone number or email (Apple ID)."},
            "text": {"type": "string", "description": "Message body."},
        },
        "required": ["to", "text"],
    }
    requires_approval = True  # sending a message is consequential

    def run(self, **kwargs: Any) -> ToolResult:
        to = as_applescript_string(kwargs["to"])
        text = as_applescript_string(kwargs["text"])
        script = f"""
        tell application "Messages"
            set targetService to 1st account whose service type = iMessage
            set targetBuddy to participant {to} of targetService
            send {text} to targetBuddy
        end tell
        return "sent"
        """
        ok, out = run_applescript(script)
        return ToolResult(content=f"Sent message to {kwargs['to']}." if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [SendMessageTool()]
