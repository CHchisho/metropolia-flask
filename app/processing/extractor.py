"""Turn uploaded files into text passages."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from ..errors import ProcessingError
from ..models import Passage

SUPPORTED_TYPES = {"pdf", "txt"}


def extract_passages(path: Path, file_type: str) -> list[Passage]:
    """Return non-empty passages; PDFs yield one passage per page so citations can cite page numbers."""
    if file_type == "txt":
        passages = _extract_txt(path)
    elif file_type == "pdf":
        passages = _extract_pdf(path)
    else:
        raise ProcessingError(f"Unsupported file type: {file_type}")

    if not passages:
        raise ProcessingError(
            "No extractable text found. Scanned PDFs need OCR, which this app does not do."
        )
    return passages


def _extract_txt(path: Path) -> list[Passage]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 rarely fails, latin-1 never does
        text = raw.decode("latin-1")
    text = text.strip()
    return [Passage(text=text)] if text else []


def _extract_pdf(path: Path) -> list[Passage]:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ProcessingError("Password-protected PDFs are not supported.")
        pages = [(i + 1, (page.extract_text() or "").strip()) for i, page in enumerate(reader.pages)]
    except ProcessingError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError) as exc:
        raise ProcessingError(f"The PDF could not be read: {exc}") from exc
    return [Passage(text=text, page=number) for number, text in pages if text]
