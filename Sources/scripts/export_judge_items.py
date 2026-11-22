"""Evaluator v3 (A36): judge items from SAVED replies, blind to preset names. No system is re-run.

Run from Sources/:
  python scripts/export_judge_items.py   # -> Report/results/quality_v3/raw/items_{dev,test}.jsonl and key.jsonl

One item per (preset, case) for B0, R15, R16, A0, G0, G1: the question, the label (gold profile, branch attributes,
required facts, gold and inapplicable evidence text), the v2 reply type, the reply, and the text of every cited chunk.
Cited chunks are mapped to the reply's [E#] markers when the counts match (the saved records keep the cited chunks in
order but not their labels); otherwise they are listed as C1, C2, ... Labels are read with the runner's reader. Items are
shuffled with a fixed seed; key.jsonl maps item ids back to preset and case and is never given to a judge.
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import RESULTS_DIR  # noqa: E402

PRESETS = ("B0_BASIC_DENSE_RAG", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL", "A0_AAES", "G0_CLOSED_BOOK", "G1_ORACLE_CONTEXT")
RUNS = {"dev": "dev-02", "test": "test-final"}
OUT = RESULTS_DIR / "quality_v3" / "raw"  # gitignored (Report/results/*/raw/): replies and label text


def span_text(docs: dict, chunk: dict, limit: int) -> str:
    doc = docs.get(chunk["doc_id"])
    if not doc:
        return ""
    return " ".join(doc["text"][a:b] for a, b in chunk.get("source_spans") or [])[:limit]


def label_text(docs: dict, spans: list[dict], limit: int) -> str:
    return " | ".join(docs[s["doc_id"]]["text"][s["char_start"]:s["char_end"]] for s in spans if s["doc_id"] in docs)[:limit]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    keys = []
    for split, run_id in RUNS.items():
        cases = {c["case_id"]: c for c in hyu_suite.load_cases(split)}
        docs = {r["doc_id"]: r for r in load_jsonl(hyu_suite.snapshot_dir(next(iter(cases.values()))["snapshot_id"]) / "documents.jsonl")}
        run = RESULTS_DIR / run_id
        v2 = {(r["preset"], r["qid"]): r["label"] for r in load_jsonl(run / "reply_actions_v2.jsonl")}
        items = []
        for preset in PRESETS:
            for rec in load_jsonl(run / "raw" / "hyu" / split / f"{preset}__-.jsonl"):
                if rec.get("status") != "completed" or rec["qid"] not in cases:
                    continue
                case, reply = cases[rec["qid"]], rec.get("answer") or ""
                cited = rec.get("cited") or []
                labels = sorted({int(m) for m in re.findall(r"\[E(\d+)\]", reply)})
                names = [f"E{n}" for n in labels] if len(labels) == len(cited) else [f"C{i}" for i in range(1, len(cited) + 1)]
                items.append({"split": split, "case_id": rec["qid"], "preset": preset, "question": case["question"],
                              "session_history": [t.get("text") for t in case.get("session_history") or []],
                              "gold_profile": case.get("gold_profile"), "branch_attributes": case.get("branch_attributes") or [],
                              "required_facts": case.get("required_facts") or [],
                              "gold_evidence": label_text(docs, case.get("gold_evidence") or [], 1800),
                              "inapplicable_evidence": label_text(docs, case.get("inapplicable_evidence") or [], 900),
                              "reply_type": v2.get((preset, rec["qid"]), "answer"), "reply": reply[:3000],
                              "cited_sources": [{"label": n, "text": span_text(docs, c, 1200)} for n, c in zip(names, cited)]})  # fmt: skip
        random.Random(36).shuffle(items)
        with (OUT / f"items_{split}.jsonl").open("w", encoding="utf-8") as handle:
            for i, item in enumerate(items, start=1):
                item_id = f"{split[0].upper()}{i:04d}"
                keys.append({"id": item_id, "split": split, "preset": item.pop("preset"), "case_id": item["case_id"]})
                handle.write(json.dumps({"id": item_id, **{k: v for k, v in item.items() if k != "split"}}, ensure_ascii=False) + "\n")
        print(split, len(items))
    (OUT / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
