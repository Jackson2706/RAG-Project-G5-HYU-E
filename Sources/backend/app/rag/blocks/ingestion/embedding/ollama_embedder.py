"""PLANNED — embeddings from an Ollama embedding model (POST /api/embed)."""

from __future__ import annotations

from app.rag.blocks.ingestion.embedding.base import BaseEmbedder


class OllamaEmbedder(BaseEmbedder):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # TODO: call POST /api/embed with {"model": ..., "input": texts} and return the vectors.
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def embed_query(self, question: str) -> list[float]:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def dimension(self) -> int:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        raise NotImplementedError("Ollama embeddings are not implemented yet.")
