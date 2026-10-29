"""IMPLEMENTED — look up chunk text, section, page and document title in MongoDB."""

from __future__ import annotations

from app.rag.blocks.evidence.metadata_enrichment.base import BaseMetadataEnricher
from app.rag.schemas import Candidate, Evidence


class MongoChunkLookup(BaseMetadataEnricher):
    """A chunk that is in Qdrant but missing in MongoDB raises an error instead of being skipped
    silently (the two databases are out of sync: re-index)."""

    async def enrich(self, candidates: list[Candidate]) -> list[Evidence]:
        db = self.services.db
        chunks = db.get_chunks([c.chunk_id for c in candidates])
        documents = db.get_documents(list({c.doc_id for c in candidates}))
        missing = [c.chunk_id for c in candidates if c.chunk_id not in chunks or c.doc_id not in documents]
        if missing:
            raise RuntimeError(f"{len(missing)} chunk(s) found in Qdrant are missing in MongoDB: {missing[:3]}. Re-index the documents.")
        return [
            Evidence(rank=c.rank, chunk_id=c.chunk_id, doc_id=c.doc_id, score=c.score, text=chunks[c.chunk_id]["text"],
                     title=documents[c.doc_id]["title"], source_uri=documents[c.doc_id]["source_uri"],
                     section=chunks[c.chunk_id].get("section"), page_number=chunks[c.chunk_id].get("page_number"),
                     token_count=chunks[c.chunk_id].get("token_count", 0))
            for c in candidates
        ]  # fmt: skip
