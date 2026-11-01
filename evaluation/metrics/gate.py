"""Evidence Sufficiency Gate metrics (Lesson 6).

Convention: ACTUAL positive = the evidence is sufficient; PREDICTED positive = the gate proceeds.
    TP proceed & sufficient     FP proceed & insufficient (unsupported-answer risk)
    TN abstain & insufficient   FN abstain & sufficient   (answer opportunity blocked)
A rate whose denominator is 0 is undefined (None).
"""

from __future__ import annotations


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def gate_metrics(cases: list[tuple[bool, bool]]) -> dict:
    """cases: (proceeded, sufficient) per case, with INDEPENDENT sufficiency labels."""
    tp = sum(p and s for p, s in cases)
    fp = sum(p and not s for p, s in cases)
    tn = sum(not p and not s for p, s in cases)
    fn = sum(not p and s for p, s in cases)
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "cases": len(cases),
            "accuracy": _ratio(tp + tn, len(cases)),            # (TP + TN) / all
            "precision": _ratio(tp, tp + fp),                    # of the proceeds, how many were sufficient
            "recall": _ratio(tp, tp + fn),                       # of the sufficient cases, how many proceeded
            "false_positive_rate": _ratio(fp, fp + tn),          # of the insufficient cases, how many proceeded
            "false_negative_rate": _ratio(fn, fn + tp),          # of the sufficient cases, how many abstained
            "abstention_rate": _ratio(tn + fn, len(cases))}  # fmt: skip
