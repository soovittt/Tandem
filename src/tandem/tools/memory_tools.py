"""Tools that let the model read and write long-term memory."""

from __future__ import annotations

from typing import Any

from tandem.domain.memory import MemoryRecord
from tandem.domain.tool import ToolResult
from tandem.memory.base import MemoryStore
from tandem.tools.base import Tool

_KINDS = ["observation", "interpretation", "decision", "fact", "note"]


class RememberTool(Tool):
    """Persist something worth keeping across sessions."""

    name = "remember"
    description = (
        "Save a durable piece of information to long-term memory so it can be "
        "recalled in future sessions. Use for facts, decisions, observations, and "
        "working interpretations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The thing to remember."},
            "kind": {
                "type": "string",
                "enum": _KINDS,
                "description": "What sort of memory this is.",
            },
        },
        "required": ["content"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, **kwargs: Any) -> ToolResult:
        content = kwargs["content"]
        kind = kwargs.get("kind", "note")
        self._store.add(MemoryRecord(content=content, kind=kind))
        return ToolResult(content=f"Remembered ({kind}): {content}")


class RecallTool(Tool):
    """Search memory for anything relevant to the current work."""

    name = "recall"
    description = (
        "Search long-term memory for relevant past facts, decisions, and "
        "observations before answering."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
        },
        "required": ["query"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, **kwargs: Any) -> ToolResult:
        hits = self._store.search(kwargs["query"])
        if not hits:
            return ToolResult(content="No relevant memories found.")
        lines = [f"- ({h.kind}) {h.content}" for h in hits]
        return ToolResult(content="Relevant memories:\n" + "\n".join(lines))
