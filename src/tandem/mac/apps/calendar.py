"""Calendar.app control via AppleScript."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


class ListTodayEventsTool(Tool):
    name = "mac_calendar_today"
    description = "List today's events from Calendar.app."
    parameters = {"type": "object", "properties": {}}

    def run(self, **kwargs: Any) -> ToolResult:
        script = """
        set output to ""
        tell application "Calendar"
            set todayStart to current date
            set hours of todayStart to 0
            set minutes of todayStart to 0
            set seconds of todayStart to 0
            set todayEnd to todayStart + (1 * days)
            repeat with cal in calendars
                set evs to (every event of cal whose start date is greater than or equal to todayStart and start date is less than todayEnd)
                repeat with e in evs
                    set output to output & (summary of e) & " @ " & (start date of e as string) & linefeed
                end repeat
            end repeat
        end tell
        return output
        """
        ok, out = run_applescript(script, timeout=40)
        if not ok:
            return ToolResult(content=f"Error: {out}")
        return ToolResult(content=out or "No events today.")


class CreateEventTool(Tool):
    name = "mac_calendar_create"
    description = "Create a Calendar event today. Provide title and start/end times (24h, e.g. '14:30')."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "Start time HH:MM (24h), today."},
            "end": {"type": "string", "description": "End time HH:MM (24h), today."},
        },
        "required": ["title", "start", "end"],
    }
    requires_approval = True

    def run(self, **kwargs: Any) -> ToolResult:
        title = as_applescript_string(kwargs["title"])
        try:
            sh, sm = (int(x) for x in kwargs["start"].split(":"))
            eh, em = (int(x) for x in kwargs["end"].split(":"))
        except ValueError:
            return ToolResult(content="Times must be HH:MM (24h).")
        script = f"""
        tell application "Calendar"
            set d1 to current date
            set hours of d1 to {sh}
            set minutes of d1 to {sm}
            set seconds of d1 to 0
            set d2 to current date
            set hours of d2 to {eh}
            set minutes of d2 to {em}
            set seconds of d2 to 0
            tell calendar 1
                make new event with properties {{summary:{title}, start date:d1, end date:d2}}
            end tell
        end tell
        return "created"
        """
        ok, out = run_applescript(script)
        return ToolResult(content=f"Created event '{kwargs['title']}'." if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [ListTodayEventsTool(), CreateEventTool()]
