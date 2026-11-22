"""Deck v3 Part 3: Lesson 3-6 evaluations from SAVED outputs (post-hoc where new). No system is re-run on test-1.

Run from Sources/ (MongoDB up; read-only):  python scripts/deck_v3_part3.py   # -> Report/slides/deck_v3/part3.json

Lesson 3  index report r5 checks, chunk-length distribution, rebuild determinism (r4 vs r5 chunk ids and texts).
Lesson 4  per method, from the saved top-10 ranked chunks (`ranked`, RANK_DEPTH 10) and the gold spans: gold hit@3,
          recall@3/@5/@10 (recall@20 is not computable: only 10 chunks were saved), MRR@10; applicability
          precision@3 = share of the top-3 evidence whose tags do not conflict with the case's labelled gold profile
          (aaes.label_chunk, the rule AAES uses). Citation support from evaluator v3.
Lesson 5  4x4 confusion (v2), precision/recall of "should not answer plainly", over-asking, risk-coverage points.
Lesson 6  slices by expected action, campus and missing detail; paired bootstrap A0 vs each baseline and each ablation
          (acceptable-action rate, v2); v1 vs v2 acceptable; A0 error taxonomy.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.metrics.aaes import _overlaps  # noqa: E402
from evaluation.metrics.stats import paired_compare  # noqa: E402

from app.config import RESULTS_DIR, REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.rag.aaes import label_chunk  # noqa: E402

TEST = RESULTS_DIR / "test-final"
ALL = ("B0", "R5", "R9S", "R15", "R16", "G0", "G1", "A0", "A1", "A2", "A3", "A4", "A6")
FULL = {"B0": "B0_BASIC_DENSE_RAG", "R5": "R5_HYBRID_CROSS_ENCODER", "R9S": "R9S_SCOPE_PREFILTER", "R15": "R15_SELF_QUERY",
        "R16": "R16_PROMPTED_CONDITIONAL", "G0": "G0_CLOSED_BOOK", "G1": "G1_ORACLE_CONTEXT", "A0": "A0_AAES", "A1": "A1_AAES_HARD_FILTER",
        "A2": "A2_AAES_ORACLE_PROFILE", "A3": "A3_AAES_ALWAYS_CLARIFY", "A4": "A4_QUESTION_ONLY_AMBIGUITY", "A6": "A6_AAES_NO_TEMPORAL"}  # fmt: skip
NOT_PLAIN = ("abstain", "conditional_answer", "clarify")


def latest(preset):
    out = {}
    for line in open(TEST / "raw" / "hyu" / "test" / f"{FULL[preset]}__-.jsonl"):
        r = json.loads(line)
        if r["status"] == "completed":
            out[r["qid"]] = r
    return out


def lesson3(db, out):
    rep = json.load(open(RESULTS_DIR / "index_reports" / "hyu_20261110_97dc1269_r5.json"))
    out["l3_checks_r5"] = rep["checks"]
    out["l3_facts_r5"] = rep["facts"]
    tokens = sorted(c.get("token_count") or 0 for c in db.chunks.find({}, {"token_count": 1, "_id": 0}))
    q = lambda p: tokens[min(len(tokens) - 1, int(p * len(tokens)))]  # noqa: E731
    bins = Counter(min(t // 40, 8) for t in tokens)
    out["l3_chunk_tokens"] = {"chunks": len(tokens), "min": tokens[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p95": q(0.95), "max": tokens[-1],
                              "mean": round(statistics.mean(tokens), 1), "histogram_40_token_bins": {f"{b * 40}-{b * 40 + 39}" if b < 8 else "320+": n for b, n in sorted(bins.items())}}  # fmt: skip
    r4 = Database.connect(get_settings()).for_index("hyu_20261110_97dc1269_r4")
    a = {c["chunk_id"]: c.get("text") for c in db.chunks.find({}, {"chunk_id": 1, "text": 1, "_id": 0})}
    b = {c["chunk_id"]: c.get("text") for c in r4.chunks.find({}, {"chunk_id": 1, "text": 1, "_id": 0})}
    out["l3_rebuild_r4_vs_r5"] = {"r4_chunks": len(b), "r5_chunks": len(a), "same_chunk_ids": len(set(a) & set(b)), "same_text": sum(a[i] == b.get(i) for i in a)}


def lesson4(db, cases, out):
    tags = {c["chunk_id"]: c for c in db.chunks.find({}, {"chunk_id": 1, "applicability": 1, "condition_status": 1, "_id": 0})}
    rows = {}
    for p in ALL:
        recs = latest(p)
        hit3, rec3, rec5, rec10, mrr, appl, n_cases, n_app = [], [], [], [], [], [], 0, 0
        for q, r in recs.items():
            case, ranked = cases[q], r.get("ranked")
            if ranked is None:
                continue
            gold = case.get("gold_evidence") or []
            if gold:
                n_cases += 1
                cov = lambda k: sum(any(_overlaps(c, [g]) for c in ranked[:k]) for g in gold) / len(gold)  # noqa: E731
                rec3.append(cov(3)), rec5.append(cov(5)), rec10.append(cov(10))
                hit3.append(float(cov(3) > 0))
                first = next((i for i, c in enumerate(ranked, 1) if any(_overlaps(c, [g]) for g in gold)), None)
                mrr.append(1 / first if first else 0.0)
            known = {a: [v] for a, v in (case.get("gold_profile") or {}).items() if v}
            top = [c for c in ranked[:3] if c["chunk_id"] in tags]
            if top:
                n_app += 1
                ok = [label_chunk((tags[c["chunk_id"]].get("applicability") or {}), tags[c["chunk_id"]].get("condition_status"), known) != "conflicting" for c in top]
                appl.append(sum(ok) / len(ok))
        mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
        rows[p] = {"cases_with_gold": n_cases, "gold_hit@3": mean(hit3), "recall@3": mean(rec3), "recall@5": mean(rec5), "recall@10": mean(rec10),
                   "mrr@10": mean(mrr), "applicability_precision@3": mean(appl), "cases_with_ranked": n_app}  # fmt: skip
    out["l4_retrieval"] = rows


def lesson5(cases, v2, v3, out):
    conf = defaultdict(lambda: defaultdict(int))
    for (p, q), r in v2.items():
        conf[p][(r["expected"], r["predicted"])] += 1
    out["l5_confusion"] = {p: {f"{e}->{pr}": n for (e, pr), n in sorted(m.items())} for p, m in conf.items()}
    rows = {}
    for p in ALL:
        recs = [v2[(p, q)] for q in cases]
        tp = sum(r["expected"] in NOT_PLAIN and r["predicted"] in NOT_PLAIN for r in recs)
        pred, pos = sum(r["predicted"] in NOT_PLAIN for r in recs), sum(r["expected"] in NOT_PLAIN for r in recs)
        plain = [r for r in recs if r["expected"] == "answer"]
        answered = [q for q in cases if v2[(p, q)]["predicted"] in ("answer", "conditional_answer")]
        judged = [v3[(p, q)] for q in answered if (p, q) in v3 and v3[(p, q)]["facts"]]
        rows[p] = {"not_plain_precision": round(tp / pred, 3) if pred else None, "not_plain_recall": round(tp / pos, 3), "not_plain_tp": tp, "predicted_not_plain": pred, "expected_not_plain": pos,
                   "over_asking_rate": round(sum(r["predicted"] in ("clarify", "conditional_answer") for r in plain) / len(plain), 3),
                   "answered_share": round(len(answered) / len(cases), 3),
                   "wrong_fact_among_answered_v3": round(sum("wrong" in j["facts"] for j in judged) / len(judged), 3) if judged else None}  # fmt: skip
    out["l5_decisions"] = rows


def lesson6(cases, v2, v1, v3, out):
    def acc(rows):
        return sum(r["acceptable"] == "True" for r in rows) / len(rows)

    qids = sorted(cases)
    out["l6_paired_acceptable_v2"] = {}
    for b in ("B0", "R5", "R9S", "R15", "R16", "G0", "G1", "A1", "A2", "A3", "A4", "A6"):
        res = paired_compare([v2[("A0", q)] for q in qids], [v2[(b, q)] for q in qids], acc)
        out["l6_paired_acceptable_v2"][b] = {k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()}
    slices = defaultdict(lambda: defaultdict(list))
    for (p, q), r in v2.items():
        c = cases[q]
        slices[p][f"expected={c['expected_behavior']}"].append(r["acceptable"] == "True")
        slices[p][f"campus={(c.get('gold_profile') or {}).get('campus')}"].append(r["acceptable"] == "True")
        slices[p][f"slice={c.get('slice')}"].append(r["acceptable"] == "True")
        for a in c.get("branch_attributes") or []:
            slices[p][f"missing={a}"].append(r["acceptable"] == "True")
    out["l6_slices_acceptable_v2"] = {p: {k: {"acceptable": round(sum(v) / len(v), 3), "cases": len(v)} for k, v in sorted(s.items())} for p, s in slices.items()}
    out["l6_v1_vs_v2_acceptable"] = {p: {"v1": round(acc([v1[(p, q)] for q in qids]), 3), "v2": round(acc([v2[(p, q)] for q in qids]), 3)} for p in ALL}
    # A0 error taxonomy over its v2-unacceptable test-1 replies (first matching category wins).
    replies = latest("A0")
    tax, examples = Counter(), defaultdict(list)
    for q in qids:
        r, c = v2[("A0", q)], cases[q]
        if r["acceptable"] == "True":
            j = v3.get(("A0", q))
            if r["predicted"] == "answer" and j and j["facts"] and sum(f == "correct" for f in j["facts"]) / len(j["facts"]) < 0.5:
                tax["thin answer (acceptable type, under half the facts, v3)"] += 1
                examples["thin answer (acceptable type, under half the facts, v3)"].append(q)
            continue
        asks_campus = "depends on your campus" in (replies[q].get("answer") or "")
        if r["predicted"] == "clarify" and c["expected_behavior"] == "abstain":
            k = "asked instead of referring"
        elif r["predicted"] == "clarify" and asks_campus:
            k = "unneeded campus question"
        elif r["predicted"] == "clarify":
            k = "unneeded or wrong detail asked (not campus)"
        elif r["predicted"] == "conditional_answer":
            k = "split into cases when one answer was expected"
        elif r["predicted"] == "abstain":
            k = "referred when an answer existed"
        elif r["predicted"] == "answer":
            k = "answered when it should refer or branch"
        else:
            k = "other"
        tax[k] += 1
        examples[k].append(q)
    out["l6_a0_error_taxonomy"] = {"unacceptable_replies": sum(v for k, v in tax.items() if not k.startswith("thin")), "counts": dict(tax),
                                   "examples": {k: v[:5] for k, v in examples.items()}}  # fmt: skip


def main() -> int:
    db = Database.connect(get_settings()).for_index("hyu_20261110_97dc1269_r5")
    cases = {c["case_id"]: c for c in hyu_suite.load_cases("test")}
    v2 = {(r["preset"].split("_")[0], r["qid"]): r for r in csv.DictReader(open(TEST / "hyu_test_v2_per_case.csv"))}
    v1 = {(r["preset"].split("_")[0], r["qid"]): r for r in csv.DictReader(open(TEST / "hyu_test_per_case.csv"))}
    raw = RESULTS_DIR / "quality_v3" / "raw"
    key = {k["id"]: k for k in map(json.loads, open(raw / "key.jsonl"))}
    judged = {j["id"]: j for f in sorted((raw / "judgments").glob("test_*.jsonl")) for j in map(json.loads, open(f))}
    v3 = {(key[i]["preset"].split("_")[0], key[i]["case_id"]): judged[i] for i in judged}
    out: dict = {"source": "saved test-1 outputs (raw/, v2 per-case, v3 judgments) and the r5 index (read-only); post-hoc"}
    lesson3(db, out)
    lesson4(db, cases, out)
    lesson5(cases, v2, v3, out)
    lesson6(cases, v2, v1, v3, out)
    path = REPORT_DIR / "slides" / "deck_v3" / "part3.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    for k in ("l3_chunk_tokens", "l3_rebuild_r4_vs_r5", "l4_retrieval", "l5_decisions", "l6_paired_acceptable_v2", "l6_a0_error_taxonomy"):
        print(k, json.dumps(out[k], default=str)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
