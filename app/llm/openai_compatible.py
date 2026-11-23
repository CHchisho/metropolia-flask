"""Provider for any OpenAI-compatible `/chat/completions` API (OpenAI, Ollama, LM Studio, vLLM...)."""
from __future__ import annotations

import requests

from ..errors import ProviderError
from ..models import ChatTurn, RetrievedChunk

SYSTEM_PROMPT = (
    "You are an assistant that answers questions about university documents. "
    "Answer ONLY from the numbered context passages provided. "
    "Cite the passages you use with markers like [1] or [2]. "
    "If the context does not contain the answer, say so plainly instead of guessing. "
    "Be concise and use short lists when helpful."
)


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._model = model
        self._timeout = timeout
        self.name = f"openai-compatible:{model}"

    def answer(self, question: str, passages: list[RetrievedChunk], history: list[ChatTurn]) -> str:
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": build_messages(question, passages, history),
        }
        try:
            resp = requests.post(self._url, json=payload, headers=self._headers, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except requests.HTTPError as exc:
            detail = exc.response.text[:200] if exc.response is not None else ""
            raise ProviderError(f"The language model returned an error ({exc.response.status_code}): {detail}") from exc
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"The language model could not be reached or returned bad data: {exc}") from exc


def build_messages(question: str, passages: list[RetrievedChunk], history: list[ChatTurn]) -> list[dict[str, str]]:
    context = "\n\n".join(
        f"[{i}] ({p.filename}{f', page {p.page}' if p.page else ''})\n{p.text}" for i, p in enumerate(passages, 1)
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": t.role, "content": t.content} for t in history]
    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})
    return messages
