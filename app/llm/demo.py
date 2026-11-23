"""Offline provider: builds an extractive answer from the best-matching sentences.

No generation happens, so it cannot hallucinate, but it also cannot paraphrase or reason.
It exists so the whole pipeline is usable (and testable) without any API credentials.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..models import ChatTurn, RetrievedChunk
from ..rag.text import tokenize

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")
MAX_SENTENCES = 4
RELATIVE_CUTOFF = 0.5  # keep sentences scoring at least half as well as the best one


class DemoProvider:
    name = "demo"

    def answer(self, question: str, passages: list[RetrievedChunk], history: list[ChatTurn]) -> str:
        query_terms = set(tokenize(question))

        sentences: list[tuple[int, int, str, set[str]]] = []  # (passage no., position, text, terms)
        for number, passage in enumerate(passages, start=1):
            for position, sentence in enumerate(_SENTENCE_SPLIT.split(passage.text)):
                sentence = sentence.strip()
                terms = set(tokenize(sentence))
                if len(sentence) >= 25 and terms:
                    sentences.append((number, position, sentence, terms))

        # Rare terms matter more: weight by inverse sentence frequency within the retrieved context.
        frequency = Counter(term for *_, terms in sentences for term in terms)
        weight = {term: math.log(1 + len(sentences) / count) for term, count in frequency.items()}

        scored = [
            (sum(weight[t] for t in query_terms & terms), number, position, sentence)
            for number, position, sentence, terms in sentences
            if query_terms & terms
        ]
        if not scored:
            return f"I found a related section but no direct answer. The closest text is: {passages[0].text[:300]} [1]"

        scored.sort(key=lambda s: s[0], reverse=True)
        best = [s for s in scored[:MAX_SENTENCES] if s[0] >= scored[0][0] * RELATIVE_CUTOFF]
        best.sort(key=lambda s: (s[1], s[2]))  # read in document order
        lines = [f"- {sentence} [{number}]" for _, number, _, sentence in best]
        return "Here is what the documents say:\n\n" + "\n".join(lines)
