"""HYU suite: every configured preset on the frozen HYU labels (dev or test), plus its tables.

Run:     python -m evaluation.runner --suite hyu --split dev --run-id dev-01
Config:  evaluation/configs/hyu.yaml.  Metrics: evaluation/metrics/aaes.py (docs/aaes_spec.md "Metrics (P8)").
One record per (preset, case) in raw/hyu/<split>/<preset>__-.jsonl. The labels are read by the runner only.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from evaluation.metrics.aaes import (ANSWERED, action_metrics, applicable_recall_at, cited_error, flag_rate,
                                     inapplicable_intrusion_at, label_action)  # fmt: skip
from evaluation.metrics.stats import holm, mean, paired_compare
from evaluation.reports import load_jsonl

from app.config import DATA_DIR
from app.demo import oracle_for  # noqa: F401  (the runner calls hyu_suite.oracle_for)
from app.rag.schemas import make_doc_id
from app.rag.snapshot import snapshot_dir

LABELS_DIR = DATA_DIR / "HYU" / "labels"
RANK_DEPTH = 10  # chunks kept per record: enough for Recall/Intrusion@5 and @10


def load_cases(split: str, labels_dir: Path = LABELS_DIR) -> list[dict]:
    return sorted(load_jsonl(labels_dir / f"{split}.jsonl"), key=lambda c: c["case_id"])


def snapshot_doc_ids(snapshot_id: str) -> dict[str, str]:
    """Index doc_id (make_doc_id of the source URI) -> snapshot doc_id, the id the label spans use."""
    return {make_doc_id(r["source_uri"]): r["doc_id"] for r in load_jsonl(snapshot_dir(snapshot_id) / "documents.jsonl")}


def history_of(case: dict) -> list[str]:
    return [turn["text"] for turn in case.get("session_history") or [] if turn.get("role", "user") == "user"]


def question_for(case: dict, config: dict) -> str:
    """Presets without AAES profile understanding cannot read `history`: they get the earlier turns in the question
    (the same information as AAES, so comparison 1 measures the method, not access to the profile)."""
    history = history_of(case)
    if not history or (config.get("query_understanding") or {}).get("method") in ("profile_understanding", "self_query"):
        return case["question"]
    return " ".join(history) + "\n" + case["question"]


GOLD = "gold:"  # chunk-id prefix of oracle evidence (G1), made by app.demo.oracle_for


def gold_chunk(chunk_id: str) -> dict | None:
    """gold:D1:100-200 -> {"doc_id": "D1", "source_spans": [[100, 200]]}; other ids -> None."""
    if not chunk_id.startswith(GOLD):
        return None
    doc_id, _, span = chunk_id[len(GOLD):].rpartition(":")
    start, end = span.split("-")
    return {"doc_id": doc_id, "source_spans": [[int(start), int(end)]]}


LLM_METHODS = {"query_rewriting": None, "generation": None, "query_understanding": "self_query"}  # None = any method calls the LLM


def llm_calls(trace: dict) -> int:
    """Completed stages that called the LLM (generation, query rewriting, the self-query parser)."""
    config = trace.get("config") or {}
    return sum(1 for s in trace["stages"] if s["status"] == "completed" and s["stage_id"] in LLM_METHODS
               and LLM_METHODS[s["stage_id"]] in (None, (config.get(s["stage_id"]) or {}).get("method")))  # fmt: skip


def trace_record(case: dict, trace: dict, lookup) -> dict:
    """What the HYU metrics need from one trace. lookup(chunk_ids) -> {chunk_id: {"doc_id", "source_spans"}} from the index."""
    stages = {s["stage_id"]: s for s in trace["stages"]}
    ranked = next((s["output"] for sid in ("reranking", "metadata_enrichment") if (s := stages.get(sid)) and s["status"] == "completed"
                   and s["output"]), [])[:RANK_DEPTH]  # fmt: skip
    ranked_ids = [c["chunk_id"] for c in ranked]
    sources = trace.get("sources") or []
    cited_ids = [s["chunk_id"] for s in sources if s.get("cited")]
    uncited = trace.get("outcome") == "answered" and not cited_ids and bool(sources)
    if uncited:  # an answer without [E#] labels: score AER over every evidence block it was given
        cited_ids = [s["chunk_id"] for s in sources]
    spans = lookup(set(ranked_ids) | set(cited_ids))

    def chunk(chunk_id):
        return {"chunk_id": chunk_id, **spans.get(chunk_id, {"doc_id": None, "source_spans": []})}

    return {"qid": case["case_id"], "slice": case.get("slice"), "campus": (case.get("gold_profile") or {}).get("campus"),
            "status": trace["status"], "error": trace["error"], "action": trace.get("action"), "outcome": trace.get("outcome"),
            "behavior": label_action(trace.get("action"), trace.get("outcome")),
            "unknown_condition_evidence": bool(trace.get("unknown_condition_evidence")),
            "answer": trace.get("answer", ""), "total_ms": trace.get("total_ms"), "usage": trace.get("usage"), "llm_calls": llm_calls(trace),
            "ranked": [chunk(c) for c in ranked_ids], "cited": [chunk(c) for c in cited_ids], "uncited": uncited}  # fmt: skip


def case_scores(case: dict, rec: dict) -> dict:
    """Per-case metric values (None = undefined for this case)."""
    behavior = rec["behavior"]
    return {"qid": case["case_id"], "slice": case.get("slice"), "expected": case["expected_behavior"], "predicted": behavior,
            "acceptable": behavior in case["acceptable_behaviors"], "correct_action": behavior == case["expected_behavior"],
            "applicable_recall@5": applicable_recall_at(rec["ranked"], case, 5),
            "applicable_recall@10": applicable_recall_at(rec["ranked"], case, 10),
            "intrusion@5": inapplicable_intrusion_at(rec["ranked"], case, 5),
            "aer": cited_error(rec["cited"], case, behavior, "inapplicable"),
            "outdated": cited_error(rec["cited"], case, behavior, "outdated"),
            "unknown_caveat": rec["unknown_condition_evidence"] if behavior in ANSWERED else None,
            "answered": behavior in ANSWERED, "uncited": rec.get("uncited", False) if behavior in ANSWERED else None,
            "total_ms": rec.get("total_ms"), "llm_calls": rec.get("llm_calls")}  # fmt: skip


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(cases: list[dict], scores: list[dict]) -> dict:
    """Aggregate per-case scores (one preset, one slice or all)."""
    by_id = {c["case_id"]: c for c in cases}
    actions = action_metrics([(by_id[s["qid"]]["expected_behavior"], by_id[s["qid"]]["acceptable_behaviors"], s["predicted"]) for s in scores])
    latencies = sorted(s["total_ms"] for s in scores if s["total_ms"] is not None)
    return {"cases": len(scores), "action_accuracy": actions["accuracy"], "acceptable_rate": actions["acceptable_rate"],
            "macro_f1": actions["macro_f1"], "clarify_precision": actions["clarify_precision"], "clarify_recall": actions["clarify_recall"],
            "unnecessary_clarification_rate": actions["unnecessary_clarification_rate"],
            "gate_fpr": actions["gate"]["false_positive_rate"], "gate_fnr": actions["gate"]["false_negative_rate"],
            **{m: _mean(s[m] for s in scores) for m in ("applicable_recall@5", "applicable_recall@10", "intrusion@5", "aer", "outdated")},
            "unknown_caveat_rate": flag_rate([(bool(s["unknown_caveat"]), s["predicted"]) for s in scores]),
            "p50_ms": latencies[len(latencies) // 2] if latencies else None,
            "p95_ms": latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)] if latencies else None,
            "answered_rate": _mean(float(s["answered"]) for s in scores), "uncited_answer_rate": _mean(s["uncited"] for s in scores),
            "llm_calls": _mean(s["llm_calls"] for s in scores), "confusion": actions["confusion"]}  # fmt: skip


def _macro_f1(rows):
    return action_metrics(rows)["macro_f1"] or 0.0


def comparisons(scores: dict[str, dict[str, dict]], cases: list[dict], spec: dict, resamples: int = 10_000) -> list[dict]:
    """The pre-registered comparisons (PLAYBOOK "Pre-registered primary comparisons"), Holm-corrected.

    scores: preset -> qid -> per-case scores. shortcut: the "best baseline" is the one with the lowest AER on
    this same run; pick it on dev and fix it in hyu.yaml (`best_baseline`) before the test run.
    """
    ours, by_id, rows = spec["ours"], {c["case_id"]: c for c in cases}, []
    if ours not in scores:
        return []
    baselines = [b for b in spec["baselines"] if b in scores]
    def baseline_aer(b):
        m = _mean(s["aer"] for s in scores[b].values() if s["slice"] in ("conditional", "temporal"))
        return 1.0 if m is None else m

    best = spec.get("best_baseline") or min(baselines, key=baseline_aer, default=None)
    if best and best not in scores:
        rows.append({"comparison": f"{ours} vs {best}", "metric": "aer", "status": f"NOT_RUN: {best} has no results"})
        best = None
    if best:
        # 1. AER on conditional + temporal, cases where both answered (AER is defined only for answered cases)
        qids = [q for q in sorted(scores[ours]) if by_id[q].get("slice") in ("conditional", "temporal")
                and q in scores[best] and scores[ours][q]["aer"] is not None and scores[best][q]["aer"] is not None]  # fmt: skip
        pool = [q for q in scores[ours] if by_id[q].get("slice") in ("conditional", "temporal") and q in scores[best]
                and by_id[q].get("inapplicable_evidence")]  # fmt: skip
        coverage = f"{len(qids)} of {len(pool)} cases with inapplicable spans answered by both"
        if qids:
            rows.append({"comparison": f"{ours} vs {best}: AER (conditional + temporal, both answered; {coverage})", "metric": "aer",
                         **paired_compare([scores[ours][q]["aer"] for q in qids], [scores[best][q]["aer"] for q in qids], mean, resamples)})
        else:
            rows.append({"comparison": f"{ours} vs {best}: AER", "metric": "aer", "status": f"NOT_RUN: {coverage}"})
        rows.append({"comparison": f"{ours} vs {best}: correctness, unconditional (non-inferiority 3 points)", "metric": "correctness",
                     "status": "NOT_COMPUTED: needs the validated LLM judge (Appendix F)"})
    ablation = spec.get("ablation")
    if ablation in scores:
        qids = [q for q in sorted(scores[ours]) if q in scores[ablation]]
        rows.append({"comparison": f"{ours} vs {ablation}: action macro-F1", "metric": "macro_f1",
                     **paired_compare([(by_id[q]["expected_behavior"], by_id[q]["acceptable_behaviors"], scores[ours][q]["predicted"]) for q in qids],
                                      [(by_id[q]["expected_behavior"], by_id[q]["acceptable_behaviors"], scores[ablation][q]["predicted"]) for q in qids],
                                      _macro_f1, resamples)})  # fmt: skip
    else:
        rows.append({"comparison": f"{ours} vs {ablation}: action macro-F1", "metric": "macro_f1", "status": f"NOT_RUN: {ablation} has no results"})
    # Holm over the whole pre-registered family of 3: a comparison that did not run counts as p = 1.
    family = [r for r in rows if r["metric"] in ("aer", "correctness", "macro_f1")][:3]
    pvalues = [r.get("p", 1.0) for r in family] + [1.0] * (3 - len(family))
    for r, p in zip(family, holm(pvalues)):
        if "p" in r:
            r["p_holm"] = p
    return rows


def hyu_tables(run_dir: Path, split: str, spec: dict, labels_dir: Path = LABELS_DIR, resamples: int = 10_000) -> tuple[list, list, list, list]:
    """(summary rows per preset x slice, per-case rows, confusion rows, comparison rows) from raw/hyu/<split>/."""
    folder = Path(run_dir) / "raw" / "hyu" / split
    if not folder.is_dir():
        return [], [], [], []
    cases = load_cases(split, labels_dir)
    by_id = {c["case_id"]: c for c in cases}
    scores: dict[str, dict[str, dict]] = {}
    for path in sorted(folder.glob("*__-.jsonl")):
        preset = path.name.removesuffix("__-.jsonl")
        latest = {r["qid"]: r for r in load_jsonl(path) if r.get("status") == "completed"}  # the newer line wins
        scores[preset] = {q: case_scores(by_id[q], r) for q, r in latest.items() if q in by_id}
    summary, per_case, confusion = [], [], []
    for preset, per in scores.items():
        groups = defaultdict(list)
        for s in per.values():
            groups["all"].append(s)
            groups[s["slice"]].append(s)
        for slice_name, rows in sorted(groups.items()):
            agg = summarize(cases, rows)
            matrix = agg.pop("confusion")
            summary.append({"preset": preset, "slice": slice_name, **agg})
            confusion += [{"preset": preset, "slice": slice_name, "expected": e, **row} for e, row in matrix.items()]
        per_case += [{"preset": preset, **s} for s in per.values()]
    return summary, per_case, confusion, comparisons(scores, cases, spec, resamples)


SUMMARY_COLS = ["preset", "slice", "cases", "answered_rate", "action_accuracy", "acceptable_rate", "macro_f1", "unnecessary_clarification_rate",
                "applicable_recall@5", "intrusion@5", "aer", "uncited_answer_rate", "outdated", "unknown_caveat_rate", "p50_ms", "llm_calls"]


def write_hyu_reports(run_dir: Path, manifest: dict, write_csv) -> str:
    """Write the hyu_*.csv tables of every split in raw/hyu/ and return the summary.md section ("" if none)."""
    spec = (manifest.get("configs") or {}).get("hyu") or {}
    section = []
    for split_dir in sorted((Path(run_dir) / "raw" / "hyu").glob("*")):
        split = split_dir.name
        summary, per_case, confusion, compared = hyu_tables(run_dir, split, spec, resamples=spec.get("bootstrap_resamples", 10_000))
        write_csv(run_dir / f"hyu_{split}_slices.csv", summary)
        write_csv(run_dir / f"hyu_{split}_per_case.csv", per_case)
        write_csv(run_dir / f"hyu_{split}_actions_confusion.csv", confusion)
        write_csv(run_dir / f"hyu_{split}_comparisons_paired.csv", compared)
        section += [f"## HYU suite — {split}", "", "| " + " | ".join(SUMMARY_COLS) + " |", "|" + "---|" * len(SUMMARY_COLS)]
        for r in summary:
            if r["slice"] == "all":
                section.append("| " + " | ".join("N/A" if r.get(c) is None else f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c]) for c in SUMMARY_COLS) + " |")
        section += ["", "Per-slice rows: `hyu_%s_slices.csv`. Pre-registered comparisons (paired bootstrap 95%% CI, permutation p, Holm):" % split, ""]
        for c in compared:
            if "p" in c:
                section.append(f"- {c['comparison']}: diff {c['diff']:+.3f} [{c['ci_low']:+.3f}, {c['ci_high']:+.3f}], p {c['p']:.4f}, Holm {c['p_holm']:.4f} (n={c['cases']})")
            else:
                section.append(f"- {c['comparison']}: {c['status']}")
        section.append("")
    return "\n".join(section)
