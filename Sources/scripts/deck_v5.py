"""Deck v5 tables from saved runs and judgments only; no inference or network calls.

Run from Sources/: python scripts/deck_v5.py --help
Rates use cases as the denominator, except kept/needed, correct/required facts,
supported/cited sentences and the component rates defined in components_table.
Undefined rates and absent timings stay blank.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import re
import sys
import tempfile
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite, reply_action  # noqa: E402
from evaluation.metrics.stats import holm  # noqa: E402
from evaluation.reports import load_jsonl, paired_bootstrap, percentile  # noqa: E402
from scripts.export_judge_items import label_text, span_text  # noqa: E402

from app.config import PROJECT_ROOT, REPORT_DIR, RESULTS_DIR, resolve_stored_path  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v4"
PROMPT = PROJECT_ROOT / "evaluation" / "judge_v3_prompt.md"
BRANCHING = {"conditional_answer", "clarify"}
ANSWERED = {"answer", "conditional_answer"}
RESAMPLES, SEED = 10_000, 0


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p from the discordant counts. b = 9, c = 1 -> 22/1024 = 0.0215."""
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n) if n else 1.0


SELECTION_RULE = ("AP_* with kept >= 0.8 * kept(A0_AAES = RRRR); highest acceptable_rate; "
                  "ties: fewer llm_calls_mean, then preset name")


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"missing input: {path}")
    return load_jsonl(path)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ratio(num, den):
    return num / den if den else None


def student_dependent(case: dict) -> bool:
    return case["student_dependent"] if "student_dependent" in case else case["expected_behavior"] in BRANCHING


def case_score(case: dict, rec: dict, kind: str) -> dict:
    """Needed clarify -> conditional: kept=1; expected answer -> clarify: unneeded=1 unless acceptable."""
    acceptable = kind in case["acceptable_behaviors"]
    needed = case["expected_behavior"] in BRANCHING
    return {"acceptable": acceptable, "needed": needed, "kept": needed and kind in BRANCHING,
            "unneeded": not needed and kind in BRANCHING and not acceptable,
            "wrong_referral": kind == "abstain" and "abstain" not in case["acceptable_behaviors"],
            "student_dependent": student_dependent(case), "llm_calls": rec.get("llm_calls"),
            "seconds": rec["total_ms"] / 1000 if rec.get("total_ms") is not None else None}


def planned_presets(run: Path, splits: list[str]) -> set[str]:
    tasks = []
    manifest_path, status_path = run / "run_manifest.json", run / "status.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tasks.extend(manifest.get("tasks", []))
        for session in manifest.get("sessions", []):
            tasks.extend(session.get("tasks", []))
    if status_path.is_file():
        tasks.extend(json.loads(status_path.read_text(encoding="utf-8")))
    presets = set()
    for task in tasks:
        parts = task.split("/")
        if len(parts) == 3 and parts[0] == "hyu" and parts[1] in splits and parts[2].endswith("__-"):
            presets.add(parts[2].removesuffix("__-"))
    if not presets:
        raise ValueError(f"no planned HYU presets for {splits} in {run}: need run_manifest.json tasks or status.json keys")
    return presets


