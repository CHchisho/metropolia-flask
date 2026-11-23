"""Split passages into overlapping chunks suitable for embedding."""
from __future__ import annotations

import re

from ..models import Passage

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_passages(passages: list[Passage], chunk_size: int, overlap: int) -> list[tuple[int | None, str]]:
    """Return (page, text) chunks.

    Chunks never cross passage (page) boundaries, so every chunk maps to one citable page.
    Paragraphs are kept whole where possible; oversized ones fall back to sentences.
    """
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be in [0, chunk_size)")

    chunks: list[tuple[int | None, str]] = []
    for passage in passages:
        units = _units(passage.text, chunk_size)
        chunks.extend((passage.page, text) for text in _pack(units, chunk_size, overlap))
    return chunks


def _units(text: str, chunk_size: int) -> list[str]:
    units: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            units.extend(_hard_split(sentence, chunk_size))
    return units


def _hard_split(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _pack(units: list[str], chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    carried = 0  # leading units in `current` that are only overlap from the previous chunk
    length = 0
    for unit in units:
        if current and length + len(unit) + 1 > chunk_size:
            chunks.append("\n".join(current))
            current = _tail(current, overlap)
            carried = len(current)
            length = sum(len(u) + 1 for u in current)
        current.append(unit)
        length += len(unit) + 1
    if len(current) > carried:
        chunks.append("\n".join(current))
    return chunks


def _tail(units: list[str], overlap: int) -> list[str]:
    """Trailing units that fit in `overlap` characters, carried into the next chunk."""
    tail: list[str] = []
    total = 0
    for unit in reversed(units):
        if total + len(unit) > overlap:
            break
        tail.insert(0, unit)
        total += len(unit)
    return tail
