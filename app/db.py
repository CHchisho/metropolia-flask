"""SQLite access: schema and a small connection helper."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    sha256      TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL,
    error       TEXT,
    page_count  INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    page            INTEGER,
    text            TEXT NOT NULL,
    embedding       BLOB NOT NULL,
    embedding_model TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    sources         TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""


class Database:
    """Opens a short-lived connection per unit of work (safe across Flask threads)."""

    def __init__(self, path: Path):
        self.path = path

    def init_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
