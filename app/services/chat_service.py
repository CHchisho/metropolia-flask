"""The RAG chat flow: retrieve -> generate -> persist."""
from __future__ import annotations

from dataclasses import dataclass

from ..errors import NotFoundError, ValidationError
from ..llm.base import LLMProvider
from ..models import ChatTurn, Conversation, Message, RetrievedChunk, Source
from ..rag.retriever import Retriever
from ..repositories import ConversationRepository

MAX_QUESTION_LENGTH = 2000
EXCERPT_LENGTH = 420
NO_ANSWER = (
    "I couldn't find anything about that in the uploaded documents. "
    "Try rephrasing the question, or upload a document that covers it."
)


@dataclass
class ChatResult:
    conversation: Conversation
    user_message: Message
    assistant_message: Message


class ChatService:
    def __init__(
        self, conversations: ConversationRepository, retriever: Retriever, llm: LLMProvider, history_turns: int
    ):
        self._conversations = conversations
        self._retriever = retriever
        self._llm = llm
        self._history_turns = history_turns

    def ask(self, question: str, conversation_id: int | None = None) -> ChatResult:
        question = (question or "").strip()
        if not question:
            raise ValidationError("Please enter a question.")
        if len(question) > MAX_QUESTION_LENGTH:
            raise ValidationError(f"The question is too long (max {MAX_QUESTION_LENGTH} characters).")

        if conversation_id is None:
            conversation = None
            history: list[ChatTurn] = []
        else:
            conversation = self.get_conversation(conversation_id)
            recent = self._conversations.messages(conversation.id)[-self._history_turns * 2 :]
            history = [ChatTurn(m.role, m.content) for m in recent]

        passages = self._retriever.retrieve(question)
        if passages:
            answer = self._llm.answer(question, passages, history)
            sources = [s.to_dict() for s in _to_sources(passages)]
        else:
            answer, sources = NO_ANSWER, []  # don't ask the LLM to answer without evidence

        # Persist only after generation succeeded, so a provider failure leaves no half-saved turn.
        if conversation is None:
            conversation = self._conversations.create(_title(question))
        user_message = self._conversations.add_message(conversation.id, "user", question)
        assistant_message = self._conversations.add_message(conversation.id, "assistant", answer, sources)
        return ChatResult(conversation, user_message, assistant_message)

    def list_conversations(self) -> list[Conversation]:
        return self._conversations.list()

    def get_conversation(self, conversation_id: int) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        return conversation

    def get_messages(self, conversation_id: int) -> list[Message]:
        self.get_conversation(conversation_id)
        return self._conversations.messages(conversation_id)

    def delete_conversation(self, conversation_id: int) -> None:
        self.get_conversation(conversation_id)
        self._conversations.delete(conversation_id)


def _title(question: str) -> str:
    return question if len(question) <= 60 else question[:57].rstrip() + "..."


def _to_sources(passages: list[RetrievedChunk]) -> list[Source]:
    return [
        Source(
            index=i,
            document_id=p.document_id,
            filename=p.filename,
            page=p.page,
            excerpt=p.text if len(p.text) <= EXCERPT_LENGTH else p.text[:EXCERPT_LENGTH].rstrip() + "…",
            score=round(p.score, 3),
        )
        for i, p in enumerate(passages, start=1)
    ]
