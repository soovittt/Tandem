"""
Filesystem integration: read files under an approved directory.

The first real integration, and the model for the rest: it takes a permitted root
(e.g. a folder of instrument exports or procedures) and exposes read-only tools
scoped to it. Path traversal outside the root is refused -- the agent can only see
what it was granted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tandem.domain.tool import Source, ToolResult
from tandem.tools.base import Tool


class FilesystemIntegration:
    """Exposes list_files + read_file scoped to one approved root directory."""

    name = "filesystem"

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def tools(self) -> list[Tool]:
        return [ListFilesTool(self._root), ReadFileTool(self._root)]


def _safe_resolve(root: Path, relative: str) -> Path | None:
    """Resolve `relative` under `root`, or None if it escapes the root."""
    candidate = (root / relative).resolve()
    if root == candidate or root in candidate.parents:
        return candidate
    return None


class ListFilesTool(Tool):
    name = "list_files"
    description = "List files available in the approved data directory."
    parameters = {
        "type": "object",
        "properties": {
            "subpath": {"type": "string", "description": "Optional subfolder to list."}
        },
    }

    def __init__(self, root: Path) -> None:
        self._root = root

    def run(self, **kwargs: Any) -> ToolResult:
        target = _safe_resolve(self._root, kwargs.get("subpath", ""))
        if target is None or not target.exists():
            return ToolResult(content="Path not found or not permitted.")
        names = sorted(p.relative_to(self._root).as_posix() for p in target.rglob("*") if p.is_file())
        return ToolResult(content="\n".join(names) if names else "(no files)")


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a text file from the approved data directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to the data dir."}
        },
        "required": ["path"],
    }

    def __init__(self, root: Path) -> None:
        self._root = root

    def run(self, **kwargs: Any) -> ToolResult:
        target = _safe_resolve(self._root, kwargs["path"])
        if target is None or not target.is_file():
            return ToolResult(content="File not found or not permitted.")
        try:
            text = target.read_text(errors="replace")
        except OSError as exc:
            return ToolResult(content=f"Could not read file: {exc}")
        source = Source(title=target.name, url=target.as_uri())
        return ToolResult(content=text[:20_000], sources=[source])
