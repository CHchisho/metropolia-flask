"""HTTP routes. Thin: parse/validate input, call a service, serialise the result."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..errors import ValidationError
from ..services.chat_service import ChatService
from ..services.document_service import DocumentService

api = Blueprint("api", __name__, url_prefix="/api")


def _documents() -> DocumentService:
    return current_app.extensions["document_service"]


def _chat() -> ChatService:
    return current_app.extensions["chat_service"]


@api.get("/health")
def health():
    return jsonify(
        status="ok",
        llm=current_app.extensions["llm"].name,
        embeddings=current_app.extensions["embedder"].name,
        demo_mode=current_app.extensions["llm"].name == "demo",
    )


# --- documents -------------------------------------------------------------

@api.get("/documents")
def list_documents():
    return jsonify(documents=[d.to_dict() for d in _documents().list()])


@api.post("/documents")
def upload_document():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ValidationError('Send the file as multipart form data in the "file" field.')
    document = _documents().upload(upload.filename, upload.read())
    return jsonify(document=document.to_dict()), 201


@api.get("/documents/<int:document_id>")
def get_document(document_id: int):
    return jsonify(document=_documents().get(document_id).to_dict())


@api.delete("/documents/<int:document_id>")
def delete_document(document_id: int):
    _documents().delete(document_id)
    return "", 204


# --- chat ------------------------------------------------------------------

@api.post("/chat")
def chat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValidationError("Expected a JSON object body.")
    message = body.get("message")
    conversation_id = body.get("conversation_id")
    if not isinstance(message, str):
        raise ValidationError('"message" must be a string.')
    if conversation_id is not None and (not isinstance(conversation_id, int) or isinstance(conversation_id, bool)):
        raise ValidationError('"conversation_id" must be an integer.')

    result = _chat().ask(message, conversation_id)
    return jsonify(
        conversation=result.conversation.to_dict(),
        user_message=result.user_message.to_dict(),
        message=result.assistant_message.to_dict(),
    )


@api.get("/conversations")
def list_conversations():
    return jsonify(conversations=[c.to_dict() for c in _chat().list_conversations()])


@api.get("/conversations/<int:conversation_id>")
def get_conversation(conversation_id: int):
    chat = _chat()
    return jsonify(
        conversation=chat.get_conversation(conversation_id).to_dict(),
        messages=[m.to_dict() for m in chat.get_messages(conversation_id)],
    )


@api.delete("/conversations/<int:conversation_id>")
def delete_conversation(conversation_id: int):
    _chat().delete_conversation(conversation_id)
    return "", 204
