"""Deterministic label checks for G4 (PLAYBOOK A33 step c). Nothing is fixed: violations go to verification.

Run from Sources/:
  python -m labeling.checks data/HYU/labels/merged.jsonl --out data/HYU/labels/violations.jsonl

One output line per violation: {"case_id", "check", "detail"}. Excluded cases are skipped.
The checks (GUIDELINES v1.3 rule in brackets):
  behavior       unanswerable / external_only / unanswerable_unreadable / korean_only -> abstain;
                 partial -> abstain or answer (the answer must name the gap: left to the verifier)  [9.1, 10.3, 11.2]
  branches       conditional_answer needs >= 1 branch attribute and <= 2 branches; clarify needs > 2 when the
                 gold spans carry branch marks  [11.6]
  unstated       answer must have no unstated branch attribute (branch_attributes, span branch marks, or gold
                 evidence from both campuses while campus is unstated)  [9.3, 11.4]
  facts          each required fact shares >= half of its content-word stems with the gold spans (facts stating
                 an absence or the answer's shape, "not described", "depends on the campus", are skipped)  [9.1]
  profile        stated_profile values equal gold_profile values; stale_update only on multi_session; a
                 multi_session update without stale_update  [11.7]
  campus         a campus-scoped gold span that applies to the profile comes from the profile's campus, unless
                 campus is an unstated branch attribute  [11.4]
  term           a year named in the question appears in the gold spans or their documents' dates  [10.1, 9.8]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from labeling._snapshot import DEFAULT_SNAPSHOT_ID, load_snapshot_rows
from labeling.validate import _has_stated_update

ABSTAIN_ONLY = ("unanswerable", "external_only", "unanswerable_unreadable", "korean_only")
WORD = re.compile(r"[a-z0-9][a-z0-9-]+")
# Facts that state what the corpus lacks ("the deadline is not described"): no span can show them.
ABSENCE = re.compile(r"\b(?:not|no|never)\s+(?:\w+\s+){0,2}(?:described|stated|mentioned|given|listed|found|available|specified|included|covered)\b|missing", re.I)
# Facts about the answer's shape, not the corpus ("depends on the campus", "should confirm with OIA"): no span shows them.
META = re.compile(r"\b(?:depends?|depending|differs?|varies|vary|should confirm|should check|omits?|extracted)\b", re.I)
YEAR = re.compile(r"\b20[2-3]\d\b")
STOP = set("""this that with from have must will they their there what when where which about into than then them
also only other each such more most some does were been being your students student hanyang university""".split())
FACT_SHARE = 0.5  # shortcut: word overlap, not entailment; the verifier judges every flagged fact


def _words(text: str) -> set[str]:
    """Content-word stems (first 5 letters), so "applies" and "application" match."""
    return {w[:5] for w in WORD.findall(text.lower()) if len(w) >= 4 and w not in STOP}


def _branch_values(case: dict) -> list[dict]:
    seen: list[dict] = []
    for span in case["gold_evidence"]:
        if span.get("branch") and span["branch"] not in seen:
            seen.append(span["branch"])
    return seen


def check_case(case: dict, documents: dict[str, dict]) -> list[tuple[str, str]]:
    """Returns [(check, detail)]. Example: an answerable case labelled clarify with branch_attributes ["visa"] and
    a stated visa gives [("branches", "clarify with 1 branch-marked value(s); clarify needs > 2")] when its
    gold spans carry one branch mark."""
    out: list[tuple[str, str]] = []
    ans, beh, stated, gold = case["answerability"], case["expected_behavior"], case["stated_profile"], case["gold_profile"]
    branches, attrs = _branch_values(case), case["branch_attributes"]

    if ans in ABSTAIN_ONLY and beh != "abstain":
        out.append(("behavior", f"{ans} must be abstain, not {beh}"))
    if ans == "partial" and beh not in ("abstain", "answer"):
        out.append(("behavior", f"partial must be abstain or answer, not {beh}"))

    if beh == "conditional_answer":
        if not attrs:
            out.append(("branches", "conditional_answer without a branch attribute"))
        if len(branches) > 2:
            out.append(("branches", f"conditional_answer with {len(branches)} branch-marked values; > 2 is clarify"))
        if not branches and len(attrs) > 1:
            out.append(("branches", f"conditional_answer on {attrs} without branch marks: branch count unknown"))
    if beh == "clarify" and branches and len(branches) <= 2:
        out.append(("branches", f"clarify with {len(branches)} branch-marked value(s); clarify needs > 2"))

    spans = [(s, documents.get(s["doc_id"])) for s in case["gold_evidence"]]
    if beh == "answer":
        unstated = sorted({a for a in attrs if a not in stated} | {a for b in branches for a in b if a not in stated})
        if unstated:
            out.append(("unstated", f"answer with unstated branch attribute(s) {unstated}"))
        campuses = {d["campus"] for s, d in spans if d and s.get("applies_to_gold_profile", True)}
        if "campus" not in stated and len(campuses) > 1 and case["condition_scope"] == "campus":
            out.append(("unstated", "answer with gold evidence from both campuses while campus is unstated"))

    text = " ".join(d["text"][s["char_start"]:s["char_end"]] for s, d in spans if d)
    gold_words = _words(text)
    for fact in case["required_facts"]:
        words = _words(fact)
        if words and not ABSENCE.search(fact) and not META.search(fact) and len(words & gold_words) < FACT_SHARE * len(words):
            out.append(("facts", f"{len(words & gold_words)}/{len(words)} content words in the gold spans: {fact[:120]}"))

    for attr, value in stated.items():
        if gold.get(attr) != value:
            out.append(("profile", f"stated {attr}={value} but gold_profile has {gold.get(attr)}"))
    if case.get("stale_update") and case["slice"] != "multi_session":
        out.append(("profile", "stale_update outside the multi_session slice"))
    if _has_stated_update(case) and not case.get("stale_update"):
        out.append(("profile", "multi_session update in the history but no stale_update: true (11.7)"))

    if case["condition_scope"] == "campus" and not ("campus" in attrs and "campus" not in stated):  # a campus branch
        for s, d in spans:
            if d and s.get("applies_to_gold_profile", True) and d["campus"] != gold.get("campus"):
                out.append(("campus", f"span {s['doc_id'][:8]} is {d['campus']} but the profile campus is {gold.get('campus')}"))

    years = set(YEAR.findall(case["question"]))
    found = set(YEAR.findall(text)) | {y for _, d in spans if d for y in YEAR.findall(f"{d.get('post_date') or ''} {d.get('title', '')}")}
    if years - found and ans in ("answerable", "partial"):
        out.append(("term", f"question names {sorted(years - found)} but no gold span or its document shows that year"))
    return out


def run(cases: list[dict], documents: dict[str, dict]) -> list[dict]:
    return [{"case_id": c["case_id"], "check": check, "detail": detail}
            for c in cases if "exclude" not in c for check, detail in check_case(c, documents)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("merged", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.merged.open(encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    documents = {row["doc_id"]: row for row in load_snapshot_rows(DEFAULT_SNAPSHOT_ID)}
    violations = run(cases, documents)
    args.out.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in violations), encoding="utf-8")
    by_check: dict[str, int] = {}
    for v in violations:
        by_check[v["check"]] = by_check.get(v["check"], 0) + 1
    print(json.dumps({"cases": len(cases), "violations": len(violations), "cases_flagged": len({v["case_id"] for v in violations}),
                      "by_check": by_check}, indent=2))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
