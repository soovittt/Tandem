"""Music playback control for Spotify and Apple Music via AppleScript."""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript, running_app_names
from tandem.tools.base import Tool

_PLAYERS = ["Spotify", "Music"]  # preference order when both are open


def _pick_player() -> str | None:
    running = running_app_names()
    for player in _PLAYERS:
        if player in running:
            return player
    return None


class MusicControlTool(Tool):
    name = "music_control"
    description = (
        "Control music playback in Spotify or Apple Music: play, pause, skip to the next "
        "or previous track, or report what's currently playing."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play", "pause", "next", "previous", "current"],
                "description": "What to do.",
            }
        },
        "required": ["action"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "")).strip().lower()
        player = _pick_player()
        if player is None:
            if action == "play":
                run_applescript('tell application "Spotify" to activate')
                player = "Spotify"
            else:
                return ToolResult(content="Neither Spotify nor Apple Music is open.")
        a = as_applescript_string(player)
        if action == "current":
            ok, out = run_applescript(
                f'tell application {a} to (get name of current track) & " — " & (get artist of current track)'
            )
            return ToolResult(content=f"Now playing in {player}: {out}" if ok else f"Nothing playing ({out}).")
        verbs = {"play": "play", "pause": "pause", "next": "next track", "previous": "previous track"}
        verb = verbs.get(action)
        if verb is None:
            return ToolResult(content=f"Unknown action '{action}'.")
        ok, out = run_applescript(f"tell application {a} to {verb}")
        labels = {
            "play": "Playing",
            "pause": "Paused",
            "next": "Skipped to the next track",
            "previous": "Back to the previous track",
        }
        return ToolResult(content=f"{labels[action]} in {player}." if ok else f"Error: {out}")


def tools() -> list[Tool]:
    return [MusicControlTool()]
