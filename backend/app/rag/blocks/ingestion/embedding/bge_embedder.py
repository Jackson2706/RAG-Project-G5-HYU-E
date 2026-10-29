"""IMPLEMENTED — BAAI/bge-small-en-v1.5 through Sentence Transformers (384 numbers per text)."""

from __future__ import annotations

from functools import lru_cache

from app.rag.blocks.ingestion.embedding.base import BaseEmbedder


@lru_cache(maxsize=2)
def load_sentence_transformer(model_name: str, revision: str | None):
    """Load a Sentence Transformers model once (the first call takes a few seconds)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=revision, device="cpu")


class SentenceTransformerEmbedder(BaseEmbedder):
    """The model name is Settings.embedding_model (backend/app/config.py)."""

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
