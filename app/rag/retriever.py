"""Similarity search over stored chunk embeddings."""
from __future__ import annotations

import numpy as np

from ..models import RetrievedChunk
from ..repositories import ChunkRepository
from .embeddings import Embedder


class Retriever:
    """Brute-force cosine search.

    Vectors are loaded per query. For a few thousand chunks this takes milliseconds and avoids
    cache invalidation; a vector index (FAISS, sqlite-vec) would be the next step at larger scale.
    """

    def __init__(self, embedder: Embedder, chunks: ChunkRepository, top_k: int, min_score: float):
        self._embedder = embedder
        self._chunks = chunks
        self._top_k = top_k
        self._min_score = min_score

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        rows = self._chunks.load_searchable(self._embedder.name)
        if not rows:
            return []

        matrix = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        query_vector = self._embedder.embed([query])[0]
        scores = matrix @ query_vector  # vectors are unit length, so this is cosine similarity

        best = np.argsort(scores)[::-1][: self._top_k]
        return [
            RetrievedChunk(
                chunk_id=rows[i]["id"],
                document_id=rows[i]["document_id"],
                filename=rows[i]["filename"],
                page=rows[i]["page"],
                text=rows[i]["text"],
                score=float(scores[i]),
            )
            for i in best
            if scores[i] >= self._min_score
        ]
