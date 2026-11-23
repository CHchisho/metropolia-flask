"""Embedding providers. `Embedder` is the interface the rest of the app depends on."""
from __future__ import annotations

import zlib
from typing import Protocol

import numpy as np
import requests

from ..config import Config
from ..errors import ProviderError
from .text import tokenize


class Embedder(Protocol):
    name: str  # stored with each chunk so vectors from different models are never mixed

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalised vectors."""
        ...


class HashingEmbedder:
    """Offline bag-of-words embedder using the hashing trick (unigrams + bigrams).

    It captures lexical overlap, not semantics, but needs no model download or API key,
    so the app works out of the box. Swap in `OpenAIEmbedder` for semantic search.
    """

    def __init__(self, dim: int = 4096):
        self.dim = dim
        self.name = f"local-hashing-{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = tokenize(text)
            # Bigrams add some word-order signal but count for less than the words themselves.
            features = [(t, 1.0) for t in tokens] + [(f"{a} {b}", 0.5) for a, b in zip(tokens, tokens[1:])]
            for feature, weight in features:
                h = zlib.crc32(feature.encode("utf-8"))
                sign = 1.0 if (h >> 31) & 1 else -1.0  # signed hashing reduces collision bias
                matrix[row, h % self.dim] += sign * weight
            # Sublinear term-frequency damping, then normalise.
            matrix[row] = np.sign(matrix[row]) * np.log1p(np.abs(matrix[row]))
        return _normalize(matrix)


class OpenAIEmbedder:
    """Embeddings from any OpenAI-compatible `/embeddings` endpoint."""

    BATCH_SIZE = 64

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60):
        self._url = base_url.rstrip("/") + "/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._model = model
        self._timeout = timeout
        self.name = f"openai-{model}"

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]
            try:
                resp = requests.post(
                    self._url,
                    json={"model": self._model, "input": batch},
                    headers=self._headers,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = sorted(resp.json()["data"], key=lambda item: item["index"])
            except (requests.RequestException, KeyError, ValueError) as exc:
                raise ProviderError(f"Embedding request failed: {exc}") from exc
            vectors.extend(item["embedding"] for item in data)
        return _normalize(np.asarray(vectors, dtype=np.float32))


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def build_embedder(config: Config) -> Embedder:
    if config.embedding_provider == "local":
        return HashingEmbedder()
    if config.embedding_provider == "openai":
        return OpenAIEmbedder(
            base_url=config.embedding_base_url or config.llm_base_url,
            api_key=config.embedding_api_key or config.llm_api_key,
            model=config.embedding_model,
            timeout=config.llm_timeout,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {config.embedding_provider!r}")
