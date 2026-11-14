"""Evaluator v3 (A36, post hoc, LLM judge): aggregate the judgments of saved replies. No system is re-run.

Run from Sources/ after the judges wrote Report/results/quality_v3/raw/judgments/{dev,test}_NN.jsonl:
  python scripts/quality_v3.py           # -> Report/results/quality_v3/{summary.md, metrics_<split>.csv, comparisons.csv, validation.json}

Per preset (expected behaviour comes from the label, via the runner's reader):
  fact coverage        answer-expected cases: correct facts / required facts (a reply that is not an answer scores 0)
  wrong-fact rate      answer-expected cases whose reply states at least one wrong fact
  wrong-group rate     answered replies (answer or conditional answer) that apply a rule to the wrong student group
  citation support     supported cited sentences / cited sentences, pooled over answered replies
  correct conditions   branching cases (labelled conditional answer or clarify): a conditional answer whose conditions
                       match the evidence, or a question about a branch attribute
  useful question      clarify replies that ask about a branch attribute
  right referral       abstain replies that name the right office or next step
Paired bootstrap 95% CIs and permutation p for A0 vs B0 and A0 vs R16 (evaluation.metrics.stats.paired_compare).
Validation: Cohen's kappa per field between the main judge and the second judge on the same 100 dev items; and, once
Report/notes/quality_human_check.csv is filled in, the human's agreement with the main judge.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.metrics.stats import paired_compare  # noqa: E402

from app.config import REPORT_DIR, RESULTS_DIR  # noqa: E402

OUT = RESULTS_DIR / "quality_v3"
RAW = OUT / "raw"
PRESETS = ("B0_BASIC_DENSE_RAG", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL", "A0_AAES", "G0_CLOSED_BOOK", "G1_ORACLE_CONTEXT")
BRANCHING, ANSWERED = ("conditional_answer", "clarify"), ("answer", "conditional_answer")


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ratio(a: float, b: float) -> float | None:
    return a / b if b else None


# Each metric: list of per-case records {expected, type, j (judgment)} -> rate (None if undefined).
def fact_coverage(rows):
    vals = [(sum(f == "correct" for f in r["j"]["facts"] or []) / len(r["j"]["facts"]) if r["type"] in ANSWERED and r["j"]["facts"] else 0.0)
            for r in rows if r["expected"] == "answer"]  # fmt: skip
    return ratio(sum(vals), len(vals))


def answered_share(rows):
    pool = [r for r in rows if r["expected"] == "answer"]
    return ratio(sum(r["type"] in ANSWERED and bool(r["j"]["facts"]) for r in pool), len(pool))


def coverage_when_answered(rows):
    vals = [sum(f == "correct" for f in r["j"]["facts"]) / len(r["j"]["facts"]) for r in rows
            if r["expected"] == "answer" and r["type"] in ANSWERED and r["j"]["facts"]]  # fmt: skip
    return ratio(sum(vals), len(vals))


def wrong_fact(rows):
    pool = [r for r in rows if r["expected"] == "answer"]
    return ratio(sum(r["type"] in ANSWERED and "wrong" in (r["j"]["facts"] or []) for r in pool), len(pool))


def wrong_group(rows):
    pool = [r for r in rows if r["type"] in ANSWERED and r["j"]["wrong_group"] is not None]
    return ratio(sum(bool(r["j"]["wrong_group"]) for r in pool), len(pool))


def citation_support(rows):
    pool = [r for r in rows if r["type"] in ANSWERED]
    return ratio(sum(r["j"]["supported_sentences"] or 0 for r in pool), sum(r["j"]["cited_sentences"] or 0 for r in pool))


def correct_conditions(rows):
    pool = [r for r in rows if r["expected"] in BRANCHING]
    good = sum((r["type"] == "conditional_answer" and r["j"]["conditions_match"] is True)
               or (r["type"] == "clarify" and r["j"]["asks_branch_attribute"] is True) for r in pool)  # fmt: skip
    return ratio(good, len(pool))


def useful_question(rows):
    pool = [r for r in rows if r["type"] == "clarify"]
    return ratio(sum(r["j"]["asks_branch_attribute"] is True for r in pool), len(pool))


def right_referral(rows):
    pool = [r for r in rows if r["type"] == "abstain"]
    return ratio(sum(r["j"]["right_referral"] is True for r in pool), len(pool))


def answered_replies(rows):
    """The base of the wrong-group rate: how many answered replies a preset has (a count, not a rate)."""
    return float(sum(r["type"] in ANSWERED and r["j"]["wrong_group"] is not None for r in rows))


def referral_per_case(rows):
    """Cases labelled abstain whose reply is a referral to the right office or next step / all cases labelled abstain."""
    pool = [r for r in rows if r["expected"] == "abstain"]
    return ratio(sum(r["type"] == "abstain" and r["j"]["right_referral"] is True for r in pool), len(pool))


METRICS = {"fact coverage": fact_coverage, "answered (answer cases)": answered_share, "coverage when answered": coverage_when_answered,
           "wrong-fact rate": wrong_fact, "wrong-group rate": wrong_group, "answered replies (wrong-group base)": answered_replies,
           "citation support": citation_support, "correct conditions (branching)": correct_conditions,
           "useful question": useful_question, "right referral": right_referral,
           "right referral (per abstain case)": referral_per_case}  # fmt: skip


def kappa(pairs: list[tuple]) -> float | None:
    """Cohen's kappa over (a, b) label pairs. [(1,1),(0,0),(1,0),(0,0)] -> 0.5."""
    if not pairs:
        return None
    n, labels = len(pairs), {x for p in pairs for x in p}
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == lab for a, _ in pairs) / n) * (sum(b == lab for _, b in pairs) / n) for lab in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def field_pairs(main: dict, other: dict, items: dict) -> dict[str, list[tuple]]:
    out = defaultdict(list)
    for i, b in other.items():
        a = main.get(i)
        if not a:
            continue
        for x, y in zip(a.get("facts") or [], b.get("facts") or []):
            out["facts (per fact)"].append((x, y))
        for field in ("wrong_group", "conditions_match", "asks_branch_attribute", "right_referral"):
            if a.get(field) is not None and b.get(field) is not None:
                out[field].append((a[field], b[field]))
        if items[i]["reply_type"] in ANSWERED and (a.get("cited_sentences") or b.get("cited_sentences")):
            full = lambda j: (j.get("supported_sentences") or 0) == (j.get("cited_sentences") or 0)  # noqa: E731
            out["all cited sentences supported"].append((full(a), full(b)))
    return out


