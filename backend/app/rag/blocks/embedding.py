"""Block: Embedding — turn text into vectors (lists of numbers).

The same embedder must be used for documents (ingestion) and questions (retrieval):
vectors from different models cannot be compared.
"""

from __future__ import annotations

from abc import abstractmethod
from functools import lru_cache

from app.rag.blocks.base import PipelineBlock


class BaseEmbedder(PipelineBlock):
    """Input: texts. Output: one vector (list[float]) per text, all of length `dimension()`."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, question: str) -> list[float]: ...

    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        """Character (start, end) of every token — used to measure chunks in real tokens."""

    def count_tokens(self, text: str) -> int:
        return len(self.token_offsets(text))


@lru_cache(maxsize=2)
def load_sentence_transformer(model_name: str, revision: str | None):
    """Load a Sentence Transformers model once (the first call takes a few seconds)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=revision, device="cpu")


class SentenceTransformerEmbedder(BaseEmbedder):
    """IMPLEMENTED — BAAI/bge-small-en-v1.5 (384 numbers), set in Settings.embedding_model."""

    @property
    def model(self):
        s = self.services.settings
        return load_sentence_transformer(s.embedding_model, s.embedding_revision)

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
        # BGE expects an instruction prefix on search questions (not on documents).
        return self.embed_documents([self.services.settings.query_instruction + question])[0]

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        encoded = self.model.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, verbose=False)
        return [(start, end) for start, end in encoded["offset_mapping"] if end > start]


class OllamaEmbedder(BaseEmbedder):
    """PLANNED — embeddings from an Ollama embedding model (POST /api/embed)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # TODO: call POST /api/embed with {"model": ..., "input": texts} and return the vectors.
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def embed_query(self, question: str) -> list[float]:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def dimension(self) -> int:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")