def load_runs(run_ids: list[str], splits: list[str]) -> tuple[dict, dict, dict]:
    """Latest completed record per file; reject conflicting records across runs instead of pooling repeats."""
    cases = {}
    for split in splits:
        labels = hyu_suite.load_cases(split)
        if not labels:
            raise ValueError(f"no cases for split {split}")
        for case in labels:
            key = (split, case["case_id"])
            if key in cases:
                raise ValueError(f"duplicate case: {key}")
            cases[key] = case
    records, types = defaultdict(dict), defaultdict(dict)
    for run_id in run_ids:
        run = RESULTS_DIR / run_id
        planned = planned_presets(run, splits)
        for preset in planned:
            records[preset]  # keep planned presets even when their raw files are absent
        cache_path = run / "reply_actions_v2.jsonl"
        cached = read_rows(cache_path) if cache_path.is_file() else []
        cache = {(r["preset"], r["qid"], r.get("reply_sha")): r["label"]
                 for r in cached}
        paths = sorted((run / "raw" / "hyu").glob("*/*__-.jsonl"))
        for path in paths:
            preset = path.name.removesuffix("__-.jsonl")
            split = path.parent.name
            if split not in splits or preset not in planned:
                continue
            latest = {r["qid"]: r for r in read_rows(path) if r.get("status") == "completed"}
            for qid, rec in latest.items():
                key = (split, qid)
                if key not in cases:
                    raise ValueError(f"{path}: unknown case {qid}")
                if key in records[preset] and records[preset][key] != rec:
                    raise ValueError(f"conflicting runs for {preset}, {key}; supply one version")
                records[preset][key] = rec
                sha = reply_action.reply_sha(rec.get("answer") or "")
                kind = cache.get((preset, qid, sha), cache.get((preset, qid, None)))
                if kind is not None:
                    if kind not in reply_action.LABELS:
                        raise ValueError(f"invalid v2 label: {preset}, {qid}: {kind}")
                    if key in types[preset] and types[preset][key] != kind:
                        raise ValueError(f"conflicting v2 labels for {preset}, {key}")
                    types[preset][key] = kind
    return cases, dict(records), dict(types)


def summarize(rows: list[dict]) -> dict:
    """Two needed cases, one kept -> kept_rate=1/2; one unneeded among four cases -> 1/4."""
    n, needed = len(rows), sum(r["needed"] for r in rows)
    seconds = [r["seconds"] for r in rows if r["seconds"] is not None]
    return {"cases": n, "acceptable_rate": ratio(sum(r["acceptable"] for r in rows), n),
            "needed": needed, "kept": sum(r["kept"] for r in rows),
            "kept_rate": ratio(sum(r["kept"] for r in rows), needed),
            "unneeded": sum(r["unneeded"] for r in rows), "unneeded_rate": ratio(sum(r["unneeded"] for r in rows), n),
            "wrong_referrals": sum(r["wrong_referral"] for r in rows),
            "wrong_referral_rate": ratio(sum(r["wrong_referral"] for r in rows), n),
            "seconds_median": median(seconds) if seconds else None}


def select_version(rows: list[dict]) -> dict:
    by_preset = {r["preset"]: r for r in rows}
    if "A0_AAES" not in by_preset:
        raise ValueError("selection needs A0_AAES (RRRR)")
    threshold = 0.8 * by_preset["A0_AAES"]["kept"]
    candidates = [r for r in rows if r["preset"].startswith("AP_")]
    eligible = [r for r in candidates if r["kept"] >= threshold]
    if any(r["llm_calls_mean"] is None for r in eligible):
        raise ValueError("selection needs llm_calls for every eligible AP_* candidate")
    choice = min(eligible, key=lambda r: (-r["acceptable_rate"], r["llm_calls_mean"], r["preset"])) if eligible else None
    return {"rule": SELECTION_RULE, "reference": by_preset["A0_AAES"], "minimum_kept": threshold,
            "candidates": [{**r, "eligible": r["kept"] >= threshold} for r in candidates],
            "choice": choice["preset"] if choice else None}


def complete_aaes_presets(cases: dict, records: dict, types: dict) -> list[str]:
    """Require every case and matching v2 label for A0_AAES and every planned AP_* preset."""
    presets = sorted(p for p in set(records) | {"A0_AAES"} if p == "A0_AAES" or p.startswith("AP_"))
    missing = {}
    for preset in presets:
        gaps = set(cases) - (set(records.get(preset, {})) & set(types.get(preset, {})))
        if gaps:
            missing[preset] = [f"{split}/{qid}" for split, qid in sorted(gaps)]
    if missing:
        raise ValueError(f"AAES tables need completed records and matching v2 labels for all cases; missing: {missing}")
    return presets


