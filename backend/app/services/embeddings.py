"""Sentence Transformers embedding provider with an explicit, validated contract."""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Protocol, Sequence

import numpy as np

from app.models.documents import EmbeddingContract


class EmbeddingProvider(Protocol):
    contract: EmbeddingContract

    def embed_documents(self, texts: Sequence[str], batch_size: int = 32) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class Embedder:
    def __init__(self, model_id: str, revision: str | None, normalize: bool, query_instruction: str,
                 distance: str = "Cosine", device: str = "cpu") -> None:  # fmt: skip
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_id, revision=revision, device=device)
        self._lock = threading.Lock()  # SentenceTransformer.encode is not guaranteed thread-safe
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        dim = get_dim()
        if not dim:
            raise ValueError(f"model '{model_id}' does not report an embedding dimension")
        self.contract = EmbeddingContract(
            provider="sentence_transformers", model_id=model_id, model_revision=revision, dimension=int(dim),
            normalize=normalize, distance=distance, query_instruction=query_instruction,
            max_seq_length=self._model.max_seq_length,
        )  # fmt: skip

    def _encode(self, texts: Sequence[str], batch_size: int) -> list[list[float]]:
        with self._lock:
            vectors = self._model.encode(list(texts), batch_size=batch_size, normalize_embeddings=self.contract.normalize,
                                         convert_to_numpy=True, show_progress_bar=False)  # fmt: skip
        validate_vectors(vectors, len(texts), self.contract.dimension)
        return vectors.astype(np.float32).tolist()

    def embed_documents(self, texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
        return self._encode(texts, batch_size) if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self.contract.query_instruction + text], 1)[0]


def validate_vectors(vectors: np.ndarray, expected_count: int, dimension: int) -> None:
    if vectors.ndim != 2 or vectors.shape[0] != expected_count:
        raise ValueError(f"embedding batch returned shape {vectors.shape}, expected ({expected_count}, {dimension})")
    if vectors.shape[1] != dimension:
        raise ValueError(f"embedding dimension {vectors.shape[1]} does not match contract dimension {dimension}")
    if not np.issubdtype(vectors.dtype, np.floating) or not np.isfinite(vectors).all():
        raise ValueError("embedding output contains non-float or non-finite values")


@lru_cache(maxsize=2)
def load_embedder(model_id: str, revision: str | None, normalize: bool, query_instruction: str,
                  distance: str = "Cosine", device: str = "cpu") -> Embedder:  # fmt: skip
    return Embedder(model_id, revision, normalize, query_instruction, distance, device)
