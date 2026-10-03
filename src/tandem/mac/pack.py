"""
The native Mac system-control tool pack.

System tools (frontmost app, open / minimize / hide app, run Shortcut) — no MCP
server covers these, so they're always on. The Apple apps (Calendar, Notes,
Messages, Reminders, Mail, Contacts) are handled by apple-mcp, not here.

To add a system tool: add it in apps/system.py (its tools() is picked up here).
"""

from __future__ import annotations

from tandem.mac.apps import system
from tandem.tools.base import Tool


def mac_system_tools() -> list[Tool]:
    return system.tools()
