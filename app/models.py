"""Plain data objects shared between layers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


@dataclass
class Document:
    id: int
    filename: str
    stored_name: str
    file_type: str
    size_bytes: int
    sha256: str
    status: str
    error: str | None
    page_count: int
    chunk_count: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("stored_name")
        return data


@dataclass
class Passage:
    """A text span extracted from a document (one PDF page, or a whole TXT file)."""

    text: str
    page: int | None = None


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    page: int | None
    text: str
    score: float


@dataclass
class Source:
    """A citation shown below an answer. `index` matches the [n] markers in the text."""

    index: int
    document_id: int
    filename: str
    page: int | None
    excerpt: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    id: int
    conversation_id: int
    role: str
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Conversation:
    id: int
    title: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatTurn:
    """A prior message passed to the LLM as conversation context."""

    role: str
    content: str
