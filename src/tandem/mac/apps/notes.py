"""Native Apple Notes: create (in the user's default folder) + search, via AppleScript.

Replaces apple-mcp's `notes` tool, which требует exact args (it errors with an
unhelpful "Invalid arguments" when the model omits `body`, then the model thrashes)
and files every note into a separate "Claude" folder instead of the main one.
"""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class CreateNoteTool(Tool):
    name = "create_note"
    description = (
        "Create a note in Apple Notes (saved to the user's default Notes folder). Pass a "
        "title and the note's content. Use this whenever the user asks to make/create/jot "
        "a note."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The note's title."},
            "body": {"type": "string", "description": "The note's content (what goes inside it)."},
        },
        "required": ["title"],
    }
    requires_approval = True  # consequential write

    def run(self, **kwargs: Any) -> ToolResult:
        title = str(kwargs.get("title", "")).strip()
        body = str(kwargs.get("body", "")).strip()
        if not title and not body:
            return ToolResult(content="Give me a title or some content for the note.")
        if not title:
            title = body.splitlines()[0][:40]
        # The Notes body is HTML; its first line becomes the displayed title.
        html = "<div><b>" + _html_escape(title) + "</b></div>"
        for line in body.splitlines():
            html += "<div>" + _html_escape(line) + "</div>"
        script = (
            'tell application "Notes" to make new note with properties '
            f"{{name:{as_applescript_string(title)}, body:{as_applescript_string(html)}}}"
        )
        ok, out = run_applescript(script)
        return ToolResult(content=f'Created the note "{title}" in your Notes app.' if ok else f"Error: {out}")


class SearchNotesTool(Tool):
    name = "search_notes"
    description = "Search Apple Notes by words in the title or content. Returns matching note titles."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Words to look for in your notes."}},
        "required": ["query"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return ToolResult(content="What should I search your notes for?")
        q = as_applescript_string(query)
        script = (
            'tell application "Notes"\n'
            '  set out to ""\n'
            f"  repeat with n in (notes whose name contains {q} or body contains {q})\n"
            '    set out to out & "• " & (name of n) & linefeed\n'
            "  end repeat\n"
            "  return out\n"
            "end tell"
        )
        ok, out = run_applescript(script, timeout=20)
        if not ok:
            return ToolResult(content=f"Error: {out}")
        return ToolResult(content=out.strip() or f"No notes found matching '{query}'.")


def tools() -> list[Tool]:
    return [CreateNoteTool(), SearchNotesTool()]
