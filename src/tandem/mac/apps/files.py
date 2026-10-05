"""Local file search (Spotlight / mdfind) and reading — fully on-device."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from tandem.domain.tool import ToolResult
from tandem.tools.base import Tool

# Junk paths that pollute Spotlight results — dependency caches, system libs, etc.
_NOISE = (
    "/node_modules/", "/site-packages/", "/.venv", "/.cache/", "/Library/",
    "/.git/", "/__pycache__/", "/.Trash/", "/.npm/", "/go/pkg/", "/dist/",
)


def _mdfind(args: list[str]) -> list[str]:
    try:
        proc = subprocess.run(["mdfind", *args], capture_output=True, text=True, timeout=20)
    except Exception:  # noqa: BLE001
        return []
    return [p for p in proc.stdout.splitlines() if p.strip() and not any(n in p for n in _NOISE)]


class FindFilesTool(Tool):
    name = "find_files"
    description = (
        "Find files on the Mac with Spotlight. Searches FILENAMES first (what people "
        "usually mean by 'find the file named X'); if nothing matches by name, falls back "
        "to searching file CONTENTS. Returns matching paths — use before read_file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Filename words, or a phrase to find in file contents."},
            "name_only": {
                "type": "boolean",
                "description": "Only match filenames; never fall back to a contents search.",
            },
        },
        "required": ["query"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return ToolResult(content="Give me something to search for.")
        # Filenames first — that's what "find the file named X" means.
        paths = _mdfind(["-name", query])
        header = ""
        if not paths and not kwargs.get("name_only"):
            paths = _mdfind([query])  # fall back to contents/metadata
            header = f"No files are named '{query}', but these mention it in their contents:\n"
        if not paths:
            return ToolResult(content=f"No files found named '{query}'.")
        shown = paths[:20]
        extra = f"\n…and {len(paths) - 20} more." if len(paths) > 20 else ""
        return ToolResult(content=header + "\n".join(shown) + extra)


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the text contents of a file by its path, so you can summarize it or answer "
        "questions about it. Pair with find_files to locate the path first."
    )
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute or ~ path to the file."}},
        "required": ["path"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip().strip("\"'")
        if not raw:
            return ToolResult(content="Give me a file path to read.")
        path = Path(raw).expanduser()
        if not path.exists():
            return ToolResult(content=f"No file at {path}.")
        if path.is_dir():
            return ToolResult(content=f"{path} is a folder, not a file.")
        try:
            data = path.read_text(errors="replace")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(content=f"Couldn't read {path}: {exc}")
        if len(data) > 12000:
            data = data[:12000] + f"\n…(truncated; {len(data)} chars total)"
        return ToolResult(content=data or "(empty file)")


def tools() -> list[Tool]:
    return [FindFilesTool(), ReadFileTool()]
