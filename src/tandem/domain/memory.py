"""The unit of long-term memory."""

from __future__ import annotations

from dataclasses import dataclass

# What kind of thing this memory is. Distinguishing these is central to the
# product: an observation is raw evidence; an interpretation can be wrong and
# revised; a decision/fact is something the team settled on.
MemoryKind = str  # "observation" | "interpretation" | "decision" | "fact" | "note"


@dataclass
class MemoryRecord:
    """One durable thing the assistant remembers across sessions."""

    content: str
    kind: MemoryKind = "note"
    id: str | int | None = None    # assigned by the store (int for SQLite, uuid for Mem0)
    created_at: str | None = None  # ISO timestamp, set by the store
