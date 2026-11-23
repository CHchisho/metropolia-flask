# Documentation

## Using a real LLM

Demo mode (the default) embeds text locally and quotes the best-matching sentences. For generated answers, set these in `.env`:

```ini
# OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai          # optional: semantic search instead of keyword matching
```

```ini
# Ollama (free, local): ollama pull llama3.1
LLM_PROVIDER=openai
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

Chunks are stored with the name of the model that embedded them, and search only uses the current model. After changing the embedding settings, delete `data/` (samples are re-seeded on an empty database) or re-upload your files.

## Configuration

Read from the environment and `.env`. Defaults live in [`.env.example`](.env.example).

| Variable                                   | Default                       | Meaning                                                                                                   |
| ------------------------------------------ | ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| `LLM_PROVIDER`                             | `demo`                        | `demo` or `openai` (any OpenAI-compatible `/chat/completions`)                                            |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | OpenAI                        | Chat endpoint. `LLM_TIMEOUT` defaults to 60s                                                              |
| `EMBEDDING_PROVIDER`                       | `local`                       | `local` (hashing embedder) or `openai`                                                                    |
| `EMBEDDING_MODEL`                          | `text-embedding-3-small`      | Used with the OpenAI embedder. `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` fall back to the `LLM_*` values |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`              | `600`, `100`                  | Characters per chunk, and how much is repeated in the next one                                            |
| `TOP_K`, `MIN_SCORE`                       | `4`, `0.10`                   | How many passages reach the model, and the minimum cosine similarity                                      |
| `HISTORY_TURNS`                            | `4`                           | Earlier exchanges sent with a follow-up                                                                   |
| `MAX_UPLOAD_MB`                            | `10`                          | Upload limit                                                                                              |
| `SEED_SAMPLE_DOCS`                         | `true`                        | Index `sample_docs/` when the library is empty                                                            |
| `DATABASE_PATH`, `UPLOAD_DIR`              | `data/app.db`, `data/uploads` | Storage                                                                                                   |
| `HOST`, `PORT`                             | `127.0.0.1`, `5000`           | Dev server                                                                                                |

## Architecture

```
Browser (ES modules, no build)
        │  JSON
app/api/routes.py          validate input, call a service
   ├─ services/document_service.py   upload → extract → chunk → embed → store
   └─ services/chat_service.py       retrieve → LLM → save the turn
            ├─ rag/      embeddings, cosine search
            ├─ llm/      LLMProvider: demo.py or openai_compatible.py
            └─ processing/   PDF/TXT extraction, chunking
repositories.py → db.py (SQLite)
```

`app/__init__.py` is the factory that wires this together. `config.py` loads settings, `errors.py` maps domain errors to JSON, `models.py` holds the dataclasses passed between layers. Services do not import Flask, so they are testable on their own.

### Pipeline

1. **Extract.** TXT is decoded as UTF-8, then cp1252. PDFs are read page by page with `pypdf`, so a citation can name the page. A scanned PDF has no text and is marked failed.
2. **Chunk.** Paragraphs are packed into ~600-character chunks with overlap. A chunk never crosses a page.
3. **Embed.** `Embedder` is a small interface. `HashingEmbedder` is a deterministic bag-of-words embedder (stemmed words, hashing, normalised). `OpenAIEmbedder` calls `/embeddings`.
4. **Store.** Chunk text and float32 vectors go into SQLite with the embedding model name.
5. **Retrieve.** The query is embedded and ranked by cosine similarity (one NumPy product) over chunks of `ready` documents. Results below `MIN_SCORE` are dropped.
6. **Answer.** The provider receives numbered passages and is asked to cite them as `[n]`. When retrieval finds nothing, the model is not called.

### Decisions

- **Vanilla JS, not React.** Three screens do not justify a Node toolchain. Output from the model is escaped before it is rendered.
- **Two interfaces, and only those.** `LLMProvider` and `Embedder` each have two implementations behind a factory. Adding another provider is one class plus one branch.
- **Indexing happens inside the upload request.** A document takes well under a second with the local embedder. The status field is already there if a background worker is needed later.
- **Search is brute force.** Exact and fast up to tens of thousands of chunks; a vector index would only replace the inside of `Retriever`.
- **A turn is saved after the model answers**, so a provider failure leaves no half-written conversation.

### Limits

- Demo mode matches words, not meaning: "plagiarize" will not find "plagiarism". An embedding model fixes this.
- The demo answer quotes sentences. It does not summarise or reason, and it cannot invent facts.
- Single user: no login and no per-user libraries.
- No OCR, and PDF tables are flattened to text.

## API

Everything is under `/api`. Errors look like `{"error": {"code": "...", "message": "..."}}`.

|                                                 |                                        |     |
| ----------------------------------------------- | -------------------------------------- | --- |
| `GET /health`                                   | active model and embedder              | 200 |
| `GET /documents`, `GET /documents/<id>`         | list or one document                   | 200 |
| `POST /documents`                               | upload, field name `file`              | 201 |
| `DELETE /documents/<id>`                        | removes the file and its chunks        | 204 |
| `POST /chat`                                    | `{"message", "conversation_id": null}` | 200 |
| `GET /conversations`, `GET /conversations/<id>` | list, or one with its messages         | 200 |
| `DELETE /conversations/<id>`                    |                                        | 204 |

`400` bad input, `404` missing, `409` duplicate file, `413` too large, `502` the model or embedder failed.

```bash
curl -s localhost:5000/api/chat -H "Content-Type: application/json" \
  -d '{"message": "What are the library opening hours?"}'

curl -s -F "file=@my_notes.pdf" localhost:5000/api/documents
```

## Tests

`python -m pytest` (50+, no network): chunking and extraction, ranking and score thresholds, upload validation, chat with sources, conversation history, and the OpenAI provider with HTTP mocked.

Screenshots: with the app running, `pip install -r requirements-dev.txt && python -m scripts.screenshots`. Rebuild the sample PDF with `python -m scripts.make_sample_pdf`.
