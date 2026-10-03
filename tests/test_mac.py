"""
Tests for the native Mac-control layer (macOS only).

Covers the safety-critical escaping, the osascript runner, the tool pack wiring,
and that consequential actions are approval-gated. Does NOT drive real apps (that
needs user-granted permissions and is non-deterministic).

Run:  uv run python tests/test_mac.py
"""

from __future__ import annotations

from tandem.mac.apps.messages import SendMessageTool
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.mac.pack import mac_tool_pack


def test_applescript_escaping() -> None:
    assert as_applescript_string('a"b') == '"a\\"b"'
    assert as_applescript_string("a\\b") == '"a\\\\b"'


def test_osascript_runs() -> None:
    ok, out = run_applescript('return "pong"')
    assert ok and out == "pong"


def test_tool_pack_and_approval() -> None:
    names = {t.name for t in mac_tool_pack()}
    for expected in {"mac_frontmost_app", "mac_calendar_today", "mac_reminders_create", "mac_messages_send"}:
        assert expected in names, f"missing {expected}"
    # Sending a message is consequential → must require approval.
    assert SendMessageTool().requires_approval is True


if __name__ == "__main__":
    test_applescript_escaping()
    test_osascript_runs()
    test_tool_pack_and_approval()
    print("OK — mac escaping, osascript runner, tool pack, and approval gating verified.")
