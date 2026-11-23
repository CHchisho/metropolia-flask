"""Application factory: wires configuration, storage, RAG pipeline, LLM and routes together."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from .api.routes import api
from .config import Config
from .db import Database
from .errors import AppError
from .llm.factory import build_llm
from .rag.embeddings import build_embedder
from .rag.retriever import Retriever
from .repositories import ChunkRepository, ConversationRepository, DocumentRepository
from .services.chat_service import ChatService
from .services.document_service import DocumentService

log = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = (config.max_upload_mb + 1) * 1024 * 1024  # headroom for multipart overhead

    db = Database(config.database_path)
    db.init_schema()
    documents, chunks, conversations = DocumentRepository(db), ChunkRepository(db), ConversationRepository(db)
    embedder = build_embedder(config)
    llm = build_llm(config)

    app.extensions["config"] = config
    app.extensions["embedder"] = embedder
    app.extensions["llm"] = llm
    app.extensions["document_service"] = DocumentService(config, documents, chunks, embedder)
    app.extensions["chat_service"] = ChatService(
        conversations, Retriever(embedder, chunks, config.top_k, config.min_score), llm, config.history_turns
    )

    app.register_blueprint(api)
    _register_error_handlers(app)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    if config.seed_sample_docs:
        seeded = app.extensions["document_service"].seed_samples()
        if seeded:
            log.info("Loaded %d sample documents", seeded)
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return jsonify(error={"code": err.code, "message": err.message}), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        message = "The uploaded file is too large." if err.code == 413 else err.description
        return jsonify(error={"code": (err.name or "error").lower().replace(" ", "_"), "message": message}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        log.exception("Unhandled error")
        return jsonify(error={"code": "internal_error", "message": "Something went wrong on the server."}), 500
