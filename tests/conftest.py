import io

import pytest

from app import create_app
from app.config import Config


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        database_path=tmp_path / "test.db",
        upload_dir=tmp_path / "uploads",
        seed_sample_docs=False,
        max_upload_mb=1,
    )


@pytest.fixture
def app(config):
    return create_app(config)


@pytest.fixture
def client(app):
    return app.test_client()


def upload(client, name: str, data: bytes):
    return client.post("/api/documents", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")


@pytest.fixture
def upload_file(client):
    return lambda name, data: upload(client, name, data)
