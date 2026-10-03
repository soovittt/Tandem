"""
The native Mac tool pack.

Split into:
  - system tools (frontmost app, open app, run Shortcut) — always useful; no MCP
    server covers them.
  - app tools (Calendar, Reminders, Notes, Messages) — a RELIABLE FALLBACK for the
    Apple apps. When apple-mcp is connected it owns those apps (richer coverage),
    so the composition root skips these to avoid redundant, confusing duplicates.

To add a new app: write `apps/<app>.py` exposing `tools() -> list[Tool]` and add
its module to the right list below.
"""

from __future__ import annotations

from tandem.mac.apps import calendar, messages, notes, reminders, system
from tandem.tools.base import Tool

_SYSTEM_MODULES = [system]
_APP_MODULES = [calendar, reminders, notes, messages]


def mac_system_tools() -> list[Tool]:
    tools: list[Tool] = []
    for module in _SYSTEM_MODULES:
        tools.extend(module.tools())
    return tools


def mac_app_tools() -> list[Tool]:
    tools: list[Tool] = []
    for module in _APP_MODULES:
        tools.extend(module.tools())
    return tools


def mac_tool_pack() -> list[Tool]:
    """All native Mac tools (system + app). Used when no MCP app server is active."""
    return mac_system_tools() + mac_app_tools()
