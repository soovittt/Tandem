"""
Mem0-backed memory: a proper AI memory layer behind our MemoryStore interface.

Mem0 does what plain SQLite can't: it embeds memories for SEMANTIC recall (find
by meaning, not keywords), auto-extracts and updates facts, and keys everything by
user_id (our private-per-person vs team split later).

Privacy: we run the OPEN-SOURCE Mem0 fully self-hosted --
  - LLM (fact extraction) -> our own Nemotron via the OpenAI-compatible endpoint
  - embedder             -> a LOCAL HuggingFace model (text never leaves the box)
  - vector store         -> a LOCAL Chroma directory (our disk, our control)

Because this file implements the exact same add/search/all as SQLiteMemoryStore,
nothing else in the app changes when we switch to it -- that's the whole point of
depending on the MemoryStore protocol.

`mem0ai` is a heavy optional dependency (it pulls chromadb + a local embedder), so
we import it lazily: the app runs on SQLite with no Mem0 installed until you opt in
(`uv sync --extra mem0` and MEMORY_BACKEND=mem0).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tandem.config import LLMConfig
from tandem.domain.memory import MemoryRecord


class Mem0Store:
    """Implements MemoryStore on top of a self-hosted Mem0 instance."""

    def __init__(
        self,
        *,
        llm: LLMConfig,
        storage_dir: Path,
        user_id: str = "default",
        embedder_model: str = "multi-qa-MiniLM-L6-cos-v1",
    ) -> None:
        try:
            from mem0 import Memory
        except ImportError as exc:  # keep the dependency optional
            raise RuntimeError(
                "The Mem0 memory backend needs `mem0ai`. Install it with "
                "`uv sync --extra mem0`, or set MEMORY_BACKEND=sqlite."
            ) from exc

        storage_dir.mkdir(parents=True, exist_ok=True)
        self._user_id = user_id
        self._memory = Memory.from_config(
            {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": llm.model,
                        "openai_base_url": llm.base_url,
                        "api_key": llm.api_key,
                    },
                },
                "embedder": {
                    "provider": "huggingface",
                    "config": {"model": embedder_model},
                },
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": "tandem_memory",
                        "path": str(storage_dir / "chroma"),
                    },
                },
            }
        )

    def add(self, record: MemoryRecord) -> MemoryRecord:
        result = self._memory.add(
            record.content, user_id=self._user_id, metadata={"kind": record.kind}
        )
        items = _items(result)
        if items:
            record.id = items[0].get("id")
        return record

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        result = self._memory.search(query, user_id=self._user_id, limit=limit)
        return [_to_record(item) for item in _items(result)]

    def all(self) -> list[MemoryRecord]:
        result = self._memory.get_all(user_id=self._user_id)
        return [_to_record(item) for item in _items(result)]


def _items(result: Any) -> list[dict[str, Any]]:
    """Mem0 sometimes returns {'results': [...]} and sometimes a bare list."""
    if isinstance(result, dict):
        return result.get("results", [])
    if isinstance(result, list):
        return result
    return []


def _to_record(item: dict[str, Any]) -> MemoryRecord:
    metadata = item.get("metadata") or {}
    return MemoryRecord(
        id=item.get("id"),
        content=item.get("memory", ""),
        kind=metadata.get("kind", "note"),
        created_at=item.get("created_at"),
    )
