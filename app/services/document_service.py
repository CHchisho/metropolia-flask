"""Document upload and ingestion workflow."""
from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path, PurePath

from ..config import Config
from ..errors import AppError, ConflictError, NotFoundError, ProcessingError, ValidationError
from ..models import STATUS_FAILED, STATUS_PROCESSING, STATUS_READY, Document
from ..processing.chunker import chunk_passages
from ..processing.extractor import SUPPORTED_TYPES, extract_passages
from ..rag.embeddings import Embedder
from ..repositories import ChunkRepository, DocumentRepository

log = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        config: Config,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        embedder: Embedder,
    ):
        self._config = config
        self._documents = documents
        self._chunks = chunks
        self._embedder = embedder
        config.upload_dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[Document]:
        return self._documents.list()

    def get(self, document_id: int) -> Document:
        document = self._documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    def upload(self, filename: str, data: bytes) -> Document:
        """Validate, store and index a file.

        Validation problems raise before anything is saved. Processing problems (e.g. an
        unreadable PDF) are recorded on the document as status=failed so the user can see why.
        """
        name = PurePath(filename.replace("\\", "/")).name.strip()
        file_type = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if not name:
            raise ValidationError("A file name is required.")
        if file_type not in SUPPORTED_TYPES:
            raise ValidationError("Unsupported file type. Please upload a PDF or TXT file.")
        if not data:
            raise ValidationError("The file is empty.")
        if len(data) > self._config.max_upload_mb * 1024 * 1024:
            raise ValidationError(f"The file is larger than {self._config.max_upload_mb} MB.")
        if file_type == "pdf" and not data.startswith(b"%PDF"):
            raise ValidationError("The file is not a valid PDF.")

        digest = hashlib.sha256(data).hexdigest()
        existing = self._documents.get_by_hash(digest)
        if existing:
            raise ConflictError(f'This file was already uploaded as "{existing.filename}".')

        stored_name = f"{uuid.uuid4().hex}.{file_type}"
        path = self._config.upload_dir / stored_name
        path.write_bytes(data)
        document = self._documents.create(name[:200], stored_name, file_type, len(data), digest, STATUS_PROCESSING)
        return self._index(document, path)

    def delete(self, document_id: int) -> None:
        document = self.get(document_id)
        self._documents.delete(document.id)  # chunks are removed by ON DELETE CASCADE
        (self._config.upload_dir / document.stored_name).unlink(missing_ok=True)

    def seed_samples(self) -> int:
        """Load bundled sample documents into an empty library."""
        if self._documents.list() or not self._config.sample_docs_dir.exists():
            return 0
        count = 0
        for path in sorted(self._config.sample_docs_dir.iterdir()):
            if path.suffix.lower().lstrip(".") in SUPPORTED_TYPES:
                try:
                    self.upload(path.name, path.read_bytes())
                    count += 1
                except AppError:
                    log.exception("Could not load sample document %s", path.name)
        return count

    def _index(self, document: Document, path: Path) -> Document:
        try:
            passages = extract_passages(path, document.file_type)
            chunks = chunk_passages(passages, self._config.chunk_size, self._config.chunk_overlap)
            vectors = self._embedder.embed([text for _, text in chunks])
            self._chunks.add_many(document.id, chunks, vectors, self._embedder.name)
            self._documents.update_status(document.id, STATUS_READY, page_count=len(passages), chunk_count=len(chunks))
        except AppError as exc:
            log.warning("Processing %s failed: %s", document.filename, exc.message)
            self._documents.update_status(document.id, STATUS_FAILED, error=exc.message)
        except Exception:
            log.exception("Unexpected error while processing %s", document.filename)
            self._documents.update_status(document.id, STATUS_FAILED, error="Unexpected processing error.")
        return self.get(document.id)
