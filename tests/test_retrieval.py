import numpy as np
import pytest

from app.db import Database
from app.rag.embeddings import HashingEmbedder
from app.rag.retriever import Retriever
from app.rag.text import tokenize
from app.repositories import ChunkRepository, DocumentRepository


def test_tokenize_drops_stopwords_and_normalises_plurals():
    assert tokenize("What are the exams?") == tokenize("exam")
    assert tokenize("retaking exams") == tokenize("retake exam")


def test_embeddings_are_unit_length_and_deterministic():
    embedder = HashingEmbedder()
    first = embedder.embed(["library opening hours", "thesis deadline"])
    second = embedder.embed(["library opening hours", "thesis deadline"])
    assert first.shape == (2, embedder.dim)
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0)
    assert np.array_equal(first, second)


def test_embedding_of_empty_text_does_not_crash():
    assert not np.isnan(HashingEmbedder().embed(["", "the and of"])).any()


def test_similar_text_scores_higher_than_unrelated():
    embedder = HashingEmbedder()
    query, related, unrelated = embedder.embed(
        ["when does the library open", "The library opens at 8:00 on weekdays.", "Tuition fees for foreign students."]
    )
    assert query @ related > query @ unrelated


@pytest.fixture
def indexed(tmp_path):
    db = Database(tmp_path / "r.db")
    db.init_schema()
    documents, chunks = DocumentRepository(db), ChunkRepository(db)
    embedder = HashingEmbedder()
    texts = {
        "library.txt": ["The library is open from 8:00 to 20:00 on weekdays.", "Printing costs five cents per page."],
        "exams.txt": ["You may retake a failed exam twice.", "Bring photo identification to every exam."],
    }
    for name, parts in texts.items():
        doc = documents.create(name, name, "txt", 10, name, "processing")
        chunks.add_many(doc.id, [(None, p) for p in parts], embedder.embed(parts), embedder.name)
        documents.update_status(doc.id, "ready")
    return embedder, chunks, documents


def test_retriever_returns_most_relevant_chunk_first(indexed):
    embedder, chunks, _ = indexed
    results = Retriever(embedder, chunks, top_k=3, min_score=0.05).retrieve("How many times can I retake an exam?")
    assert results[0].filename == "exams.txt"
    assert "retake" in results[0].text
    assert results == sorted(results, key=lambda r: r.score, reverse=True)


def test_retriever_respects_top_k_and_min_score(indexed):
    embedder, chunks, _ = indexed
    assert len(Retriever(embedder, chunks, top_k=1, min_score=0.0).retrieve("exam")) == 1
    assert Retriever(embedder, chunks, top_k=3, min_score=0.5).retrieve("quantum physics") == []


def test_retriever_ignores_documents_that_are_not_ready(indexed):
    embedder, chunks, documents = indexed
    for doc in documents.list():
        documents.update_status(doc.id, "failed", error="x")
    assert Retriever(embedder, chunks, top_k=3, min_score=0.0).retrieve("library") == []


def test_retriever_ignores_vectors_from_other_embedding_models(indexed):
    _, chunks, _ = indexed
    other = HashingEmbedder(dim=128)
    assert Retriever(other, chunks, top_k=3, min_score=0.0).retrieve("library") == []


def test_retriever_on_empty_index(tmp_path):
    db = Database(tmp_path / "e.db")
    db.init_schema()
    assert Retriever(HashingEmbedder(), ChunkRepository(db), 3, 0.0).retrieve("anything") == []
