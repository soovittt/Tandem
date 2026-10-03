"""
Persistent conversation history.

Keeps each session's chat turns on disk so a conversation survives app restarts,
backend restarts, and agent eviction — the chat stays continuous instead of
resetting to one-shot Q&A. The agent seeds its context from here on build, and the
UI restores the visible thread.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class ConversationStore:
    """A local SQLite log of (session, role, text) turns."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: reached from different FastAPI worker threads; a
        # lock serializes access on the shared connection.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                text       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS turns_by_session ON turns(session_id, id)")
        self._conn.commit()

    def append(self, session_id: str, role: str, text: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO turns (session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, text, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def load(self, session_id: str, limit: int = 40) -> list[dict[str, str]]:
        """The last `limit` turns for a session, oldest-first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, text FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

    def list_sessions(self, limit: int = 60) -> list[dict[str, str]]:
        """All conversations, most-recent first: {session_id, title (first message),
        updated_at}. For the chat-history list."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT t.session_id, t.text AS title, g.updated_at
                FROM turns t
                JOIN (SELECT session_id, MAX(created_at) AS updated_at, MIN(id) AS first_id
                      FROM turns GROUP BY session_id) g
                  ON t.session_id = g.session_id AND t.id = g.first_id
                ORDER BY g.updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {"session_id": r["session_id"], "title": r["title"], "updated_at": r["updated_at"]}
            for r in rows
        ]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
