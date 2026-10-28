#!/usr/bin/env python
"""Controlled retrieval ablation (and optional answer evaluation) over a labelled question set.

    conda activate RAG
    python scripts/evaluate.py --questions data/eval/sample_questions.jsonl
    python scripts/evaluate.py --questions data/eval/sample_questions.jsonl --with-generation --model qwen3:4b

Each experiment changes ONE component relative to the dense baseline; everything else
(index revision, embedding, evidence settings, question set) is held fixed. Relevance labels
are document-level (`relevant`: list of source_uri). Results are written to data/eval/results/.

Retrieval metrics are computed on the ranked, de-duplicated *document* list derived from the
candidates after metadata enrichment (before evidence selection), at cut-off k.
Answer metrics (with --with-generation) are reported separately and are not mixed in.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import _bootstrap

from app.config import get_settings
from app.ingestion.loaders import sha256_bytes
from app.models.config import PipelineConfig, StageConfig
from app.rag.pipeline import RAGPipeline, RAGServices
from app.rag.registry import ONLINE_ORDER, resolve_config
from app.services.ollama import OllamaClient

EXPERIMENTS: dict[str, tuple[str, dict[str, dict[str, Any]]]] = {
    "A_dense": ("Dense RAG baseline", {}),
    "B_dense_bm25": ("Dense + BM25 (RRF)", {"lexical_retrieval": {"enabled": True}, "hybrid_fusion": {"method": "rrf"}}),
    "C_dense_metadata": ("Dense + metadata filtering", {"query_understanding": {"method": "rule_based"}, "metadata_filtering": {"enabled": True}}),
    "D_dense_rerank": ("Dense + reranking", {"reranking": {"enabled": True, "method": "cross_encoder"}}),
    "E_full": ("Full advanced pipeline", {"query_understanding": {"method": "rule_based"}, "metadata_filtering": {"enabled": True},
                                          "lexical_retrieval": {"enabled": True}, "hybrid_fusion": {"method": "rrf"},
                                          "reranking": {"enabled": True, "method": "cross_encoder"}}),
}  # fmt: skip


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(d in relevant for d in ranked[:k]) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(d in relevant for d in ranked[:k]) / len(relevant)


def mrr(ranked: list[str], relevant: set[str]) -> float:
    return next((1 / (i + 1) for i, d in enumerate(ranked) if d in relevant), 0.0)


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, d in enumerate(ranked[:k]) if d in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def ranked_documents(trace) -> list[str]:
    stage = next(s for s in trace.stages if s.stage_id == "metadata_enrichment")
    docs: list[str] = []
    for c in stage.output.get("candidates", []):
        uri = c.get("source_uri")
        if uri and uri not in docs:
            docs.append(uri)
    return docs


async def run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    mongo, qdrant = _bootstrap.connect()
    revision = mongo.active_revision()
    if revision is None:
        sys.exit("No active index. Run scripts/ingest.py first.")
    raw = args.questions.read_bytes()
    questions = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    ollama = OllamaClient(settings.ollama_base_url, settings.ollama_request_timeout)
    pipeline = RAGPipeline(RAGServices(settings, mongo, qdrant, ollama))
    k = args.k
    report: dict[str, Any] = {
        "dataset": {"path": str(args.questions), "sha256": sha256_bytes(raw), "questions": len(questions)},
        "index_revision": revision.revision_id, "embedding": revision.embedding.model_dump(), "k": k, "experiments": {},
    }  # fmt: skip
    for exp_id, (name, overrides) in EXPERIMENTS.items():
        base = {"generation": {"params": {"model": args.model, "temperature": 0.0, "seed": 42}}} if args.model else {}
        draft = PipelineConfig(stages={s: StageConfig(**v) for s, v in {**base, **overrides}.items()})
        resolved = resolve_config(draft, ONLINE_ORDER)
        if not resolved.valid:
            report["experiments"][exp_id] = {"name": name, "status": "unavailable", "reason": "; ".join(e.message for e in resolved.errors)}
            print(f"{exp_id:18s} unavailable: {report['experiments'][exp_id]['reason']}")
            continue
        per_query, latencies = [], []
        for q in questions:
            t0 = time.perf_counter()
            stop = None if args.with_generation else "evidence_selection"
            trace = await pipeline.run(q["question"], resolved.resolved, session_id=f"eval-{exp_id}", stop_after=stop, persist=False)
            latencies.append((time.perf_counter() - t0) * 1000)
            row: dict[str, Any] = {"qid": q["qid"], "status": trace.status, "error": trace.error, "latency_ms": round(latencies[-1], 1)}
            if trace.status == "completed":
                ranked = ranked_documents(trace)
                row["ranked_documents"] = ranked[:k]
                rel = set(q["relevant"])
                if rel:
                    row.update(precision=precision_at_k(ranked, rel, k), recall=recall_at_k(ranked, rel, k), mrr=mrr(ranked, rel), ndcg=ndcg_at_k(ranked, rel, k))
                if args.with_generation and trace.result:
                    cited = [c for c in trace.result.citations if c.cited]
                    row.update(outcome=trace.result.outcome, cited=len(cited),
                               citations_valid=sum(1 for c in cited if c.resolved and c.span_verified is not False),
                               invalid_markers=len(trace.result.citation_report.invalid_markers) if trace.result.citation_report else 0)  # fmt: skip
            per_query.append(row)
        labelled = [r for r in per_query if "mrr" in r]
        summary: dict[str, Any] = {f"{m}@{k}" if m != "mrr" else "mrr": round(statistics.mean(r[m] for r in labelled), 4)
                                   for m in ("precision", "recall", "mrr", "ndcg")} if labelled else {}  # fmt: skip
        summary.update(labelled_queries=len(labelled), failed=sum(r["status"] != "completed" for r in per_query),
                       latency_ms_median=round(statistics.median(latencies), 1))  # fmt: skip
        if args.with_generation:
            ans = [r for r in per_query if "outcome" in r]
            unanswerable = {q["qid"] for q in questions if not q["answerable"]}
            cited_total = sum(r["cited"] for r in ans)
            summary.update(
                answered=sum(r["outcome"] == "answered" for r in ans),
                abstained_on_unanswerable=f"{sum(r['outcome'] != 'answered' for r in ans if r['qid'] in unanswerable)}/{len(unanswerable)}",
                answered_answerable=f"{sum(r['outcome'] == 'answered' for r in ans if r['qid'] not in unanswerable)}/{len(questions) - len(unanswerable)}",
                citation_validity=round(sum(r["citations_valid"] for r in ans) / cited_total, 4) if cited_total else None,
                invalid_markers=sum(r["invalid_markers"] for r in ans),
            )  # fmt: skip
        report["experiments"][exp_id] = {"name": name, "status": "completed", "config_hash": resolved.resolved.config_hash,
                                         "config": resolved.resolved.model_dump(), "summary": summary, "queries": per_query}  # fmt: skip
        print(f"{exp_id:18s} {json.dumps(summary)}")
    await ollama.aclose()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=Path("data/eval/sample_questions.jsonl"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--with-generation", action="store_true", help="Also run generation and evaluate answers (slow)")
    parser.add_argument("--model", default="", help="Ollama model for --with-generation (default: OLLAMA_CHAT_MODEL / first installed)")
    parser.add_argument("--out", type=Path, help="Output JSON path (default: data/eval/results/<revision>_<timestamp>.json)")
    args = parser.parse_args()
    report = asyncio.run(run(args))
    out = args.out or get_settings().data_dir / "eval" / "results" / f"{report['index_revision']}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"results written to {out}")


if __name__ == "__main__":
    main()