def ablation_table(run_ids: list[str], splits: list[str]) -> list[dict]:
    if set(splits) - {"dev", "dev2"}:
        raise ValueError("ablation and selection use dev/dev2 only")
    cases, records, types = load_runs(run_ids, splits)
    complete_aaes_presets(cases, records, types)
    table = []
    for preset, per in sorted(records.items()):
        if not per:
            continue
        if set(per) - set(types.get(preset, {})):
            raise ValueError(f"{preset}: missing v2 labels; finish reply_actions_v2.jsonl first")
        scores = [case_score(cases[k], rec, types[preset][k]) for k, rec in sorted(per.items())]
        summary = summarize(scores)
        calls = [s["llm_calls"] for s in scores]
        table.append({"preset": preset, **{k: summary[k] for k in
                      ("cases", "acceptable_rate", "needed", "kept", "kept_rate", "unneeded", "wrong_referrals")},
                      "llm_calls_mean": mean(calls) if all(c is not None for c in calls) else None,
                      "fresh_seconds_median": None})
    return table


def ablation(args) -> None:
    table = ablation_table(args.runs, args.splits)
    timings = defaultdict(list)
    if args.timing:
        with args.timing.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                seconds = float(row["seconds"])
                if not math.isfinite(seconds) or seconds < 0:
                    raise ValueError("timing seconds must be finite and nonnegative")
                timings[row["preset"]].append(seconds)
    for row in table:
        values = timings[row["preset"]]
        row["fresh_seconds_median"] = median(values) if values else None
    selection = {"runs": args.runs, "splits": args.splits, **select_version(table)}
    folder = OUT / "aaes_plus"
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "dev_ablation.csv", table)
    write_json(folder / "selection.json", selection)
    print(json.dumps(selection, indent=2))


def components_table(run_ids: list[str], splits: list[str]) -> list[dict]:
    """Pool all dev/dev2 cases once per A0_AAES/AP_* preset, with complete record/v2 coverage.

    Step 3 detail: choose aaes_plus.clarify_attribute, else the first branch_attributes
    entry. Count only cases with both a chosen detail and nonempty label branch_attributes;
    a hit means the chosen detail is in that label list. Hit rate = hits/detail cases.
    Step 3 split: predicted positive iff aaes_plus.branch_attributes is nonempty OR
    record action is CLARIFY/CONDITIONAL. Gold positive iff expected_behavior is in
    BRANCHING (case_score's needed). Precision = TP/(TP+FP), recall = TP/(TP+FN),
    F1 = 2*TP/(2*TP+FP+FN), counting every case, independent of the v2 reply type.
    Step 4: step4_expected_<gold>__predicted_<v2> holds each of the 4x4 counts,
    including zeros, in reply_action.LABELS order. Gold is expected_behavior, never
    acceptable_behaviors; v2 comes only from matching cached reply_actions_v2.jsonl
    labels. Correct = diagonal sum; accuracy = correct/all cases. Undefined rates
    are None (JSON null, CSV blank), including F1 when TP=FP=FN=0.
    """
    if set(splits) - {"dev", "dev2"}:
        raise ValueError("components use dev/dev2 only")
    cases, records, types = load_runs(run_ids, splits)
    presets = complete_aaes_presets(cases, records, types)
    table = []
    for preset in presets:
        detail_cases = detail_hits = tp = fp = fn = correct = 0
        confusion = {(gold, predicted): 0 for gold in reply_action.LABELS for predicted in reply_action.LABELS}
        for key, case in sorted(cases.items()):
            rec, kind = records[preset][key], types[preset][key]
            details = rec.get("aaes_plus") or {}
            branches = details.get("branch_attributes") or []
            chosen = details.get("clarify_attribute") or (branches[0] if branches else None)
            if chosen and case.get("branch_attributes"):
                detail_cases += 1
                detail_hits += chosen in case["branch_attributes"]
            predicted = bool(branches) or rec.get("action") in {"CLARIFY", "CONDITIONAL"}
            needed = case_score(case, rec, kind)["needed"]
            tp += predicted and needed
            fp += predicted and not needed
            fn += not predicted and needed
            confusion[(case["expected_behavior"], kind)] += 1
            correct += kind == case["expected_behavior"]
        table.append({"preset": preset, "cases": len(cases),
                      "step3_detail_cases": detail_cases, "step3_detail_hits": detail_hits,
                      "step3_detail_hit_rate": ratio(detail_hits, detail_cases),
                      "step3_split_tp": tp, "step3_split_fp": fp, "step3_split_fn": fn,
                      "step3_split_precision": ratio(tp, tp + fp), "step3_split_recall": ratio(tp, tp + fn),
                      "step3_split_f1": ratio(2 * tp, 2 * tp + fp + fn),
                      "step4_correct": correct, "step4_accuracy": ratio(correct, len(cases)),
                      **{f"step4_expected_{gold}__predicted_{predicted}": n
                         for (gold, predicted), n in confusion.items()}})
    return table


