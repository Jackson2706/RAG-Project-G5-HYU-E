"""Test fixtures. No Docker, Ollama or internet needed:

- MongoDB → mongomock (an in-memory MongoDB imitation)
- Qdrant  → QdrantClient(":memory:")
- Sentence Transformers model → FakeModel: word-hash vectors (NOT semantic, only for tests)
- Ollama  → FakeOllama behind httpx.MockTransport
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil

import httpx
import mongomock
import numpy as np
import pytest
from qdrant_client import QdrantClient

from app.config import PROJECT_ROOT, Settings
from app.database import Database
from app.ollama import OllamaClient
from app.rag.pipeline import run_ingestion
from app.rag.registry import validate_config
from app.rag.schemas import Services

SAMPLES = PROJECT_ROOT / "data" / "samples"
WORD = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]")

# mongomock 4.3 is older than PyMongo 4.19, which passes an extra `sort` argument to bulk updates.
_add_update = mongomock.collection.BulkOperationBuilder.add_update
mongomock.collection.BulkOperationBuilder.add_update = lambda self, *a, sort=None, **kw: _add_update(self, *a, **kw)


class FakeTokenizer:
    """Splits text into words and punctuation, like a (much simpler) real tokenizer."""

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(m.start(), m.end()) for m in WORD.finditer(text)]}


class FakeModel:
    """Bag-of-words hash vectors: texts sharing words get similar vectors."""

    tokenizer = FakeTokenizer()
    dim = 64

    def get_embedding_dimension(self) -> int:
        return self.dim

    def encode(self, texts, **kwargs):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                out[row, hashlib.sha256(word.encode()).digest()[0] % self.dim] += 1.0
            out[row] /= np.linalg.norm(out[row]) or 1.0
        return out


class FakeOllama:
    """A pretend Ollama server. Change `answer`, `models` or `fail` inside a test."""

    def __init__(self) -> None:
        self.models = [{"name": "test-model", "details": {"parameter_size": "1B"}, "capabilities": ["completion"]}]
        self.answer = "Need-based scholarships require a household income certificate [E1]."
        self.fail: str | None = None  # "connect" or "500"
        self.requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail == "connect":
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": self.models})
        if request.url.path == "/api/chat":
            self.requests.append(json.loads(request.content))
            if self.fail == "500":
                return httpx.Response(500, json={"error": "model crashed"})
            words = self.answer.split(" ")
            lines = [json.dumps({"message": {"content": w + (" " if i < len(words) - 1 else "")}, "done": False}) for i, w in enumerate(words)]
            lines.append(json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}))
            return httpx.Response(200, content="\n".join(lines).encode())
        return httpx.Response(404)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    """Every test uses FakeModel instead of downloading BAAI/bge-small-en-v1.5."""
    model = FakeModel()
    monkeypatch.setattr("app.rag.blocks.embedding.load_sentence_transformer", lambda name, revision: model)
    return model


@pytest.fixture
def settings(tmp_path) -> Settings:
    (tmp_path / "data" / "raw").mkdir(parents=True)
    return Settings(data_dir=tmp_path / "data", ollama_chat_model="")


@pytest.fixture
def db() -> Database:
    database = Database(mongomock.MongoClient(tz_aware=True)["test"], QdrantClient(location=":memory:"), "test_chunks")
    database.create_indexes()
    return database


@pytest.fixture
def fake_ollama() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def ollama(fake_ollama) -> OllamaClient:
    return OllamaClient("http://ollama.test", transport=httpx.MockTransport(fake_ollama.handler))


@pytest.fixture
def services(db, ollama, settings) -> Services:
    return Services(db=db, ollama=ollama, settings=settings)


@pytest.fixture
def corpus(settings):
    """A copy of the five synthetic sample documents in a temporary data/raw folder."""
    folder = settings.data_dir / "raw"
    for f in SAMPLES.iterdir():
        shutil.copy(f, folder / f.name)
    return folder


@pytest.fixture
def ingested(corpus, services):
    return run_ingestion(corpus, validate_config({}), services)
