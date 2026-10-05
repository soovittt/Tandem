"""
Safe AppleScript execution — the foundation of native Mac app control.

Every native Mac tool goes through here. Two rules for code quality + safety:
  1. Never string-format untrusted values straight into a script — use
     `as_applescript_string()` so quotes/backslashes can't break out or inject.
  2. Always return (ok, output) so tools can surface errors to the model cleanly
     (including the macOS permission prompts the user must grant on first use).
"""

from __future__ import annotations

import subprocess


def as_applescript_string(value: str) -> str:
    """Quote a Python string as an AppleScript string literal, safely escaped."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def running_app_names() -> list[str]:
    """Names of all visible (non-background) application processes, e.g.
    ['Safari', 'Notes', 'Spotify']. Shared by tools that resolve an app by name."""
    ok, out = run_applescript(
        'tell application "System Events" to get name of every application process '
        "whose background only is false"
    )
    return [n.strip() for n in out.split(",") if n.strip()] if ok else []


def run_applescript(script: str, *, timeout: float = 25.0) -> tuple[bool, str]:
    """Run an AppleScript source string. Returns (ok, stdout_or_error)."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out."
    except FileNotFoundError:
        return False, "osascript not found — this isn't macOS."

    if result.returncode != 0:
        err = (result.stderr or "AppleScript error").strip()
        # Surface the common permission error in a way the model/user understands.
        if "not allowed" in err.lower() or "-1743" in err:
            err += " (grant Automation/Accessibility access in System Settings → Privacy.)"
        return False, err
    return True, result.stdout.strip()
