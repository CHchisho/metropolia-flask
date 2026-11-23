from app import create_app

from .pdf_factory import make_pdf

TXT = b"The library is open from 8:00 to 20:00. Printing costs five cents per page."


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True


def test_upload_txt_becomes_ready(upload_file, client):
    resp = upload_file("library.txt", TXT)
    assert resp.status_code == 201
    doc = resp.get_json()["document"]
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    assert doc["filename"] == "library.txt"
    assert "stored_name" not in doc  # internal detail is not exposed
    assert client.get("/api/documents").get_json()["documents"][0]["id"] == doc["id"]


def test_upload_pdf_records_pages(upload_file):
    doc = upload_file("guide.pdf", make_pdf(["Page one text here.", "Page two text here."])).get_json()["document"]
    assert doc["status"] == "ready"
    assert doc["page_count"] == 2


def test_upload_rejects_unsupported_type(upload_file):
    resp = upload_file("malware.exe", b"data")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_upload_rejects_empty_file(upload_file):
    assert upload_file("empty.txt", b"").status_code == 400


def test_upload_rejects_fake_pdf(upload_file):
    assert upload_file("fake.pdf", b"just text").status_code == 400


def test_upload_rejects_oversized_file(upload_file):
    resp = upload_file("big.txt", b"a" * (2 * 1024 * 1024))
    assert resp.status_code == 413
    assert "too large" in resp.get_json()["error"]["message"]


def test_upload_without_file_field(client):
    resp = client.post("/api/documents", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_duplicate_upload_conflicts(upload_file):
    assert upload_file("a.txt", TXT).status_code == 201
    resp = upload_file("copy.txt", TXT)
    assert resp.status_code == 409
    assert "already uploaded" in resp.get_json()["error"]["message"]


def test_unreadable_document_is_saved_as_failed(upload_file):
    resp = upload_file("blank.txt", b"   \n\n  ")
    assert resp.status_code == 201
    doc = resp.get_json()["document"]
    assert doc["status"] == "failed"
    assert "No extractable text" in doc["error"]


def test_path_components_are_stripped_from_filename(upload_file):
    doc = upload_file("../../etc/notes.txt", TXT).get_json()["document"]
    assert doc["filename"] == "notes.txt"


def test_delete_document_removes_file_and_chunks(upload_file, client, config):
    doc = upload_file("a.txt", TXT).get_json()["document"]
    assert len(list(config.upload_dir.iterdir())) == 1
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert list(config.upload_dir.iterdir()) == []
    assert client.get(f"/api/documents/{doc['id']}").status_code == 404
    answer = client.post("/api/chat", json={"message": "library hours"}).get_json()["message"]
    assert answer["sources"] == []


def test_delete_missing_document(client):
    assert client.delete("/api/documents/999").status_code == 404


def test_unknown_api_route_returns_json_404(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_sample_documents_are_seeded_once(config):
    from dataclasses import replace

    seeded = replace(config, seed_sample_docs=True)
    docs = create_app(seeded).test_client().get("/api/documents").get_json()["documents"]
    assert len(docs) >= 5
    assert all(d["status"] == "ready" for d in docs)
    again = create_app(seeded).test_client().get("/api/documents").get_json()["documents"]
    assert len(again) == len(docs)
