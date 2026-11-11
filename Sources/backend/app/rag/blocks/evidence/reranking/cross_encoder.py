"""IMPLEMENTED — a cross-encoder reads question and chunk TOGETHER and scores each pair."""

from __future__ import annotations

from functools import lru_cache

from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.blocks.ingestion.embedding.bge_embedder import resolve_device
from app.rag.schemas import Evidence

MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"


@lru_cache(maxsize=2)
def load_cross_encoder(device: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(MODEL, revision=REVISION, device=device, max_length=512)


class CrossEncoderReranker(BaseReranker):
    """Hyperparameters: rerank_depth (how many top items are scored), batch_size, device.

    The bi-encoder (dense retrieval) embeds question and chunk separately; a cross-encoder sees both
    in one input, which is more accurate but needs one model call per pair — so only the top
    `rerank_depth` items are rescored. Scores are the model's relevance logits (higher = more relevant;
    not probabilities, not cosine similarities). Inputs longer than 512 word pieces are cut off.
    """

    async def rerank(self, query: str, evidence: list[Evidence], profile: dict | None = None) -> list[Evidence]:
        depth = self.params["rerank_depth"]
        head, tail = evidence[:depth], evidence[depth:]
        if not head:
            return evidence
        model = load_cross_encoder(resolve_device(self.params["device"]))
        pairs = [(query, f"{e.section}\n{e.text}" if e.section else e.text) for e in head]
        logits = model.predict(pairs, batch_size=self.params["batch_size"], show_progress_bar=False)
        scores = {e.chunk_id: float(s) for e, s in zip(head, logits, strict=True)}
        head = sorted(head, key=lambda e: (-scores[e.chunk_id], e.rank))
        return self.reordered(head, tail, scores, "cross_encoder")