def components(args) -> None:
    table = components_table(args.runs, args.splits)
    folder = OUT / "aaes_plus"
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "components_v5.csv", table)
    write_json(folder / "components_v5.json", table)


def select(args) -> None:
    path = OUT / "aaes_plus" / "dev_ablation.csv"
    selection_path = path.with_name("selection.json")
    source = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.is_file() else {}
    if not source.get("runs") or not source.get("splits"):
        raise ValueError("selection needs source runs and splits in selection.json; rerun ablation first")
    expected = ablation_table(source["runs"], source["splits"])
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [{k: v if k == "preset" else float(v) if v else None for k, v in r.items()} for r in csv.DictReader(handle)]
    if [{**row, "fresh_seconds_median": None} for row in rows] != expected:
        raise ValueError("dev_ablation.csv does not match the complete source runs; rerun ablation first")
    selection = {"runs": source["runs"], "splits": source["splits"], "table_sha256": sha256(path), **select_version(rows)}
    write_json(selection_path, selection)
    print(json.dumps(selection, indent=2))


def paired_interval(a: list, b: list) -> dict:
    if len(a) != len(b):
        raise ValueError("paired interval needs identical case coverage")
    lo, hi = paired_bootstrap([x - y for x, y in zip(a, b)], RESAMPLES, SEED)
    return {"cases": len(a), "ours": mean(a) if a else None, "baseline": mean(b) if b else None,
            "difference": mean(a) - mean(b) if a else None, "ci_low": lo, "ci_high": hi}


def mcnemar(a: list, b: list, one_sided: bool) -> dict:
    wins = sum(x and not y for x, y in zip(a, b))
    losses = sum(y and not x for x, y in zip(a, b))
    p = mcnemar_exact(wins, losses)
    if one_sided and wins + losses:
        mass = math.comb(wins + losses, wins) / 2 ** (wins + losses)
        p = p / 2 if wins > losses else (1 + mass) / 2 if wins == losses else 1 - p / 2 + mass
    return {"ours_only": wins, "baseline_only": losses, "mcnemar_p": p,
            "mcnemar_alternative": "greater" if one_sided else "two-sided"}


def hypothesis(a: list, b: list, name: str) -> dict:
    return {**paired_interval(a, b), **mcnemar(a, b, one_sided=name != "H2")}


def decide_hypotheses(rows: dict) -> None:
    for name, adjusted in zip(("H1", "H2", "H3"), holm([rows[n]["mcnemar_p"] for n in ("H1", "H2", "H3")])):
        row = rows[name]
        row["p_holm"] = adjusted
        if row["ci_low"] is None:
            row["decision"] = "insufficient_cases"
        elif name == "H2":
            row["decision"] = "non_inferior" if row["ci_low"] > -0.10 else "not_demonstrated"
        else:
            row["decision"] = "superior" if row["difference"] > 0 and adjusted < 0.05 else "not_demonstrated"


def balanced_cases(cases: dict, records: dict, types: dict) -> tuple[list, list]:
    empty = sorted(p for p, per in records.items() if not per)
    if empty:
        raise ValueError(f"planned presets have no completed records for requested splits: {empty}")
    balanced, dropped = [], []
    for key in sorted(cases):
        missing = [p for p in sorted(records) if key not in records[p] or key not in types.get(p, {})]
        if missing:
            dropped.append({"split": key[0], "case_id": key[1], "missing_presets": missing})
        else:
            balanced.append(key)
    return balanced, dropped


