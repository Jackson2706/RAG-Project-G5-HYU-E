"""IMPLEMENTED — BAAI/bge-small-en-v1.5 through Sentence Transformers (384 numbers per text)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.rag.blocks.ingestion.embedding.base import BaseEmbedder


@lru_cache(maxsize=4)
def load_sentence_transformer(model_name: str, revision: str | None, device: str = "cpu"):
    """Load a Sentence Transformers model once (the first call takes a few seconds)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=revision, device=device)


def resolve_device(setting: str) -> str:
    """"auto" → the Apple GPU (mps) when PyTorch can use it, otherwise the CPU."""
    if setting != "auto":
        return setting
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class SentenceTransformerEmbedder(BaseEmbedder):
    """BGE-small. The model and revision come from Settings (backend/app/config.py), the device from
    Settings.embedding_device. Subclasses (e.g. MiniLM) only change the class attributes below."""

    MODEL: str | None = None  # None = Settings.embedding_model
    REVISION: str | None = None  # used together with MODEL
    QUERY_PREFIX: str | None = None  # None = Settings.query_instruction (BGE's search instruction)

    def _model_id(self) -> tuple[str, str | None]:
        s = self.services.settings
        return (self.MODEL, self.REVISION) if self.MODEL else (s.embedding_model, s.embedding_revision)

    def _query_prefix(self) -> str:
        """BGE expects an instruction prefix on search questions (not on documents)."""
        return self.services.settings.query_instruction if self.QUERY_PREFIX is None else self.QUERY_PREFIX

    @property
    def model(self):
        name, revision = self._model_id()
        return load_sentence_transformer(name, revision, resolve_device(self.services.settings.embedding_device))

    def dimension(self) -> int:
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        return int(get_dim())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # normalize_embeddings=True: every vector has length 1, so cosine similarity = dot product
        vectors = [list(map(float, v)) for v in self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)]
        if len(vectors) != len(texts) or any(len(v) != self.dimension() for v in vectors):
            raise ValueError(f"embedding model returned the wrong shape (expected {len(texts)} × {self.dimension()})")
        return vectors

    def embed_query(self, question: str) -> list[float]:
        return self.embed_documents([self._query_prefix() + question])[0]

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        encoded = self.model.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, verbose=False)
        return [(start, end) for start, end in encoded["offset_mapping"] if end > start]

    def contract(self) -> dict[str, Any]:
        name, revision = self._model_id()
        return {"method": self.method_id, "model": name, "revision": revision, "dimension": self.dimension(),
                "normalize": True, "similarity": "cosine", "max_seq_length": getattr(self.model, "max_seq_length", None),
                "query_prefix": self._query_prefix(), "document_prefix": "", "document_text": "section heading + newline + chunk text",
                "device": resolve_device(self.services.settings.embedding_device)}  # fmt: skip