def main() -> int:
    key = {k["id"]: k for k in load(RAW / "key.jsonl")}
    judged = {j["id"]: j for f in sorted((RAW / "judgments").glob("*.jsonl")) for j in load(f)}
    lines = ["# Evaluator v3: answer quality of saved replies (post hoc, LLM judge, A36)", "",
             "Judge: fresh `claude-code:claude-opus-5-5` subagents, blind to preset names, items shuffled; prompt "
             "`Sources/evaluation/judge_v3_prompt.md` (frozen before any test item was judged). Not pre-registered as an "
             "evaluator: it computes the pre-registered correctness comparison post hoc.", ""]  # fmt: skip
    comparisons = []
    for split in ("test", "dev"):
        items = {i["id"]: i for i in load(RAW / f"items_{split}.jsonl")}
        cases = {c["case_id"]: c for c in hyu_suite.load_cases(split)}
        per = defaultdict(dict)  # preset -> case_id -> record
        for i, item in items.items():
            if i in judged:
                k = key[i]
                per[k["preset"]][k["case_id"]] = {"expected": cases[k["case_id"]]["expected_behavior"], "type": item["reply_type"], "j": judged[i]}
        missing = len(items) - sum(len(v) for v in per.values())
        table = [{"preset": p, "cases": len(per[p]), **{m: f(list(per[p].values())) for m, f in METRICS.items()}} for p in PRESETS]
        with (OUT / f"metrics_{split}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
        name = "test-1 (121 cases)" if split == "test" else "dev (47 cases, validation)"
        lines += [f"## {name}" + (f": {missing} items not judged" if missing else ""), "", "| Preset | " + " | ".join(METRICS) + " |",
                  "|---|" + "---|" * len(METRICS)]  # fmt: skip
        lines += ["| " + r["preset"] + " | " + " | ".join("n/a" if r[m] is None else f"{r[m]:.3f}" for m in METRICS) + " |" for r in table]
        lines.append("")
        if split == "test":
            for other in ("B0_BASIC_DENSE_RAG", "R16_PROMPTED_CONDITIONAL"):
                qids = sorted(set(per["A0_AAES"]) & set(per[other]))
                for m, f in METRICS.items():
                    if f is answered_replies:
                        continue
                    a, b = [per["A0_AAES"][q] for q in qids], [per[other][q] for q in qids]
                    if f(a) is None or f(b) is None:
                        continue
                    res = paired_compare(a, b, lambda rows, f=f: f(rows) or 0.0)
                    comparisons.append({"comparison": f"A0 vs {other.split('_')[0]}", "metric": m, **res})
            # Pre-registered comparison 2 (PLAYBOOK): A0 vs the best baseline R15 on correctness, unconditional slice,
            # non-inferiority margin 3 points. Correctness here = v3 fact coverage; non-inferior iff the CI's lower bound > -0.03.
            uncond = sorted(q for q in set(per["A0_AAES"]) & set(per["R15_SELF_QUERY"]) if cases[q].get("slice") == "unconditional")
            res = paired_compare([per["A0_AAES"][q] for q in uncond], [per["R15_SELF_QUERY"][q] for q in uncond], lambda rows: fact_coverage(rows) or 0.0)
            comparisons.append({"comparison": "PREREG 2: A0 vs R15, unconditional (non-inferiority -0.03: " +
                                ("met" if res["ci_low"] > -0.03 else "not met") + ")", "metric": "fact coverage", **res})  # fmt: skip
    with (OUT / "comparisons.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["comparison", "metric", "diff", "ci_low", "ci_high", "p", "cases"])
        writer.writeheader()
        writer.writerows(comparisons)
    lines += ["## Paired comparisons on test-1 (bootstrap 95% CI, permutation p; post hoc, not Holm-corrected)", "",
              "| Comparison | Metric | diff | 95% CI | p |", "|---|---|---|---|---|"]  # fmt: skip
    lines += [f"| {c['comparison']} | {c['metric']} | {c['diff']:+.3f} | [{c['ci_low']:+.3f}, {c['ci_high']:+.3f}] | {c['p']:.4f} |" for c in comparisons]

    items_dev = {i["id"]: i for i in load(RAW / "items_dev.jsonl")}
    second = {j["id"]: j for f in sorted((RAW / "validation_judgments").glob("*.jsonl")) for j in load(f)}
    pairs = field_pairs(judged, second, items_dev)
    validation = {"items": len(second), "second_judge": "claude-code:claude-sonnet-5-5",
                  "kappa": {f: {"kappa": kappa(p), "pairs": len(p), "agreement": sum(a == b for a, b in p) / len(p)} for f, p in pairs.items() if p}}  # fmt: skip
    human = REPORT_DIR / "notes" / "quality_human_check.csv"
    rows = [r for r in csv.DictReader(open(human)) if any(r[c].strip() for c in r if c.startswith(("facts", "wrong_group")))] if human.exists() else []
    if rows:
        def yn(v):
            v = v.strip().lower()
            return None if not v else v.startswith("y")

        hp = defaultdict(list)
        for r in rows:
            j = judged.get(r["id"]) or {}
            for x, y in zip([f.strip() for f in r["facts (correct/wrong/missing per fact, ; separated)"].split(";") if f.strip()], j.get("facts") or []):
                hp["facts (per fact)"].append((x, y))
            for col, field in (("wrong_group (yes/no)", "wrong_group"), ("conditions_match (yes/no, conditional only)", "conditions_match"),
                               ("asks_branch_attribute (yes/no, clarify only)", "asks_branch_attribute"), ("right_referral (yes/no, abstain only)", "right_referral")):
                if yn(r[col]) is not None and j.get(field) is not None:
                    hp[field].append((yn(r[col]), j[field]))
        validation["human"] = {f: {"agreement": sum(a == b for a, b in p) / len(p), "pairs": len(p)} for f, p in hp.items() if p}
    (OUT / "validation.json").write_text(json.dumps(validation, indent=1) + "\n")
    lines += ["", "## Validation on dev", "", f"Second judge ({validation['second_judge']}, {validation['items']} dev items, blind to the first):", "",
              "| Field | kappa | agreement | pairs |", "|---|---|---|---|"]  # fmt: skip
    for f, v in validation["kappa"].items():
        k = "n/a" if v["kappa"] is None else f"{v['kappa']:.3f}"
        lines.append(f"| {f} | {k} | {v['agreement']:.3f} | {v['pairs']} |")
    if "human" in validation:
        lines += ["", "Human check (20 dev items): " + "; ".join(f"{f} {v['agreement']:.2f} ({v['pairs']})" for f, v in validation["human"].items())]
    else:
        lines += ["", "Human check: `Report/notes/quality_human_check.csv` not filled in yet."]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
