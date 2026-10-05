"""
The native Mac control tool pack.

These are the local, AppleScript/CLI-backed tools that no MCP server covers
cleanly — always on, zero-install, fully on-device:
  - system: frontmost / open / minimize / hide app, run Shortcut, volume, dark mode
  - browser: read the active tab, open a URL, list tabs (Safari + Chrome family)
  - files: Spotlight search + read a file by path
  - media: Spotify / Apple Music playback control
  - clipboard: read / set the clipboard

The Apple apps (Calendar, Notes, Messages, Reminders, Mail, Contacts, Maps) and
WhatsApp come from MCP servers (see mcp_servers.py), not here.

To add a native tool: add it in the right apps/*.py module (its tools() is picked
up here); to add a whole new app surface, add a module and one line below.
"""

from __future__ import annotations

from tandem.mac.apps import browser, clipboard, files, media, notes, system
from tandem.tools.base import Tool

_MODULES = [system, browser, files, media, clipboard, notes]


def mac_system_tools() -> list[Tool]:
    return [tool for module in _MODULES for tool in module.tools()]
