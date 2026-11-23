import pytest

from app.errors import ProcessingError
from app.models import Passage
from app.processing.chunker import chunk_passages
from app.processing.extractor import extract_passages

from .pdf_factory import make_pdf


def test_chunks_respect_size_limit():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 30 for i in range(20))
    chunks = chunk_passages([Passage(text)], chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for _, chunk in chunks)


def test_chunks_cover_all_content():
    text = "\n\n".join(f"Unique marker {i} " + "filler " * 20 for i in range(15))
    joined = " ".join(chunk for _, chunk in chunk_passages([Passage(text)], 250, 40))
    assert all(f"Unique marker {i} " in joined for i in range(15))


def test_consecutive_chunks_overlap():
    sentences = [f"Sentence number {i} is here." for i in range(40)]
    chunks = [c for _, c in chunk_passages([Passage(" ".join(sentences))], chunk_size=200, overlap=60)]
    assert len(chunks) > 2
    last_of_first = chunks[0].split("\n")[-1]
    assert last_of_first in chunks[1]


def test_chunks_keep_page_numbers_and_do_not_cross_pages():
    passages = [Passage("First page text.", page=1), Passage("Second page text.", page=2)]
    assert chunk_passages(passages, 500, 50) == [(1, "First page text."), (2, "Second page text.")]


def test_oversized_sentence_is_hard_split():
    chunks = chunk_passages([Passage("x" * 1000)], chunk_size=300, overlap=0)
    assert [len(c) for _, c in chunks] == [300, 300, 300, 100]


def test_short_text_is_single_chunk_without_empty_tail():
    assert chunk_passages([Passage("Just one line.")], 500, 100) == [(None, "Just one line.")]


@pytest.mark.parametrize("size, overlap", [(0, 0), (100, 100), (100, -1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        chunk_passages([Passage("text")], size, overlap)


def test_extract_txt_handles_utf8_and_legacy_encodings(tmp_path):
    utf8 = tmp_path / "a.txt"
    utf8.write_text("Hyvää päivää", encoding="utf-8")
    legacy = tmp_path / "b.txt"
    legacy.write_bytes("Hyvää päivää".encode("cp1252"))
    assert extract_passages(utf8, "txt")[0].text == "Hyvää päivää"
    assert extract_passages(legacy, "txt")[0].text == "Hyvää päivää"


def test_extract_pdf_returns_one_passage_per_page(tmp_path):
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(["Alpha page content.", "Beta page content."]))
    passages = extract_passages(path, "pdf")
    assert [p.page for p in passages] == [1, 2]
    assert "Beta" in passages[1].text


def test_extract_empty_text_fails(tmp_path):
    path = tmp_path / "blank.txt"
    path.write_text("   \n  ")
    with pytest.raises(ProcessingError):
        extract_passages(path, "txt")


def test_extract_corrupt_pdf_fails(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(ProcessingError):
        extract_passages(path, "pdf")
