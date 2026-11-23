from __future__ import annotations

from typing import Protocol

from ..models import ChatTurn, RetrievedChunk


class LLMProvider(Protocol):
    """Anything that can answer a question from retrieved context.

    Passages are numbered 1..n in the order given; answers cite them as [1], [2], ...
    """

    name: str

    def answer(self, question: str, passages: list[RetrievedChunk], history: list[ChatTurn]) -> str: ...
