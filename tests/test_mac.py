"""
Tests for the native Mac-control layer (macOS only).

Covers the safety-critical escaping, the osascript runner, the system tool pack
wiring, and that consequential actions are approval-gated. Does NOT drive real apps
(that needs user-granted permissions and is non-deterministic).

Run:  uv run python tests/test_mac.py
"""

from __future__ import annotations

from tandem.mac.apps.system import RunShortcutTool
from tandem.mac.osascript import as_applescript_string, run_applescript
from tandem.mac.pack import mac_system_tools


def test_applescript_escaping() -> None:
    assert as_applescript_string('a"b') == '"a\\"b"'
    assert as_applescript_string("a\\b") == '"a\\\\b"'


def test_osascript_runs() -> None:
    ok, out = run_applescript('return "pong"')
    assert ok and out == "pong"


def test_system_tools_and_approval() -> None:
    names = {t.name for t in mac_system_tools()}
    for expected in {
        "mac_frontmost_app",
        "mac_open_app",
        "mac_minimize_window",
        "mac_hide_app",
        "mac_run_shortcut",
    }:
        assert expected in names, f"missing {expected}"
    # Running an arbitrary Shortcut is consequential → must require approval.
    assert RunShortcutTool().requires_approval is True


if __name__ == "__main__":
    test_applescript_escaping()
    test_osascript_runs()
    test_system_tools_and_approval()
    print("OK — mac escaping, osascript runner, system tool pack, and approval gating verified.")
