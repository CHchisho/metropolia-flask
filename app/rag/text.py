"""Shared tokenisation used by the offline embedder and the demo LLM."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from how i if in is it its my of on or so
    that the their there this to was we what when where which who whom why will with you your
    about after also any been before can could did get has have into more most not should than
    then these they those up us very would many much long time times need make tell please""".split()
)


def stem(word: str) -> str:
    """Very light suffix stripping ("retakes"/"retaking" -> "retak"); enough for matching, not linguistics."""
    if len(word) <= 3 or word.isdigit():
        return word
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith(("sses", "xes", "ches", "shes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 4 else word

def tokenize(text: str) -> list[str]:
    """Lowercase, drop stopwords, stem."""
    return [stem(w) for w in _TOKEN.findall(text.lower()) if w not in STOPWORDS]
