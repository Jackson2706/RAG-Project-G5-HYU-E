"""IMPLEMENTED — RankGPT-style listwise reranking: a local LLM orders the passages ([2] > [1] > …)."""

from __future__ import annotations

import re
import time

from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.schemas import Evidence

SYSTEM = "You are RankGPT, an intelligent assistant that can rank passages based on their relevancy to the query."


def build_prompt(query: str, passages: list[str]) -> list[dict[str, str]]:
    """The RankGPT prompt (Sun et al., 2023): numbered passages, then ask for an ordering of the identifiers."""
    n = len(passages)
    listing = "\n".join(f"[{i}] {text}" for i, text in enumerate(passages, start=1))
    user = (f"I will provide you with {n} passages, each indicated by a numerical identifier []. "
            f"Rank the passages based on their relevance to the search query: {query}\n\n{listing}\n\n"
            f"Search Query: {query}\nRank the {n} passages above based on their relevance to the search query. "
            "List them in descending order of relevance using their identifiers, the most relevant first. "
            "The output format must be [] > [], e.g. [2] > [1]. Only respond with the ranking, do not explain.")  # fmt: skip
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def check_permutation(text: str, n: int) -> dict:
    """Read "[3] > [1] > …" and report problems. Returns {"order": valid ids in order (first occurrence),
    "invalid": ids outside 1..n, "duplicates": repeated ids, "missing": ids never mentioned}."""
    order, invalid, duplicates = [], [], []
    for token in re.findall(r"\[(\d+)\]", text):
        i = int(token)
        if not 1 <= i <= n:
            invalid.append(i)
        elif i in order:
            duplicates.append(i)
        else:
            order.append(i)
    return {"order": order, "invalid": invalid, "duplicates": duplicates, "missing": [i for i in range(1, n + 1) if i not in order]}


class RankGPTReranker(BaseReranker):
    """Hyperparameters: model (local Ollama model), rerank_depth (passages in the one ranking window),
    max_words (each passage is cut to this many words), temperature, max_tokens.

    Output check: every passage must appear exactly once. Policy:
      1. problems (missing/duplicate/invalid ids) → ask once more;
      2. still problems but at least half the passages were ranked → REPAIR: keep the valid order,
         drop duplicates/invalid ids, append missing passages in their original order;
      3. otherwise → FALLBACK: keep the original order.
    The LLM returns an order, not relevance scores, so `score` stays the incoming score.
    """

    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        depth = self.params["rerank_depth"]
        head, tail = evidence[:depth], evidence[depth:]
        if len(head) < 2:
            return evidence
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        passages = [" ".join(((f"{e.section}. " if e.section else "") + e.text).split()[: self.params["max_words"]]) for e in head]
        messages = build_prompt(query, passages)
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 8192, "seed": 42}
        attempts, start = [], time.perf_counter()
        for _ in range(2):
            text, usage = await ollama.complete(model, messages, options)
            check = check_permutation(text, len(head))
            attempts.append({"output": text[:500], **{k: v for k, v in check.items() if k != "order"}, "ranked": len(check["order"]),
                             "prompt_tokens": usage.get("prompt_eval_count"), "output_tokens": usage.get("eval_count")})  # fmt: skip
            if not (check["missing"] or check["duplicates"] or check["invalid"]):
                break
        if check["missing"] or check["duplicates"] or check["invalid"]:
            outcome = "repaired" if len(check["order"]) >= len(head) / 2 else "fallback_original_order"
        else:
            outcome = "valid"
        order = check["order"] + check["missing"] if outcome != "fallback_original_order" else list(range(1, len(head) + 1))
        self.trace_details = {"model": model["name"], "outcome": outcome, "attempts": attempts,
                              "latency_ms": round((time.perf_counter() - start) * 1000, 1)}  # fmt: skip
        return self.reordered([head[i - 1] for i in order], tail)
