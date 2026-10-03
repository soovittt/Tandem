"""
SQLite-backed memory with full-text search (FTS5).

Why SQLite: it's embedded (no server), it's a single file we fully control (good
for the privacy story), and its FTS5 extension gives real keyword search for free.
A `memories` table holds the rows; a mirrored `memories_fts` virtual table,
kept in sync by triggers, provides ranked search. Swapping in vector search later
means adding another implementation of MemoryStore -- nothing else changes.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tandem.domain.memory import MemoryRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
    USING fts5(content, content='memories', content_rowid='id');

-- Keep the FTS index in lockstep with the base table.
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content)
        VALUES ('delete', old.id, old.content);
END;
"""


class SQLiteMemoryStore:
    """Implements MemoryStore on a local SQLite file."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def add(self, record: MemoryRecord) -> MemoryRecord:
        created_at = record.created_at or datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO memories (kind, content, created_at) VALUES (?, ?, ?)",
            (record.kind, record.content, created_at),
        )
        self._conn.commit()
        record.id = cursor.lastrowid
        record.created_at = created_at
        return record

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        match = _to_fts_query(query)
        if not match:
            return []
        rows = self._conn.execute(
            """
            SELECT m.id, m.kind, m.content, m.created_at
            FROM memories_fts f
            JOIN memories m ON m.id = f.rowid
            WHERE memories_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, limit),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def all(self) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT id, kind, content, created_at FROM memories ORDER BY id DESC"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def _to_fts_query(query: str) -> str:
    """
    Turn free text into a safe FTS5 query. We quote each word so punctuation in
    user input can't break FTS5 syntax, and OR them so any term can match.
    """
    terms = [f'"{word}"' for word in query.split() if word]
    return " OR ".join(terms)


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        kind=row["kind"],
        content=row["content"],
        created_at=row["created_at"],
    )
