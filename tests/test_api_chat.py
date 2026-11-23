import pytest
import requests

from app.errors import ProviderError
from app.llm.openai_compatible import OpenAICompatibleProvider, build_messages
from app.models import ChatTurn, RetrievedChunk

EXAMS = (
    b"Students have three attempts per course: the original exam and two retakes.\n\n"
    b"Bring a valid photo ID to every exam."
)
LIBRARY = b"The library is open from 8:00 to 20:00 on weekdays. Printing costs five cents per page."


@pytest.fixture
def loaded(upload_file):
    upload_file("exams.txt", EXAMS)
    upload_file("library.txt", LIBRARY)


def ask(client, message, conversation_id=None):
    body = {"message": message}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    return client.post("/api/chat", json=body)


def test_answer_includes_sources_with_excerpts(client, loaded):
    resp = ask(client, "How many retakes do I get for an exam?")
    assert resp.status_code == 200
    message = resp.get_json()["message"]
    assert message["role"] == "assistant"
    source = message["sources"][0]
    assert source["filename"] == "exams.txt"
    assert "retakes" in source["excerpt"]
    assert source["index"] == 1


def test_unrelated_question_has_no_sources(client, loaded):
    message = ask(client, "What is the capital of France?").get_json()["message"]
    assert message["sources"] == []
    assert "couldn't find" in message["content"]


def test_conversation_is_persisted_and_continued(client, loaded):
    first = ask(client, "What are the library hours?").get_json()
    conversation_id = first["conversation"]["id"]
    ask(client, "How much does printing cost?", conversation_id)

    body = client.get(f"/api/conversations/{conversation_id}").get_json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert client.get("/api/conversations").get_json()["conversations"][0]["id"] == conversation_id

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": 42},
        {"message": "hi", "conversation_id": "1"},
        {"message": "hi", "conversation_id": True},
        {"message": "x" * 2001},
    ],
)
def test_invalid_chat_payloads_are_rejected(client, payload):
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_non_json_body_is_rejected(client):
    assert client.post("/api/chat", data="hello", content_type="text/plain").status_code == 400


def test_unknown_conversation_returns_404(client):
    assert ask(client, "hello", conversation_id=12345).status_code == 404


def test_provider_failure_returns_502_and_saves_nothing(app, client, loaded):
    class Broken:
        name = "broken"

        def answer(self, *args, **kwargs):
            raise ProviderError("model offline")

    app.extensions["chat_service"]._llm = Broken()
    resp = ask(client, "How many retakes do I get for an exam?")
    assert resp.status_code == 502
    assert resp.get_json()["error"]["message"] == "model offline"
    assert client.get("/api/conversations").get_json()["conversations"] == []


# --- LLM provider ------------------------------------------------------------

PASSAGE = RetrievedChunk(1, 1, "exams.txt", 3, "Two retakes are allowed.", 0.9)


def test_prompt_contains_numbered_context_history_and_question():
    messages = build_messages("How many retakes?", [PASSAGE], [ChatTurn("user", "hi"), ChatTurn("assistant", "hello")])
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert "[1] (exams.txt, page 3)" in messages[-1]["content"]
    assert "Question: How many retakes?" in messages[-1]["content"]


def test_openai_provider_parses_response(monkeypatch):
    captured = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": " Two retakes [1]. "}}]}

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers)
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OpenAICompatibleProvider("http://llm.local/v1/", "secret", "test-model")
    assert provider.answer("q", [PASSAGE], []) == "Two retakes [1]."
    assert captured["url"] == "http://llm.local/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "test-model"


def test_openai_provider_wraps_network_errors(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", fail)
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider("http://llm.local/v1", "", "m").answer("q", [PASSAGE], [])


def test_openai_provider_rejects_malformed_response(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"unexpected": True}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp())
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider("http://llm.local/v1", "", "m").answer("q", [PASSAGE], [])