def heldout(args) -> None:
    cases, records, types = load_runs(csv_list(args.run), args.splits)  # one or several runs, e.g. heldout-test3,heldout-test2
    for preset in (args.ours, args.aaes, args.conditional):
        if preset not in records:
            raise ValueError(f"preset not in run: {preset}")
    balanced, dropped = balanced_cases(cases, records, types)
    scores = {p: {k: case_score(cases[k], records[p][k], types[p][k]) for k in balanced} for p in records}
    dependent = [k for k in balanced if student_dependent(cases[k])]
    needed = [k for k in dependent if cases[k]["expected_behavior"] in BRANCHING]
    table = []
    for preset in sorted(scores):
        for split in args.splits:
            keys = [k for k in balanced if k[0] == split]
            slices = {"all": keys, "student_dependent": [k for k in keys if student_dependent(cases[k])]}
            for value in sorted({cases[k].get("slice") for k in keys if cases[k].get("slice") is not None}):
                if value not in slices:
                    slices[value] = [k for k in keys if cases[k].get("slice") == value]
            for label, pool in slices.items():
                table.append({"preset": preset, "split": split, "slice": label, **summarize([scores[preset][k] for k in pool])})
    specs = {"H1": (balanced, args.aaes, "acceptable"), "H2": (needed, args.aaes, "kept"),
             "H3": (dependent, args.conditional, "acceptable")}
    hypotheses = {}
    for name, (pool, baseline, metric) in specs.items():
        hypotheses[name] = {"baseline_preset": baseline, "metric": metric,
                            **hypothesis([scores[args.ours][k][metric] for k in pool], [scores[baseline][k][metric] for k in pool], name)}
    decide_hypotheses(hypotheses)
    secondary = []
    for baseline in dict.fromkeys((args.aaes, args.conditional)):
        for metric in ("unneeded", "wrong_referral", "seconds"):
            pool = [k for k in balanced if scores[args.ours][k][metric] is not None and scores[baseline][k][metric] is not None]
            a, b = [scores[args.ours][k][metric] for k in pool], [scores[baseline][k][metric] for k in pool]
            secondary.append({"baseline_preset": baseline, "metric": metric, **paired_interval(a, b),
                              **(mcnemar(a, b, False) if metric != "seconds" else {}),
                              "ours_median": median(a) if a else None, "baseline_median": median(b) if b else None})
    report = {"run": args.run, "splits": args.splits, "ours": args.ours, "presets": sorted(records),
              "annotation": "LLM-annotated; claims are relative comparisons only",
              "bootstrap": {"resamples": RESAMPLES, "seed": SEED, "confidence": 0.95},
              "rate_denominators": "kept/needed; acceptable, unneeded and wrong referrals/all cases in slice",
              "cases": len(balanced), "student_dependent_cases": len(dependent), "needed_dependent_cases": len(needed),
              "cases_by_split": {s: sum(k[0] == s for k in balanced) for s in args.splits}, "dropped_unbalanced": dropped,
              "hypotheses": hypotheses, "secondary": secondary,
              "decision_rules": {"H1_H3": "positive difference and one-sided McNemar Holm p < 0.05",
                                 "H2": "paired bootstrap 95% lower bound > -0.10; undefined without needed cases",
                                 "H2_p": "McNemar tests equality, not the -0.10 margin; its two-sided p is descriptive. "
                                          "Holm values cover H1-H3; H2's decision uses the specified CI rule."}}
    folder = OUT / "heldout"
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "reply_types.csv", table)
    write_json(folder / "hypotheses.json", report)


