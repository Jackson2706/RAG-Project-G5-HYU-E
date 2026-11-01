"""IMPLEMENTED — sentence-transformers/all-MiniLM-L6-v2 (384 numbers per text), the alternative embedding (O6)."""

from __future__ import annotations

from app.rag.blocks.ingestion.embedding.bge_embedder import SentenceTransformerEmbedder


class MiniLMEmbedder(SentenceTransformerEmbedder):
    """Same code as BGE, another model: no query instruction, and inputs longer than 256 word pieces
    are cut off by the model (BGE: 512). Its vectors cannot be mixed with BGE vectors — it always
    needs its own index."""

    MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    QUERY_PREFIX = ""
