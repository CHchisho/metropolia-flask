"""Data access layer. All SQL lives here."""
from __future__ import annotations

import json
import sqlite3

import numpy as np

from .db import Database
from .models import Conversation, Document, Message


def _document(row: sqlite3.Row) -> Document:
    return Document(**dict(row))


class DocumentRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(
        self, filename: str, stored_name: str, file_type: str, size_bytes: int, sha256: str, status: str
    ) -> Document:
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO documents (filename, stored_name, file_type, size_bytes, sha256, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (filename, stored_name, file_type, size_bytes, sha256, status),
            )
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _document(row)

    def get(self, document_id: int) -> Document | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return _document(row) if row else None

    def get_by_hash(self, sha256: str) -> Document | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
        return _document(row) if row else None

    def list(self) -> list[Document]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC, id DESC").fetchall()
        return [_document(r) for r in rows]

    def update_status(
        self, document_id: int, status: str, error: str | None = None, page_count: int = 0, chunk_count: int = 0
    ) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE documents SET status = ?, error = ?, page_count = ?, chunk_count = ? WHERE id = ?",
                (status, error, page_count, chunk_count, document_id),
            )

    def delete(self, document_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


class ChunkRepository:
    def __init__(self, db: Database):
        self._db = db

    def add_many(
        self,
        document_id: int,
        chunks: list[tuple[int | None, str]],
        vectors: np.ndarray,
        embedding_model: str,
    ) -> None:
        """Store chunks given as (page, text) together with their embedding vectors."""
        rows = [
            (document_id, i, page, text, vectors[i].astype(np.float32).tobytes(), embedding_model)
            for i, (page, text) in enumerate(chunks)
        ]
        with self._db.connection() as conn:
            conn.executemany(
                "INSERT INTO chunks (document_id, chunk_index, page, text, embedding, embedding_model) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

    def load_searchable(self, embedding_model: str) -> list[sqlite3.Row]:
        """Chunks of ready documents embedded with the given model."""
        with self._db.connection() as conn:
            return conn.execute(
                "SELECT c.id, c.document_id, d.filename, c.page, c.text, c.embedding "
                "FROM chunks c JOIN documents d ON d.id = c.document_id "
                "WHERE d.status = 'ready' AND c.embedding_model = ? "
                "ORDER BY c.id",
                (embedding_model,),
            ).fetchall()


class ConversationRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, title: str) -> Conversation:
        with self._db.connection() as conn:
            cur = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Conversation(**dict(row))

    def get(self, conversation_id: int) -> Conversation | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return Conversation(**dict(row)) if row else None

    def list(self) -> list[Conversation]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM conversations ORDER BY id DESC").fetchall()
        return [Conversation(**dict(r)) for r in rows]

    def delete(self, conversation_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def add_message(self, conversation_id: int, role: str, content: str, sources: list[dict] | None = None) -> Message:
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, sources) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, json.dumps(sources or [])),
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._message(row)

    def messages(self, conversation_id: int) -> list[Message]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)
            ).fetchall()
        return [self._message(r) for r in rows]

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        data = dict(row)
        data["sources"] = json.loads(data["sources"])
        return Message(**data)
