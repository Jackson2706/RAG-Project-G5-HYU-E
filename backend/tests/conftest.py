"""Shared fixtures.

Unit tests run without Docker or Ollama: MongoDB is replaced by mongomock, Qdrant
runs in-memory (local mode), embeddings come from a deterministic *test-only*
hashing embedder, and Ollama is an httpx MockTransport. Tests that need the real
BGE model are marked `integration` and skipped when it is not cached.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

import httpx
import mongomock
import pytest
from qdrant_client import QdrantClient

from app.api.deps import AppState
from app.config import PROJECT_ROOT, Settings
from app.ingestion.pipeline import IngestionPipeline
from app.models.documents import EmbeddingContract
from app.rag.pipeline import RAGPipeline, RAGServices
from app.rag.registry import OFFLINE_ORDER, ONLINE_ORDER, default_config, resolve_config
from app.repositories.mongodb import MongoRepository
from app.repositories.qdrant import QdrantRepository
from app.services.ollama import OllamaClient

SAMPLES = PROJECT_ROOT / "data" / "samples"

# mongomock 4.3 predates PyMongo 4.19, which passes a `sort` argument to bulk updates.
_add_update = mongomock.collection.BulkOperationBuilder.add_update
mongomock.collection.BulkOperationBuilder.add_update = lambda self, *a, sort=None, **kw: _add_update(self, *a, **kw)
TOKEN = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]")


class RegexTokenizer:
    """Transparent word/punctuation tokenizer (same pattern as Lesson 3) for fast tests."""

    name = "regex-test"

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [(m.start(), m.end()) for m in TOKEN.finditer(text)]


class HashEmbedder:
    """Deterministic signed-hash bag-of-words vectors. NON-SEMANTIC — test use only."""

    def __init__(self, dimension: int = 64) -> None:
        self.contract = EmbeddingContract(provider="test-hash", model_id="test-hash", model_revision="1", dimension=dimension,
                                          normalize=True, distance="Cosine", query_instruction="")  # fmt: skip
        self.calls = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.contract.dimension
        for tok in TOKEN.findall(text.lower()):
            d = hashlib.sha256(tok.encode()).digest()
            v[int.from_bytes(d[:4], "big") % len(v)] += 1.0 if d[4] % 2 == 0 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts, batch_size: int = 32):
        self.calls += len(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str):
        return self._vec(text)


class FakeOllama:
    """Scriptable Ollama server behind httpx.MockTransport. Records chat requests."""

    def __init__(self) -> None:
        self.models = [{"name": "test-model:1b", "size": 1, "modified_at": "2026-01-01T00:00:00Z",
                        "details": {"family": "test", "parameter_size": "1B", "quantization_level": "Q4"}}]  # fmt: skip
        self.capabilities = ["completion"]
        self.answer: str | None = "Orientation week includes an international student session on Thursday [S1]."
        self.fail: str | None = None  # "connect" | "500"
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail == "connect":
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": self.models})
        if path == "/api/show":
            name = json.loads(request.content)["model"]
            if name not in {m["name"] for m in self.models}:
                return httpx.Response(404, json={"error": f"model '{name}' not found"})
            return httpx.Response(200, json={"capabilities": self.capabilities, "details": {}, "model_info": {"test.context_length": 4096}})
        if path == "/api/chat":
            body = json.loads(request.content)
            self.requests.append(body)
            if self.fail == "500":
                return httpx.Response(500, json={"error": "boom"})
            words = (self.answer or "").split(" ")
            lines = [json.dumps({"message": {"role": "assistant", "thinking": "private"}, "done": False})]
            lines += [json.dumps({"message": {"role": "assistant", "content": w + (" " if i < len(words) - 1 else "")}, "done": False})
                      for i, w in enumerate(words)]  # fmt: skip
            lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "eval_count": len(words)}))
            return httpx.Response(200, content="\n".join(lines).encode())
        return httpx.Response(404, json={"error": "unknown path"})


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    return Settings(data_dir=data, qdrant_collection_prefix="test_chunks", ollama_chat_model="", mongodb_uri="mongodb://unused")


@pytest.fixture
def repos(settings: Settings) -> tuple[MongoRepository, QdrantRepository]:
    mongo = MongoRepository(mongomock.MongoClient(tz_aware=True)["hyu_test"])
    mongo.ensure_indexes()
    qdrant = QdrantRepository(QdrantClient(location=":memory:"), settings.qdrant_alias, local_mode=True)
    return mongo, qdrant


@pytest.fixture
def embedder() -> HashEmbedder:
    return HashEmbedder()


@pytest.fixture
def offline_config(request):
    return resolve_config(default_config(), OFFLINE_ORDER).resolved


@pytest.fixture
def ingestion(settings, repos, embedder) -> IngestionPipeline:
    mongo, qdrant = repos
    return IngestionPipeline(settings, mongo, qdrant, embedder_factory=lambda cfg, dist: embedder,
                             tokenizer_factory=lambda tid, rev: RegexTokenizer())  # fmt: skip


@pytest.fixture
def corpus(settings: Settings) -> Path:
    target = settings.data_dir / "raw"
    for f in SAMPLES.iterdir():
        shutil.copy(f, target / f.name)
    return target


@pytest.fixture
def ingested(ingestion, corpus, offline_config):
    report = ingestion.run(corpus, offline_config)
    assert report.status == "completed", report.error
    return report


@pytest.fixture
def fake_ollama() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def services(settings, repos, embedder, fake_ollama) -> RAGServices:
    mongo, qdrant = repos
    client = OllamaClient("http://ollama.test", transport=httpx.MockTransport(fake_ollama.handler))
    return RAGServices(settings, mongo, qdrant, client, embedder_factory=lambda rev: embedder,
                       tokenizer_factory=lambda rev: RegexTokenizer())  # fmt: skip


@pytest.fixture
def pipeline(services) -> RAGPipeline:
    return RAGPipeline(services)


@pytest.fixture
def app_state(settings, services, ingestion, pipeline) -> AppState:
    return AppState(settings=settings, services=services, pipeline=pipeline, ingestion=ingestion)


def online(overrides: dict[str, dict[str, Any]] | None = None):
    """Resolved online config with per-stage overrides: {"stage": {"enabled":..., "method":..., "params": {...}}}."""
    from app.models.config import PipelineConfig, StageConfig

    draft = PipelineConfig(stages={k: StageConfig(**v) for k, v in (overrides or {}).items()})
    result = resolve_config(draft, ONLINE_ORDER)
    assert result.valid, result.errors
    return result.resolved
