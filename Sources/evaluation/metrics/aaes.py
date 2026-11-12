"""AAES metrics on the HYU labels (definitions: docs/aaes_spec.md "Metrics (P8)").

A chunk is {"doc_id", "source_spans": [[start, end], ...]} with half-open snapshot offsets. A rate whose
denominator is 0 is undefined (None).
"""

from __future__ import annotations

from evaluation.metrics.gate import gate_metrics

BEHAVIORS = ("answer", "conditional_answer", "clarify", "abstain")
ANSWERED = ("answer", "conditional_answer")
ACTION_TO_BEHAVIOR = {"ANSWER": "answer", "CONDITIONAL": "conditional_answer", "CLARIFY": "clarify", "CONFIRM": "clarify",
                      "ABSTAIN": "abstain"}  # fmt: skip


def label_action(action: str | None, outcome: str | None = None) -> str:
    """AAES action -> label behaviour; without an action, answered -> answer, anything else -> abstain.

    "CONFIRM" -> "clarify" (both ask the student); (None, "answered") -> "answer". An ANSWER/CONDITIONAL decision
    whose generation still abstained ("CONDITIONAL", "insufficient_context") -> "abstain": that is what the student got.
    """
    if action in ("ANSWER", "CONDITIONAL") and outcome != "answered":
        return "abstain"
    if action:
        return ACTION_TO_BEHAVIOR[action]
    return "answer" if outcome == "answered" else "abstain"


def _overlaps(chunk: dict, spans: list[dict]) -> bool:
    return any(s["doc_id"] == chunk["doc_id"] and start < s["char_end"] and s["char_start"] < end
               for s in spans for start, end in chunk.get("source_spans") or [])  # fmt: skip


def chunk_class(chunk: dict, case: dict) -> str:
    """gold > inapplicable > outdated > other. D1 [150, 250) vs gold D1 [100, 200) -> "gold"; [200, 300) -> "other"."""
    for name, field in (("gold", "gold_evidence"), ("inapplicable", "inapplicable_evidence"), ("outdated", "outdated_evidence")):
        if _overlaps(chunk, case.get(field) or []):
            return name
    return "other"


def applicable_recall_at(ranked: list[dict], case: dict, k: int) -> float | None:
    """Share of gold spans overlapped by a top-k chunk. 2 gold spans, 1 covered in the top 2 -> 0.5."""
    gold = case.get("gold_evidence") or []
    if not gold:
        return None
    top = ranked[:k]
    return sum(any(_overlaps(c, [span]) for c in top) for span in gold) / len(gold)


def inapplicable_intrusion_at(ranked: list[dict], case: dict, k: int) -> float | None:
    """Share of the top-k chunks that are inapplicable. [bad, gold] at k = 2 -> 0.5."""
    if not case.get("inapplicable_evidence") or k <= 0:
        return None
    top = ranked[:k]
    return sum(chunk_class(c, case) == "inapplicable" for c in top) / len(top) if top else None


def cited_error(cited: list[dict], case: dict, behavior: str, kind: str) -> int | None:
    """AER (kind "inapplicable") or outdated-answer (kind "outdated") for one case.

    None if the case was not answered or has no spans of that kind; else 1 if a cited chunk has that class.
    """
    field = {"inapplicable": "inapplicable_evidence", "outdated": "outdated_evidence"}[kind]
    if behavior not in ANSWERED or not case.get(field):
        return None
    return int(any(chunk_class(c, case) == kind for c in cited))


def flag_rate(rows: list[tuple[bool, str]]) -> float | None:
    """(flag, behaviour) per case; the share of answered cases with the flag. [(T, answer), (F, cond), (T, abstain)] -> 0.5."""
    answered = [flag for flag, behavior in rows if behavior in ANSWERED]
    return sum(answered) / len(answered) if answered else None


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def action_metrics(rows: list[tuple[str, list[str], str]]) -> dict:
    """rows: (expected_behavior, acceptable_behaviors, predicted). Hand-computed example in the tests (macro-F1 1/4)."""
    confusion = {e: {p: 0 for p in BEHAVIORS} for e in BEHAVIORS}
    for expected, _, predicted in rows:
        confusion[expected][predicted] += 1
    f1s = []
    for b in BEHAVIORS:
        tp = confusion[b][b]
        support, predicted = sum(confusion[b].values()), sum(confusion[e][b] for e in BEHAVIORS)
        if support or predicted:
            f1s.append(2 * tp / (support + predicted))
    clarify_tp = confusion["clarify"]["clarify"]
    not_acceptable = [p for _, acceptable, p in rows if "clarify" not in acceptable]
    return {"cases": len(rows), "confusion": confusion,
            "accuracy": _ratio(sum(e == p for e, _, p in rows), len(rows)),
            "acceptable_rate": _ratio(sum(p in a for _, a, p in rows), len(rows)),
            "macro_f1": sum(f1s) / len(f1s) if f1s else None,
            "clarify_precision": _ratio(clarify_tp, sum(confusion[e]["clarify"] for e in BEHAVIORS)),
            "clarify_recall": _ratio(clarify_tp, sum(confusion["clarify"].values())),
            "unnecessary_clarification_rate": _ratio(sum(p == "clarify" for p in not_acceptable), len(not_acceptable)),
            "gate": gate_metrics([(p in ANSWERED, e in ANSWERED) for e, _, p in rows])}  # fmt: skip
