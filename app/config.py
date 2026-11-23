"""Application configuration, loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> Path:
    path = Path(os.getenv(name) or default)
    return path if path.is_absolute() else BASE_DIR / path


@dataclass(frozen=True)
class Config:
    database_path: Path
    upload_dir: Path
    sample_docs_dir: Path = BASE_DIR / "sample_docs"
    max_upload_mb: int = 10
    seed_sample_docs: bool = True

    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k: int = 4
    min_score: float = 0.10
    history_turns: int = 4

    llm_provider: str = "demo"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout: int = 60

    embedding_provider: str = "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = ""
    embedding_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(BASE_DIR / ".env")
        return cls(
            database_path=_path("DATABASE_PATH", "data/app.db"),
            upload_dir=_path("UPLOAD_DIR", "data/uploads"),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
            seed_sample_docs=_bool("SEED_SAMPLE_DOCS", True),
            chunk_size=int(os.getenv("CHUNK_SIZE", "600")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            top_k=int(os.getenv("TOP_K", "4")),
            min_score=float(os.getenv("MIN_SCORE", "0.10")),
            history_turns=int(os.getenv("HISTORY_TURNS", "4")),
            llm_provider=os.getenv("LLM_PROVIDER", "demo").lower(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", ""),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
        )
