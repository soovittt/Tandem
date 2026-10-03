"""System-level Mac control: what's focused, launching apps, running Shortcuts."""

from __future__ import annotations

import subprocess
from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.tools.base import Tool


class FrontmostAppTool(Tool):
    name = "mac_frontmost_app"
    description = "Get the name of the app the user is currently focused on."
    parameters = {"type": "object", "properties": {}}

    def run(self, **kwargs: Any) -> ToolResult:
        ok, out = run_applescript(
            'tell application "System Events" to get name of first application process whose frontmost is true'
        )
        return ToolResult(content=out if ok else f"Error: {out}")


class OpenAppTool(Tool):
    name = "mac_open_app"
    description = "Open or switch to a Mac application by name (e.g. 'Safari', 'Notes')."
    parameters = {
        "type": "object",
        "properties": {"app": {"type": "string", "description": "App name."}},
        "required": ["app"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        app = as_applescript_string(kwargs["app"])
        ok, out = run_applescript(f"tell application {app} to activate")
        return ToolResult(content=f"Opened {kwargs['app']}." if ok else f"Error: {out}")


class RunShortcutTool(Tool):
    name = "mac_run_shortcut"
    description = "Run a macOS Shortcut by name (from the Shortcuts app). Optional text input."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Shortcut name."},
            "input": {"type": "string", "description": "Optional text input."},
        },
        "required": ["name"],
    }
    requires_approval = True  # a shortcut can do anything

    def run(self, **kwargs: Any) -> ToolResult:
        cmd = ["shortcuts", "run", kwargs["name"]]
        text = kwargs.get("input")
        try:
            proc = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return ToolResult(content=f"Error running shortcut: {exc}")
        if proc.returncode != 0:
            return ToolResult(content=f"Shortcut failed: {proc.stderr.strip()}")
        return ToolResult(content=proc.stdout.strip() or f"Ran shortcut '{kwargs['name']}'.")


def _resolve_process(app: str) -> str | None:
    """Map a user-given app name to an actual running process name
    ('Chrome' -> 'Google Chrome'). Returns None if nothing plausible is running.
    macOS process names are exact, so the model saying "Chrome" would otherwise fail."""
    ok, out = run_applescript(
        'tell application "System Events" to get name of every application process '
        "whose background only is false"
    )
    if not ok:
        return None
    names = [n.strip() for n in out.split(",") if n.strip()]
    low = app.strip().lower()
    for n in names:  # exact, case-insensitive
        if n.lower() == low:
            return n
    for n in names:  # substring either direction ("Chrome" <-> "Google Chrome")
        if low in n.lower() or n.lower() in low:
            return n
    return None


def _act_on_process(app: str, make_script: Any) -> tuple[bool, str, str]:
    """Run an AppleScript targeting `app`'s process, trying the given name directly
    first (the common exact-name fast path, one osascript call) and only resolving
    the real process name ("Chrome" -> "Google Chrome") if that first call fails.
    Returns (ok, output, label)."""
    ok, out = run_applescript(make_script(as_applescript_string(app)))
    if ok:
        return True, out, app
    proc = _resolve_process(app)
    if proc is None:
        return False, f"'{app}' doesn't appear to be running.", app
    if proc != app:  # a different real name — retry once with it
        ok, out = run_applescript(make_script(as_applescript_string(proc)))
    return ok, out, proc


class MinimizeWindowTool(Tool):
    name = "mac_minimize_window"
    description = "Minimize the front window of an app (or the frontmost app if 'app' is omitted)."
    parameters = {
        "type": "object",
        "properties": {"app": {"type": "string", "description": "App name; omit for the frontmost app."}},
    }

    def run(self, **kwargs: Any) -> ToolResult:
        app = kwargs.get("app")
        if not app:
            ok, out = run_applescript(
                'tell application "System Events"\n'
                "  set p to first application process whose frontmost is true\n"
                '  set value of attribute "AXMinimized" of window 1 of p to true\n'
                "end tell"
            )
            return ToolResult(content="Minimized the front window." if ok else f"Error: {out}")
        ok, out, proc = _act_on_process(
            app,
            lambda t: f'tell application "System Events" to tell process {t} '
            'to set value of attribute "AXMinimized" of window 1 to true',
        )
        return ToolResult(content=f"Minimized {proc}." if ok else f"Error: {out}")


class HideAppTool(Tool):
    name = "mac_hide_app"
    description = "Hide an application's windows (like pressing Command-H)."
    parameters = {
        "type": "object",
        "properties": {"app": {"type": "string", "description": "App name to hide."}},
        "required": ["app"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        ok, out, proc = _act_on_process(
            kwargs["app"],
            lambda t: f'tell application "System Events" to set visible of process {t} to false',
        )
        return ToolResult(content=f"Hid {proc}." if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [
        FrontmostAppTool(),
        OpenAppTool(),
        MinimizeWindowTool(),
        HideAppTool(),
        RunShortcutTool(),
    ]