def judge_items(args) -> None:
    cases, records, types = load_runs(csv_list(args.run), args.splits)  # one or several runs, e.g. heldout-test3,heldout-test2
    presets = list(dict.fromkeys([p for p in args.presets if p != args.gold_preset] + [args.gold_preset]))
    if set(presets) - set(records):
        raise ValueError(f"presets missing from run: {sorted(set(presets) - set(records))}")
    balanced, dropped = balanced_cases(cases, records, types)
    docs, pools = {}, {"H": [], "G": []}
    for preset in presets:
        for key in balanced:
            rec = records[preset][key]
            kind = types[preset][key]
            if kind not in ANSWERED:
                continue
            case = cases[key]
            snapshot = case["snapshot_id"]
            if snapshot not in docs:
                docs[snapshot] = {d["doc_id"]: d for d in read_rows(hyu_suite.snapshot_dir(snapshot) / "documents.jsonl")}
            source = docs[snapshot]
            reply, cited = rec.get("answer") or "", rec.get("cited") or []
            markers = sorted({int(n) for n in re.findall(r"\[E(\d+)\]", reply)})
            names = [f"E{n}" for n in markers] if len(markers) == len(cited) else [f"C{i}" for i in range(1, len(cited) + 1)]
            item = {"question": case["question"], "session_history": [t.get("text") for t in case.get("session_history") or []],
                    "gold_profile": case.get("gold_profile"), "branch_attributes": case.get("branch_attributes") or [],
                    "required_facts": case.get("required_facts") or [],
                    "gold_evidence": label_text(source, case.get("gold_evidence") or [], 1800),
                    "inapplicable_evidence": label_text(source, case.get("inapplicable_evidence") or [], 900),
                    "reply_type": kind, "reply": reply[:3000],
                    "cited_sources": [{"label": n, "text": span_text(source, c, 1200)} for n, c in zip(names, cited)]}
            pools["G" if preset == args.gold_preset else "H"].append((item, {"preset": preset, "split": key[0], "case_id": key[1]}))
    outputs, keys = {}, []
    for prefix, pool in pools.items():
        random.Random(SEED).shuffle(pool)
        outputs[prefix] = []
        for i, (item, key) in enumerate(pool, 1):
            item_id = f"{prefix}{i:04d}"
            outputs[prefix].append({"id": item_id, **item})
            keys.append({"id": item_id, **key})
    folder = OUT / "heldout" / "judge"
    folder.mkdir(parents=True, exist_ok=True)
    write_jsonl(folder / "items.jsonl", outputs["H"])
    write_jsonl(folder / "items_gold.jsonl", outputs["G"])
    write_jsonl(folder / "key.jsonl", keys)
    write_json(folder / "coverage.json", {"run": args.run, "splits": args.splits, "presets": sorted(records),
                                        "cases": len(balanced), "dropped_unbalanced": dropped})
    print(f"blind items: {len(outputs['H'])}; gold items: {len(outputs['G'])}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_judgments(folder: Path, gold: bool) -> tuple[list, list, Path, list]:
    """Stage arbitrary shards into the existing strict merger's three-batch layout."""
    from scripts import deck_v4_followup

    items_path = folder / ("items_gold.jsonl" if gold else "items.jsonl")
    items = read_rows(items_path)
    if len({r["id"] for r in items}) != len(items):
        raise ValueError("duplicate item ids")
    parts = sorted(folder.glob("judgments_gold_*.jsonl" if gold else "judgments_*.jsonl"))
    if not gold:
        parts = [p for p in parts if p.name != "judgments_gold.jsonl" and not p.name.startswith("judgments_gold_")]
    if not parts:
        raise ValueError("no judgment batches; use judgments_*.jsonl (gold: judgments_gold_*.jsonl)")
    rows = [r for path in parts for r in read_rows(path)]
    # The existing merger owns exact coverage, JUDGE_KEYS and fact alignment checks.
    original_out = deck_v4_followup.OUT
    with tempfile.TemporaryDirectory(prefix="deck-v5-judge-") as temp:
        staging = Path(temp) / "judge"
        staging.mkdir()
        write_jsonl(staging / "items.jsonl", items)
        for i in range(1, 4):
            write_jsonl(staging / f"judgments_part{i}.jsonl", rows if i == 1 else [])
        try:
            deck_v4_followup.OUT = Path(temp)
            with redirect_stdout(io.StringIO()):
                deck_v4_followup.merge_judgments()
            merged = read_rows(staging / "judgments.jsonl")
        finally:
            deck_v4_followup.OUT = original_out
    return items, merged, items_path, parts


def content_stat(rows: list[dict], metric: str):
    """Two replies with 1/1 and 1/3 correct facts -> coverage=2/4, not mean(1, 1/3)."""
    if metric == "facts_covered":
        return ratio(sum(r["facts"].count("correct") for r in rows), sum(len(r["facts"]) for r in rows))
    if metric == "wrong_fact_rate":
        return ratio(sum("wrong" in r["facts"] for r in rows), len(rows))
    if metric == "wrong_group_rate":
        return ratio(sum(r["wrong_group"] for r in rows), len(rows))
    return ratio(sum(r["supported_sentences"] for r in rows), sum(r["cited_sentences"] for r in rows))


def content_interval(rows: list[dict], metric: str) -> dict:
    value = content_stat(rows, metric)
    lo = hi = None
    if value is not None and rows:
        if metric in ("wrong_fact_rate", "wrong_group_rate"):
            values = ["wrong" in r["facts"] if metric == "wrong_fact_rate" else r["wrong_group"] for r in rows]
            lo, hi = paired_bootstrap(values, RESAMPLES, SEED)
        else:
            # The shared mean bootstrap cannot express a ratio with undefined resamples.
            rng = random.Random(SEED)
            draws = []
            while len(draws) < RESAMPLES:
                draw = content_stat(rng.choices(rows, k=len(rows)), metric)
                if draw is not None:
                    draws.append(draw)
            lo, hi = percentile(draws, 0.025), percentile(draws, 0.975)
    return {metric: value, f"{metric}_ci_low": lo, f"{metric}_ci_high": hi}


def score_content(args) -> None:
    folder = args.dir
    items, judged, items_path, parts = merge_judgments(folder, args.gold)
    all_keys = read_rows(folder / "key.jsonl")
    if len({k["id"] for k in all_keys}) != len(all_keys):
        raise ValueError("duplicate key ids")
    keys = {k["id"]: k for k in all_keys}
    item_by_id = {i["id"]: i for i in items}
    prefix = "G" if args.gold else "H"
    selected_keys = {i for i in keys if i.startswith(prefix)}
    if set(item_by_id) != selected_keys:
        raise ValueError("item ids do not match key.jsonl coverage")
    keyed_cases = [(keys[i]["preset"], keys[i]["split"], keys[i]["case_id"]) for i in item_by_id]
    if len(keyed_cases) != len(set(keyed_cases)):
        raise ValueError("duplicate preset/case in key.jsonl")
    cases = {split: {c["case_id"]: c for c in hyu_suite.load_cases(split)} for split in {keys[i]["split"] for i in item_by_id}}
    groups = defaultdict(list)
    for j in judged:
        key, item = keys[j["id"]], item_by_id[j["id"]]
        if item["reply_type"] not in ANSWERED:
            raise ValueError(f"{j['id']}: content scoring needs an answered item")
        if type(j["wrong_group"]) is not bool or any(type(j[f]) is not int or j[f] < 0 for f in ("cited_sentences", "supported_sentences")):
            raise ValueError(f"{j['id']}: invalid content judgment types")
        if j["supported_sentences"] > j["cited_sentences"]:
            raise ValueError(f"{j['id']}: supported_sentences exceeds cited_sentences")
        if key["case_id"] not in cases[key["split"]]:
            raise ValueError(f"unknown keyed case: {key}")
        groups[(key["preset"], "all")].append(j)
        if student_dependent(cases[key["split"]][key["case_id"]]):
            groups[(key["preset"], "student_dependent")].append(j)
    scores = []
    for preset in sorted({p for p, _ in groups}):
        for slice_name in ("all", "student_dependent"):
            rows = groups[(preset, slice_name)]
            row = {"preset": preset, "slice": slice_name, "cases": len(rows),
                   "required_facts": sum(len(r["facts"]) for r in rows), "correct_facts": sum(r["facts"].count("correct") for r in rows),
                   "wrong_fact_replies": sum("wrong" in r["facts"] for r in rows), "wrong_group_replies": sum(r["wrong_group"] for r in rows),
                   "cited_sentences": sum(r["cited_sentences"] for r in rows), "supported_sentences": sum(r["supported_sentences"] for r in rows)}
            for metric in ("facts_covered", "wrong_fact_rate", "wrong_group_rate", "citation_support"):
                row.update(content_interval(rows, metric))
            scores.append(row)
    suffix = "_gold" if args.gold else ""
    merged_path = folder / f"judgments{suffix}.jsonl"
    if not scores:
        raise ValueError("no answered items to score")
    write_jsonl(merged_path, judged)
    write_csv(folder / f"content_scores{suffix}.csv", scores)
    write_json(folder / f"content{suffix}.json", {
        "annotation": "LLM-annotated; claims are relative comparisons only", "gold": args.gold,
        "bootstrap": {"resamples": RESAMPLES, "seed": SEED, "unit": "case", "confidence": 0.95},
        "definitions": {"facts_covered": "correct/required facts", "wrong_fact_rate": "replies with >=1 wrong fact/answered replies",
                        "wrong_group_rate": "wrong-group replies/answered replies", "citation_support": "supported/cited sentences",
                        "bootstrap_ratios": "resample all cases together; redraw zero-denominator samples; undefined rates stay null"},
        "prompt_sha256": sha256(PROMPT), "items_sha256": sha256(items_path), "key_sha256": sha256(folder / "key.jsonl"),
        "judgments_sha256": sha256(merged_path), "judgment_parts_sha256": {p.name: sha256(p) for p in parts}, "scores": scores})


def csv_list(value: str) -> list[str]:
    values = value.split(",")
    if any(not v or v != v.strip() for v in values) or len(values) != len(set(values)):
        raise argparse.ArgumentTypeError("use a comma-separated list of distinct nonempty names")
    return values


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    ab = commands.add_parser("ablation", help="write dev ablation table and select AP_*")
    ab.add_argument("--runs", required=True, type=csv_list)
    ab.add_argument("--splits", default="dev,dev2", type=csv_list)
    ab.add_argument("--timing", type=resolve_stored_path)
    ab.set_defaults(func=ablation)
    comp = commands.add_parser("components", help="Step 3 detail/split scores and Step 4 reply-type confusion")
    comp.add_argument("--runs", required=True, type=csv_list)
    comp.add_argument("--splits", default="dev,dev2", type=csv_list)
    comp.set_defaults(func=components)
    commands.add_parser("select", help="repeat fixed selection from dev_ablation.csv").set_defaults(func=select)
    held = commands.add_parser("heldout", help="balanced reply types and paired hypotheses")
    held.add_argument("--run", required=True)
    held.add_argument("--splits", default="test3,test2", type=csv_list)
    held.add_argument("--ours", required=True)
    held.add_argument("--aaes", default="A0_AAES")
    held.add_argument("--conditional", default="R16_PROMPTED_CONDITIONAL")
    held.set_defaults(func=heldout)
    judge = commands.add_parser("judge-items", help="blind answered replies, with G1 separate")
    judge.add_argument("--run", required=True)
    judge.add_argument("--splits", default="test3,test2", type=csv_list)
    judge.add_argument("--presets", required=True, type=csv_list)
    judge.add_argument("--gold-preset", default="G1_ORACLE_CONTEXT")
    judge.set_defaults(func=judge_items)
    content = commands.add_parser("score-content", help="validate judge batches and score answered replies")
    content.add_argument("--dir", type=resolve_stored_path, default=OUT / "heldout" / "judge")
    content.add_argument("--gold", action="store_true", help="read judgments_gold_*.jsonl; write separate *_gold outputs")
    content.set_defaults(func=score_content)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"{args.command}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
