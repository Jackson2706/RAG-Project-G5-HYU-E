"""Reports from saved results — no inference is re-run.

    python -m evaluation.reports --run-id main

Reads evaluation/results/<run-id>/ (status.json, run_manifest.json, raw/**.jsonl) and writes:
results.json, per_query.csv, retrieval_comparison.csv, offline_comparison.csv, generation_comparison.csv,
failure_analysis.csv, summary.md. Missing values are written as "N/A", never as 0.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from evaluation import ROOT, beir
from evaluation.failure_analysis import CATEGORIES, classify_fixture, classify_generation, classify_retrieval
from evaluation.metrics.attribution import marker_validity
from evaluation.metrics.gate import gate_metrics
from evaluation.metrics.retrieval import clean_ranking, evaluate_run, recall_at

HEADLINE = ["nDCG@10", "MAP@100", "Recall@100", "P@10"]
ADDITIONAL = ["P@5", "Recall@5", "Recall@10", "Recall@20", "MRR@10", "HitRate@1", "HitRate@5", "HitRate@10", "nDCG@5", "R_cap@5", "R_cap@10", "Hole@10"]
BASELINE = "B0_BASIC_DENSE_RAG"
NA = "N/A"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def fmt(value, digits: int = 4):
    if value is None:
        return NA
    return round(value, digits) if isinstance(value, float) else value


def percentile(values: list[float], p: float):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = (len(values) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def paired_bootstrap(diffs: list[float], resamples: int = 2000, seed: int = 0) -> tuple[float | None, float | None]:
    """95% interval of the mean paired difference (resampling queries)."""
    if len(diffs) < 2:
        return None, None
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("no rows\n")
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, restval=NA)
        writer.writeheader()
        writer.writerows([{k: fmt(v) if not isinstance(v, (list, dict)) else json.dumps(v) for k, v in r.items()} for r in rows])


# --------------------------------------------------------------------------------------------- retrieval


def retrieval_tables(run_dir: Path, status: dict, split: str) -> tuple[list, list, list, list, dict]:
    """Rows for retrieval_comparison / offline_comparison / per_query / failure_analysis, plus raw aggregates."""
    qrels_cache: dict[str, dict] = {}
    comparison, offline_rows, per_query_rows, failure_rows = [], [], [], []
    records: dict[tuple, dict[str, dict]] = {}
    for key, info in sorted(status.items()):
        suite, dataset, rest = key.split("/")
        experiment, protocol = rest.split("__")
        if suite not in ("offline", "retrieval"):
            continue
        path = run_dir / "raw" / suite / dataset / f"{experiment}__{protocol}.jsonl"
        recs = load_jsonl(path)
        if info.get("status") != "COMPLETED" or not recs:
            row = {"suite": suite, "dataset": dataset, "protocol": protocol, "experiment": experiment, "status": info.get("status"),
                   "reason": info.get("reason", "")}  # fmt: skip
            (offline_rows if suite == "offline" else comparison).append(row)
            continue
        if dataset not in qrels_cache:
            qrels_cache[dataset] = beir.load(dataset, split)[2]
        all_qrels = qrels_cache[dataset]
        by_qid = {r["qid"]: r for r in recs}
        records[(suite, dataset, protocol, experiment)] = by_qid
        qrels = {q: all_qrels[q] for q in by_qid if q in all_qrels}
        per_query, mean = evaluate_run({q: r["ranking"] for q, r in by_qid.items()}, qrels)
        judged_total = {d for g in all_qrels.values() for d in g}
        hole = [sum(d not in judged_total for d in clean_ranking(by_qid[q]["ranking"], q)[:10]) / 10 for q in qrels]
        mean["Hole@10"] = {"mean": statistics.fmean(hole) if hole else None, "n": len(hole), "undefined": 0}
        row = {"suite": suite, "dataset": dataset, "protocol": protocol, "experiment": experiment, "status": "COMPLETED",
               "queries": len(by_qid), "failed_queries": sum(r["status"] != "completed" for r in recs),
               "subset": "first %d queries" % len(by_qid) if len(by_qid) < len(all_qrels) else "all test queries"}  # fmt: skip
        for m in HEADLINE + ADDITIONAL:
            row[m] = mean.get(m, {}).get("mean")
        row["undefined_queries"] = mean.get("Recall@100", {}).get("undefined")
        # stage diagnostics
        relevant = {q: {d for d, g in qrels[q].items() if g > 0} for q in qrels}
        for name in ("dense", "lexical", "fused"):
            vals = [recall_at(clean_ranking(r["candidates"][name], q), relevant[q], 100) for q, r in by_qid.items()
                    if name in r.get("candidates", {}) and relevant.get(q)]  # fmt: skip
            if vals:
                row[f"candidate_Recall@100_{name}"] = statistics.fmean(v for v in vals if v is not None)
        sel = [len(set(r["selected"]) & relevant[q]) / len(relevant[q]) for q, r in by_qid.items() if relevant.get(q)]
        row["selected_doc_recall"] = statistics.fmean(sel) if sel else None
        found_any = [q for q, r in by_qid.items() if relevant.get(q) and set(clean_ranking(r["ranking"], q)[:100]) & relevant[q]]
        lost = [q for q in found_any if not set(by_qid[q]["selected"]) & relevant[q]]
        row["relevant_lost_in_selection_rate"] = len(lost) / len(found_any) if found_any else None
        row["evidence_retention_rate"] = 1 - row["relevant_lost_in_selection_rate"] if row["relevant_lost_in_selection_rate"] is not None else None
        dup = [1 - len(set(r["selected"])) / r["selected_units"] for r in recs if r.get("selected_units")]
        row["duplicate_doc_rate_in_selection"] = statistics.fmean(dup) if dup else None
        row["evidence_tokens_mean"] = statistics.fmean(r["selected_tokens"] for r in recs) if recs else None
        row["units_ranked_mean"] = statistics.fmean(r["units_ranked"] for r in recs)
        row["effective_doc_depth_mean"] = statistics.fmean(len(r["ranking"]) for r in recs)
        row["depth_shortfall_queries"] = sum(len(clean_ranking(r["ranking"], r["qid"])) < 100 for r in recs)
        retrieval_ms = [sum(v for k, v in r["timings"].items() if k in ("query_rewriting", "dense_retrieval", "lexical_retrieval", "hybrid_fusion",
                                                                         "metadata_prefiltering", "metadata_postfiltering", "reranking")) for r in recs]  # fmt: skip
        row["retrieval_ms_p50"], row["retrieval_ms_p95"] = percentile(retrieval_ms, 0.5), percentile(retrieval_ms, 0.95)
        for stage in ("query_rewriting", "dense_retrieval", "lexical_retrieval", "hybrid_fusion", "reranking", "evidence_selection"):
            vals = [r["timings"][stage] for r in recs if stage in r["timings"]]
            if vals:
                row[f"{stage}_ms_p50"], row[f"{stage}_ms_p95"] = percentile(vals, 0.5), percentile(vals, 0.95)
        rewrites = [r["rewrite"] for r in recs if r.get("rewrite")]
        if rewrites:
            row["rewrite_validation_pass_rate"] = statistics.fmean(bool(w["validation"].get("passed")) for w in rewrites)
            tokens = [(w.get("details") or {}).get("output_tokens") for w in rewrites]
            row["aux_llm_output_tokens_mean"] = statistics.fmean(t for t in tokens if t is not None) if any(t is not None for t in tokens) else None
        reranks = [r["rerank"] for r in recs if r.get("rerank")]
        if reranks:
            outcomes = Counter(x.get("outcome") for x in reranks)
            row["rankgpt_outcomes"] = dict(outcomes)
        gates = [r["gate"] for r in recs if r.get("gate")]
        if gates:
            row["gate_proceed_rate"] = statistics.fmean(bool(g["sufficient"]) for g in gates)
        if suite == "offline":
            manifest = info.get("index_manifest") or {}
            chunking = (manifest.get("config") or {}).get("chunking", {})
            offline_rows.append({**{k: row[k] for k in ("suite", "dataset", "protocol", "experiment", "status", "queries")},
                                 "chunker": chunking.get("method"), **chunking.get("params", {}),
                                 "embedding": (manifest.get("embedding_contract") or {}).get("model"),
                                 "nDCG@10": row["nDCG@10"], "Recall@100": row["Recall@100"], "MAP@100": row["MAP@100"], "MRR@10": row["MRR@10"],
                                 "documents": manifest.get("documents"), "chunks": manifest.get("chunks"),
                                 "index_build_s": (manifest.get("timings") or {}).get("total_ms", 0) / 1000 or None,
                                 "embed_s": (manifest.get("timings") or {}).get("embed_ms", 0) / 1000 or None,
                                 "embedding_texts_per_s": manifest.get("embedding_texts_per_s"),
                                 "mongodb_storage_bytes": (info.get("storage") or {}).get("mongodb_storage_bytes"),
                                 "qdrant_raw_vector_bytes": (info.get("storage") or {}).get("qdrant_raw_vector_bytes"),
                                 "source_spans_invalid": manifest.get("source_spans_invalid"), "truncated_by_embedder": manifest.get("truncated_by_embedder"),
                                 "hnsw_built": (manifest.get("vector_index") or {}).get("hnsw_built"),
                                 "indexed_vectors": (manifest.get("vector_index") or {}).get("indexed_vectors"),
                                 "index_id": info.get("index_id"), "dense_search_ms_p50": percentile([r.get("dense", {}).get("search_ms") for r in recs], 0.5),
                                 "latency_repeats_ms_p50": percentile([x for r in recs for x in r.get("latency_repeats_ms", [])], 0.5),
                                 "latency_repeats_ms_p95": percentile([x for r in recs for x in r.get("latency_repeats_ms", [])], 0.95),
                                 "effective_doc_depth_mean": row["effective_doc_depth_mean"], "depth_shortfall_queries": row["depth_shortfall_queries"]})  # fmt: skip
        else:
            comparison.append(row)
        for q, r in by_qid.items():
            pq = per_query.get(q, {})
            per_query_rows.append({"suite": suite, "dataset": dataset, "protocol": protocol, "experiment": experiment, "qid": q,
                                   "status": r["status"], **{m: pq.get(m) for m in ("nDCG@10", "Recall@100", "MRR@10", "P@10")},
                                   "total_ms": r.get("total_ms"), "selected_docs": r["selected"]})  # fmt: skip
    # paired comparisons with B0 (same suite, dataset, protocol; the queries both ran)
    for row in comparison + offline_rows:
        if row.get("status") != "COMPLETED":
            continue
        base_key = ("retrieval", row["dataset"], row["protocol"], BASELINE) if row["suite"] == "retrieval" else ("offline", row["dataset"], "B", "O0_SECTION_AWARE_256_32")
        mine, base = records.get((row["suite"], row["dataset"], row["protocol"], row["experiment"])), records.get(base_key)
        if not mine or not base or base_key[3] == row["experiment"] or row["protocol"] != base_key[2]:
            continue  # protocols are never compared with each other
        qrels = qrels_cache[row["dataset"]]
        common = sorted(set(mine) & set(base) & set(qrels))
        pm, _ = evaluate_run({q: mine[q]["ranking"] for q in common}, {q: qrels[q] for q in common})
        pb, _ = evaluate_run({q: base[q]["ranking"] for q in common}, {q: qrels[q] for q in common})
        diffs = [pm[q]["nDCG@10"] - pb[q]["nDCG@10"] for q in common if pm[q]["nDCG@10"] is not None and pb[q]["nDCG@10"] is not None]
        lo, hi = paired_bootstrap(diffs)
        row.update({"paired_baseline": base_key[3], "paired_queries": len(diffs),
                    "delta_nDCG@10_vs_baseline": statistics.fmean(diffs) if diffs else None, "delta_ci95_low": lo, "delta_ci95_high": hi,
                    "improved": sum(d > 1e-9 for d in diffs), "regressed": sum(d < -1e-9 for d in diffs), "unchanged": sum(abs(d) <= 1e-9 for d in diffs),
                    "top10_jaccard_vs_baseline": statistics.fmean(len(set(mine[q]["ranking"][:10]) & set(base[q]["ranking"][:10])) /
                                                                  max(1, len(set(mine[q]["ranking"][:10]) | set(base[q]["ranking"][:10]))) for q in common) if common else None,
                    "selected_evidence_changed": sum(mine[q]["selected"] != base[q]["selected"] for q in common),
                    "latency_delta_ms_p50": percentile([(mine[q].get("total_ms") or 0) - (base[q].get("total_ms") or 0) for q in common], 0.5)})  # fmt: skip
        # failure categories (with the baseline's view for rewrite drift)
        for q in common:
            relevant = {d for d, g in qrels[q].items() if g > 0}
            base_found = bool(set(clean_ranking(base[q]["ranking"], q)[:100]) & relevant)
            labels = classify_retrieval({**mine[q], "qid": q}, relevant, base[q], base_found)
            mine_ndcg, base_ndcg = pm[q]["nDCG@10"], pb[q]["nDCG@10"]
            change = "unchanged"  # also when nDCG is undefined for this query
            if mine_ndcg is not None and base_ndcg is not None:
                if mine_ndcg > base_ndcg + 1e-9:
                    change = "improved"
                elif mine_ndcg < base_ndcg - 1e-9:
                    change = "regressed"
            if labels:
                failure_rows.append({"suite": row["suite"], "dataset": row["dataset"], "protocol": row["protocol"], "experiment": row["experiment"], "qid": q,
                                     "primary": labels[0], "category": CATEGORIES[labels[0]], "secondary": labels[1:],
                                     "expected_relevant": sorted(relevant)[:10], "retrieved_top10": mine[q]["ranking"][:10],
                                     "selected": mine[q]["selected"], "vs_baseline": change})  # fmt: skip
    # failures of the baselines themselves
    for (suite, dataset, protocol, experiment), by_qid in records.items():
        if experiment not in (BASELINE, "O0_SECTION_AWARE_256_32"):
            continue
        qrels = qrels_cache[dataset]
        for q, r in by_qid.items():
            relevant = {d for d, g in qrels.get(q, {}).items() if g > 0}
            labels = classify_retrieval({**r, "qid": q}, relevant)
            if labels:
                failure_rows.append({"suite": suite, "dataset": dataset, "protocol": protocol, "experiment": experiment, "qid": q, "primary": labels[0],
                                     "category": CATEGORIES[labels[0]], "secondary": labels[1:], "expected_relevant": sorted(relevant)[:10],
                                     "retrieved_top10": r["ranking"][:10], "selected": r["selected"], "vs_baseline": "baseline"})  # fmt: skip
    return comparison, offline_rows, per_query_rows, failure_rows, records


def ann_rows(records: dict) -> list[dict]:
    """O8 (HNSW) vs O7 (exact) on identical vectors and queries: neighbour recall of the approximate search."""
    rows = []
    for (suite, dataset, protocol, experiment), approx in records.items():
        if experiment != "O8_HNSW_ANN":
            continue
        exact = records.get((suite, dataset, protocol, "O7_EXACT_SEARCH"))
        if not exact:
            continue
        common = [q for q in approx if q in exact and approx[q].get("dense_chunks") and exact[q].get("dense_chunks")]
        row = {"dataset": dataset, "queries": len(common)}
        for k in (10, 100):
            vals = [len(set(approx[q]["dense_chunks"][:k]) & set(exact[q]["dense_chunks"][:k])) / max(1, len(exact[q]["dense_chunks"][:k])) for q in common]
            row[f"ann_recall@{k}_vs_exact"] = statistics.fmean(vals) if vals else None
        for name, recs in (("exact", exact), ("hnsw", approx)):
            reps = [x for q in common for x in recs[q].get("latency_repeats_ms", [])]
            row[f"{name}_search_ms_p50"], row[f"{name}_search_ms_p95"] = percentile(reps, 0.5), percentile(reps, 0.95)
            row["repetitions_per_query"] = len(recs[common[0]].get("latency_repeats_ms", [])) if common else None
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------------- fixture and generation


def fixture_tables(run_dir: Path, status: dict) -> tuple[list, list, list]:
    filter_rows, gate_rows, failures = [], [], []
    for exp in ("R0_DENSE", "R9_PREFILTERING", "R10_POSTFILTERING"):
        recs = load_jsonl(run_dir / "raw" / "fixture" / "hyu_fixture" / f"{exp}__-.jsonl")
        info = status.get(f"fixture/hyu_fixture/{exp}__-", {})
        if not recs:
            filter_rows.append({"experiment": exp, "status": info.get("status", "NOT_RUN"), "reason": info.get("reason", "")})
            continue
        with_target = [r for r in recs if r["target"]]
        filter_rows.append({
            "experiment": exp, "status": info.get("status"), "cases": len(recs), "candidate_cutoff": recs[0]["cutoff"],
            "target_hit_rate": statistics.fmean(bool(set(r["ranking"]) & set(r["target"])) for r in with_target) if with_target else None,
            "cases_with_eligible_relevant_doc": len(with_target),
            "ineligible_returned_rate": statistics.fmean(sum(d not in r["eligible"] for d in r["ranking"]) / max(1, len(r["ranking"])) for r in recs),
            "starved_rate": statistics.fmean(r["units_ranked"] < r["cutoff"] for r in recs),
            "empty_rate": statistics.fmean(r["units_ranked"] == 0 for r in recs),
            "returned_units_mean": statistics.fmean(r["units_ranked"] for r in recs),
        })  # fmt: skip
        for r in recs:
            if labels := classify_fixture(r):
                failures.append({"suite": "fixture", "dataset": "hyu_fixture", "experiment": exp, "qid": r["qid"], "primary": labels[0],
                                 "category": CATEGORIES[labels[0]], "secondary": labels[1:], "expected_relevant": r["target"],
                                 "retrieved_top10": r["ranking"], "selected": r["selected"]})  # fmt: skip
    recs = load_jsonl(run_dir / "raw" / "fixture" / "hyu_fixture" / "R12_SUFFICIENCY_GATE__-.jsonl")
    if recs:
        # Derived fixture label: sufficient = answerable AND a relevant document is among the selected evidence.
        cases = [(bool(r["gate"]["sufficient"]), r["answerable"] and bool(set(r["selected"]) & set(r["relevant"]))) for r in recs if r.get("gate")]
        gate_rows.append({"experiment": "R12_SUFFICIENCY_GATE", "label_source": "author-written fixture labels (answerable + relevant evidence selected)",
                          "signal": recs[0]["gate"].get("signals", {}).get("signal"), "threshold": recs[0]["gate"].get("signals", {}).get("threshold"),
                          **gate_metrics(cases)})  # fmt: skip
        for r, (proceed, sufficient) in zip([r for r in recs if r.get("gate")], cases):
            if proceed != sufficient:
                failures.append({"suite": "fixture", "dataset": "hyu_fixture", "experiment": "R12_SUFFICIENCY_GATE", "qid": r["qid"],
                                 "primary": "wrong_gate_decision", "category": CATEGORIES["wrong_gate_decision"], "secondary": [],
                                 "expected_relevant": r["relevant"], "retrieved_top10": r["ranking"], "selected": r["selected"],
                                 "explanation": f"gate {'proceeded' if proceed else 'abstained'} ({r['gate']['reason']}); label: {'sufficient' if sufficient else 'insufficient'}"})  # fmt: skip
    return filter_rows, gate_rows, failures


def generation_tables(run_dir: Path, status: dict, annotations_path: Path) -> tuple[list, list, dict]:
    annotations = {a["case_id"]: a for a in load_jsonl(annotations_path) if a.get("annotation_status") == "annotated"}
    rows, failures, per_case = [], [], {}
    for key, info in sorted(status.items()):
        if not key.startswith("generation/"):
            continue
        experiment = key.split("/")[2].split("__")[0]
        recs = load_jsonl(run_dir / "raw" / "generation" / "cases" / f"{experiment}__-.jsonl")
        if info.get("status") != "COMPLETED" or not recs:
            rows.append({"experiment": experiment, "status": info.get("status"), "reason": info.get("reason", "")})
            continue
        identity = info.get("model_identity", {})
        for group in sorted({r["dataset"] for r in recs}) + ["ALL"]:
            sub = [r for r in recs if group in ("ALL", r["dataset"])]
            ok = [r for r in sub if r["status"] == "completed"]
            markers = [marker_validity(r.get("raw_answer") or "", r.get("prompt_labels", [])) for r in ok if r.get("raw_answer")]
            gen_ms = [r["generation_ms"] for r in ok if r.get("raw_answer")]
            usage = [r.get("usage") or {} for r in ok]
            annotated = [r for r in ok if r["qid"] in annotations]
            rows.append({
                "experiment": experiment, "model": identity.get("name"), "digest": (identity.get("digest") or "")[:12],
                "quantization": identity.get("quantization"), "parameter_size": identity.get("parameter_size"), "group": group,
                "status": info.get("status"), "cases": len(sub), "failed": len(sub) - len(ok),
                "answered_rate": statistics.fmean(r["outcome"] == "answered" for r in ok) if ok else None,
                "abstention_rate": statistics.fmean(r["outcome"] == "insufficient_context" for r in ok) if ok else None,
                "marker_validity_mean": statistics.fmean(m["marker_validity"] for m in markers if m["marker_validity"] is not None)
                if any(m["marker_validity"] is not None for m in markers) else None,
                "answers_citing_a_source_rate": statistics.fmean(m["cites_any_source"] for m in markers) if markers else None,
                "invalid_markers_total": sum(m["invalid_markers"] for m in markers),
                "generation_ms_p50": percentile(gen_ms, 0.5), "generation_ms_p95": percentile(gen_ms, 0.95),
                "first_token_ms_p50": percentile([r.get("first_token_ms") for r in ok], 0.5),
                "output_tokens_mean": statistics.fmean(u["eval_count"] for u in usage if u.get("eval_count")) if any(u.get("eval_count") for u in usage) else None,
                "prompt_tokens_mean": statistics.fmean(u["prompt_eval_count"] for u in usage if u.get("prompt_eval_count"))
                if any(u.get("prompt_eval_count") for u in usage) else None,
                "annotated_cases": len(annotated),
                **{m: (NA if not annotated else None) for m in ("correctness", "relevance", "completeness", "grounding_support",
                                                                "citation_precision", "citation_coverage", "exact_match", "token_f1")},
            })  # fmt: skip
        for r in recs:
            per_case.setdefault(r["qid"], {})[experiment] = r
            marker = marker_validity(r.get("raw_answer") or "", r.get("prompt_labels", [])) if r.get("raw_answer") else {}
            if labels := classify_generation(r, marker):
                failures.append({"suite": "generation", "dataset": r["dataset"], "experiment": experiment, "qid": r["qid"], "primary": labels[0],
                                 "category": CATEGORIES[labels[0]], "secondary": labels[1:], "explanation": r.get("error") or
                                 f"{marker.get('invalid_markers')} [E#] marker(s) pointed to no evidence block"})  # fmt: skip
    return rows, failures, per_case


# --------------------------------------------------------------------------------------------- summary


def summary_markdown(manifest: dict, status: dict, comparison: list, offline_rows: list, ann: list, filters: list, gates: list,
                     generation: list, failures: list) -> str:
    def table(rows: list[dict], cols: list[str]) -> str:
        if not rows:
            return "_No results._\n"
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in rows:
            out.append("| " + " | ".join(str(fmt(r.get(c))) if not isinstance(r.get(c), (list, dict)) else json.dumps(r.get(c)) for c in cols) + " |")
        return "\n".join(out) + "\n"

    counts = Counter(v.get("status") for v in status.values())
    lines = [f"# Benchmark summary — run `{manifest.get('run_id')}`", "",
             f"Git `{(manifest.get('git') or {}).get('commit', '')[:10]}`{' (uncommitted changes)' if (manifest.get('git') or {}).get('dirty') else ''} · "
             f"split `{manifest.get('split')}` · smoke: {manifest.get('smoke')} · machine: {manifest.get('machine', {}).get('machine')}, "
             f"{round((manifest.get('machine', {}).get('memory_bytes') or 0) / 2**30)} GB · Ollama {manifest.get('ollama_version')}", "",
             "Task status: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), "",
             "All numbers below were computed from the saved per-query results. N/A = not measurable (missing labels, not run, or undefined).", ""]  # fmt: skip
    for protocol, title in (("B", "Protocol B — HYU-style chunked retrieval (chunks → BEIR documents)"), ("A", "Protocol A — BEIR documents as units")):
        rows = [r for r in comparison if r.get("protocol") == protocol and r.get("status") == "COMPLETED"]
        if not rows:
            continue
        lines += [f"## Report B — Online retrieval, {title}", "",
                  table(rows, ["dataset", "experiment", "subset", "nDCG@10", "MAP@100", "Recall@100", "P@10", "MRR@10", "retrieval_ms_p50",
                               "delta_nDCG@10_vs_baseline", "delta_ci95_low", "delta_ci95_high", "improved", "regressed"])]  # fmt: skip
        lines.append("Best nDCG@10 per dataset (all queries only; LLM methods ran on a subset and are compared with B0 on that subset above):")
        for ds in sorted({r["dataset"] for r in rows}):
            full = [r for r in rows if r["dataset"] == ds and r.get("subset") == "all test queries" and r.get("nDCG@10") is not None]
            if full:
                best = max(full, key=lambda r: r["nDCG@10"])
                base = next((r for r in full if r["experiment"] == BASELINE), None)
                lines.append(f"- **{ds}**: {best['experiment']} ({best['nDCG@10']:.4f})" + (f" vs B0 {base['nDCG@10']:.4f}" if base else ""))
        lines.append("")
    not_completed = [r for r in comparison if r.get("status") != "COMPLETED"]
    if not_completed:
        lines += ["Not completed online tasks:", "", table(not_completed, ["dataset", "protocol", "experiment", "status", "reason"])]
    if offline_rows:
        lines += ["## Report A — Offline comparison", "",
                  table([r for r in offline_rows if r.get("status") == "COMPLETED"],
                        ["dataset", "protocol", "experiment", "chunker", "chunk_size", "chunk_overlap", "embedding", "chunks", "nDCG@10", "Recall@100",
                         "index_build_s", "mongodb_storage_bytes", "qdrant_raw_vector_bytes", "source_spans_invalid", "truncated_by_embedder",
                         "hnsw_built", "delta_nDCG@10_vs_baseline", "delta_ci95_low", "delta_ci95_high"])]  # fmt: skip
        bad = [r for r in offline_rows if r.get("status") != "COMPLETED"]
        if bad:
            lines += [table(bad, ["dataset", "experiment", "status", "reason"])]
    if ann:
        lines += ["### Exact (O7) vs HNSW (O8) on identical vectors and queries", "",
                  table(ann, ["dataset", "queries", "ann_recall@10_vs_exact", "ann_recall@100_vs_exact", "exact_search_ms_p50", "hnsw_search_ms_p50",
                              "exact_search_ms_p95", "hnsw_search_ms_p95", "repetitions_per_query"]),
                  "Latency is Qdrant's measured query time over HTTP on this machine; HNSW only counts when the manifest says the graph was built.", ""]  # fmt: skip
    if filters or gates:
        lines += ["## Controlled fixture (5 synthetic HYU documents; author-written labels — not a benchmark)", "",
                  table(filters, ["experiment", "status", "cases", "candidate_cutoff", "target_hit_rate", "ineligible_returned_rate", "starved_rate",
                                  "empty_rate", "returned_units_mean"]),
                  table(gates, ["experiment", "label_source", "signal", "threshold", "cases", "TP", "FP", "TN", "FN", "accuracy", "precision", "recall",
                                "false_positive_rate", "false_negative_rate", "abstention_rate"])]  # fmt: skip
    if generation:
        lines += ["## Report C — Generation (same cached evidence for both backbones)", "",
                  table([r for r in generation if r.get("group") == "ALL" or "group" not in r],
                        ["experiment", "model", "quantization", "status", "cases", "failed", "answered_rate", "abstention_rate", "marker_validity_mean",
                         "answers_citing_a_source_rate", "invalid_markers_total", "generation_ms_p50", "generation_ms_p95", "output_tokens_mean",
                         "annotated_cases", "correctness", "grounding_support", "citation_precision"]),
                  "Correctness, relevance, completeness, grounding and citation support need annotated cases "
                  "(evaluation/annotations/). With 0 annotated cases they are N/A — BEIR qrels are not reference answers.", ""]  # fmt: skip
    if failures:
        by = Counter((f.get("dataset", ""), f.get("protocol", "-"), f["experiment"], f["category"]) for f in failures)
        lines += ["## Report D — Failure categories (earliest observable stage)", "",
                  table([{"dataset": d, "protocol": p, "experiment": e, "category": c, "queries": n} for (d, p, e, c), n in sorted(by.items())],
                        ["dataset", "protocol", "experiment", "category", "queries"]),
                  "Per-query details: failure_analysis.csv (expected relevant IDs, retrieved IDs, selected IDs, change vs baseline).", ""]  # fmt: skip
    lines += ["## Limitations", "",
              "- BEIR measures document ranking. No answer-quality metric is reported without annotated cases.",
              "- Protocol B maps chunk rankings to documents by first appearance; it is not the BEIR leaderboard setting.",
              "- LLM-based methods (R6, R7, R8, R13, R14) ran on a subset of queries; compare them with B0 on the same subset (paired columns).",
              "- One auxiliary LLM was used for all LLM-based retrieval methods; results may differ with another model.",
              "- No hyperparameter was tuned on the test splits: every value is the preset default declared before running.",
              "- Gate and filter results come from a small author-written fixture, not from independent labels.", ""]
    return "\n".join(lines)


def write_reports(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    status = json.loads((run_dir / "status.json").read_text()) if (run_dir / "status.json").exists() else {}
    manifest = json.loads((run_dir / "run_manifest.json").read_text()) if (run_dir / "run_manifest.json").exists() else {}
    split = manifest.get("split", "test")
    comparison, offline_rows, per_query, failures, records = retrieval_tables(run_dir, status, split)
    ann = ann_rows(records)
    filters, gates, fixture_failures = fixture_tables(run_dir, status)
    annotations = ROOT / ((manifest.get("configs") or {}).get("generation", {}).get("annotations") or "evaluation/annotations/qa_annotations.jsonl")
    generation, generation_failures, _ = generation_tables(run_dir, status, annotations)
    failures += fixture_failures + generation_failures
    write_csv(run_dir / "retrieval_comparison.csv", comparison)
    write_csv(run_dir / "offline_comparison.csv", offline_rows + [{"experiment": "ANN_" + r["dataset"], **r} for r in ann])
    write_csv(run_dir / "generation_comparison.csv", generation)
    write_csv(run_dir / "failure_analysis.csv", failures)
    write_csv(run_dir / "per_query.csv", per_query)
    results = {"run": manifest.get("run_id"), "status": status, "retrieval": comparison, "offline": offline_rows, "ann": ann,
               "fixture_filters": filters, "fixture_gate": gates, "generation": generation,
               "failure_counts": Counter(f"{f['experiment']}: {f['category']}" for f in failures)}  # fmt: skip
    (run_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (run_dir / "summary.md").write_text(summary_markdown(manifest, status, comparison, offline_rows, ann, filters, gates, generation, failures))


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate reports from saved benchmark results (no inference)")
    parser.add_argument("--run-id", default="main")
    parser.add_argument("--suite", default="all", help="accepted for symmetry with the runner; reports always cover the whole run")
    args = parser.parse_args()
    run_dir = ROOT / "evaluation" / "results" / args.run_id
    if not (run_dir / "status.json").exists():
        raise SystemExit(f"No results in {run_dir}. Run: python -m evaluation.runner --run-id {args.run_id}")
    write_reports(run_dir)
    print(f"Reports written to {run_dir.relative_to(ROOT)}/ (summary.md, results.json, *.csv)")


if __name__ == "__main__":
    main()
