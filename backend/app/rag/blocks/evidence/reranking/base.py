"""Abstract class for Reranking."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Evidence


class BaseReranker(PipelineBlock):
    """Reorder evidence by relevance.

    Input:  the query and the Evidence list (with text)
    Output: the same Evidence objects in a new order (renumber `rank` from 1)

    Rerankers reorder the first `rerank_depth` items and keep the rest in their original order behind
    them, so a deep candidate list (e.g. 100 for benchmark metrics) is never shortened.
    """

    @abstractmethod
    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]: ...

    @staticmethod
    def reordered(head: list[Evidence], tail: list[Evidence], new_scores: dict[str, float] | None = None, score_name: str = "") -> list[Evidence]:
        """`head` (the reranked part, in its new order) followed by the untouched `tail`, ranks renumbered from 1.

        Each item keeps its previous rank as scores["rank_before"]. When the reranker produced a
        score (new_scores[chunk_id]), it becomes the item's `score` and scores[score_name].
        """
        result = []
        for rank, e in enumerate(head + tail, start=1):
            scores = {**e.scores, "rank_before": e.rank}
            score = e.score
            if new_scores is not None and e.chunk_id in new_scores:
                score = scores[score_name] = round(new_scores[e.chunk_id], 6)
            result.append(e.model_copy(update={"rank": rank, "score": score, "scores": scores}))
        return result
