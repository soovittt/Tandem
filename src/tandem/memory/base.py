"""The memory store interface (repository pattern)."""

from __future__ import annotations

from typing import Protocol

from tandem.domain.memory import MemoryRecord


class MemoryStore(Protocol):
    """
    Persists and retrieves memories. The agent depends on this protocol, so the
    storage engine (SQLite now, a vector DB later) is an implementation detail.
    """

    def add(self, record: MemoryRecord) -> MemoryRecord:
        """Persist a record; return it with id + created_at filled in."""
        ...

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        """Return the most relevant memories for a query, best first."""
        ...

    def all(self) -> list[MemoryRecord]:
        """Return every memory, newest first (for a memory panel / audit)."""
        ...
