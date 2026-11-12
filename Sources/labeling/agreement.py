"""Measure pre-adjudication agreement between two HYU label files."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

FIELDS = ("answerability", "expected_behavior", "branch_attributes", "gold_evidence")
CSV_COLUMNS = (
    "case_id",
    "question",
    "annotator_a",
    "annotator_b",
    "answerability_a",
    "answerability_b",
    "expected_behavior_a",
    "expected_behavior_b",
    "branch_attributes_a",
    "branch_attributes_b",
    "gold_evidence_a",
    "gold_evidence_b",
    "notes_a",
    "notes_b",
    "agree",
    "final_answerability",
    "final_expected_behavior",
    "final_branch_attributes",
    "final_gold_evidence",
    "adjudicator",
)


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa for two equally sized categorical sequences.

    A 2x2 table ``[[2, 1], [1, 2]]`` has observed agreement 4/6 and expected agreement
    1/2 from its balanced marginals, so kappa is ``(4/6 - 1/2) / (1 - 1/2) = 1/3``.
    """
    if len(a) != len(b) or not a:
        raise ValueError("kappa needs two non-empty sequences of equal length")
    observed = sum(left == right for left, right in zip(a, b, strict=True)) / len(a)
    categories = set(a) | set(b)
    expected = sum(a.count(value) * b.count(value) for value in categories) / len(a) ** 2
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def kappa_interval(a: list[str], b: list[str], draws: int = 2000, seed: int = 13) -> tuple[float, float]:
    """95% percentile-bootstrap interval for Cohen's kappa, resampling cases with replacement.

    Identical sequences with two categories give kappa 1.0 in every draw that has both
    categories (and 1.0 by convention when a draw has one), so the interval is (1.0, 1.0).
    """
    rng = random.Random(seed)
    n = len(a)
    scores = []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        scores.append(cohens_kappa([a[i] for i in idx], [b[i] for i in idx]))
    scores.sort()
    return scores[int(0.025 * draws)], scores[int(0.975 * draws) - 1]


def collapse(answerability: str) -> str:
    """answerable / partial / not_answerable: every negative type (external_only, unanswerable, ...) is one class."""
    return answerability if answerability in ("answerable", "partial") else "not_answerable"


def mean_jaccard(a: list[list[str]], b: list[list[str]]) -> float:
    scores = []
    for left, right in zip(a, b, strict=True):
        left_set, right_set = set(left), set(right)
        scores.append(1.0 if not left_set and not right_set else len(left_set & right_set) / len(left_set | right_set))
    return sum(scores) / len(scores)


def span_f1(a: list[dict], b: list[dict]) -> float:
    left = {(span["doc_id"], offset) for span in a for offset in range(span["char_start"], span["char_end"])}
    right = {(span["doc_id"], offset) for span in b for offset in range(span["char_start"], span["char_end"])}
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision, recall = overlap / len(left), overlap / len(right)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def mean_span_f1(a: list[list[dict]], b: list[list[dict]]) -> float:
    scores = [span_f1(left, right) for left, right in zip(a, b, strict=True)]
    return sum(scores) / len(scores)


def _load(path: Path) -> dict[str, dict]:
    """One label file, or a folder: every *.jsonl in it, keeping only label rows (with expected_behavior)."""
    rows = []
    for file in sorted(path.glob("*.jsonl")) if path.is_dir() else [path]:
        with file.open(encoding="utf-8") as handle:
            rows += [row for row in map(json.loads, filter(str.strip, handle)) if "expected_behavior" in row]
    cases = {row["case_id"]: row for row in rows}
    if len(cases) != len(rows):
        raise ValueError(f"duplicate case_id in {path}")
    return cases


def _ci(interval: tuple[float, float]) -> str:
    return f"[{interval[0]:.3f}, {interval[1]:.3f}]"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def agreement(a_path: Path, b_path: Path, out_dir: Path) -> dict[str, float | int]:
    a_cases, b_cases = _load(a_path), _load(b_path)
    case_ids = sorted(a_cases.keys() & b_cases.keys())
    if not case_ids:
        raise ValueError("the files have no case_id values in common")
    pairs = [(a_cases[case_id], b_cases[case_id]) for case_id in case_ids]

    answerability_a = [left["answerability"] for left, _ in pairs]
    answerability_b = [right["answerability"] for _, right in pairs]
    collapsed_a, collapsed_b = [collapse(x) for x in answerability_a], [collapse(x) for x in answerability_b]
    behavior_a = [left["expected_behavior"] for left, _ in pairs]
    behavior_b = [right["expected_behavior"] for _, right in pairs]
    branches_a = [left["branch_attributes"] for left, _ in pairs]
    branches_b = [right["branch_attributes"] for _, right in pairs]
    evidence_a = [left["gold_evidence"] for left, _ in pairs]
    evidence_b = [right["gold_evidence"] for _, right in pairs]
    span_scores = [span_f1(left, right) for left, right in zip(evidence_a, evidence_b, strict=True)]

    report: dict = {
        "cases": len(case_ids),
        "answerability_kappa": cohens_kappa(answerability_a, answerability_b),
        "answerability_collapsed_kappa": cohens_kappa(collapsed_a, collapsed_b),
        "answerability_collapsed_kappa_ci": kappa_interval(collapsed_a, collapsed_b),
        "expected_behavior_kappa": cohens_kappa(behavior_a, behavior_b),
        "answerability_kappa_ci": kappa_interval(answerability_a, answerability_b),
        "expected_behavior_kappa_ci": kappa_interval(behavior_a, behavior_b),
        "branch_attributes_jaccard": mean_jaccard(branches_a, branches_b),
        "gold_evidence_span_f1": sum(span_scores) / len(span_scores),
        "answerability_disagreements": sum(a != b for a, b in zip(answerability_a, answerability_b, strict=True)),
        "answerability_collapsed_disagreements": sum(a != b for a, b in zip(collapsed_a, collapsed_b, strict=True)),
        "expected_behavior_disagreements": sum(a != b for a, b in zip(behavior_a, behavior_b, strict=True)),
        "branch_attributes_disagreements": sum(set(a) != set(b) for a, b in zip(branches_a, branches_b, strict=True)),
        "gold_evidence_disagreements": sum(score != 1.0 for score in span_scores),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "adjudication.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for case_id, (left, right) in zip(case_ids, pairs, strict=True):
            values_agree = all(
                (
                    set(left[field]) == set(right[field])
                    if field == "branch_attributes"
                    else span_f1(left[field], right[field]) == 1.0
                    if field == "gold_evidence"
                    else left[field] == right[field]
                )
                for field in FIELDS
            )
            writer.writerow(
                {
                    "case_id": case_id,
                    "question": left.get("question", ""),
                    "annotator_a": left["annotator"],
                    "annotator_b": right["annotator"],
                    "answerability_a": left["answerability"],
                    "answerability_b": right["answerability"],
                    "expected_behavior_a": left["expected_behavior"],
                    "expected_behavior_b": right["expected_behavior"],
                    "branch_attributes_a": _json(left["branch_attributes"]),
                    "branch_attributes_b": _json(right["branch_attributes"]),
                    "gold_evidence_a": _json(left["gold_evidence"]),
                    "gold_evidence_b": _json(right["gold_evidence"]),
                    "notes_a": left.get("notes", ""),
                    "notes_b": right.get("notes", ""),
                    "agree": "yes" if values_agree else "no",
                }
            )

    markdown = [
        "# Label agreement",
        "",
        f"Cases in both files: {len(case_ids)}",
        "",
        "| Field | Measure | Score | 95% bootstrap CI | Disagreements |",
        "|---|---|---:|---|---:|",
        f"| answerability | Cohen's kappa | {report['answerability_kappa']:.6f} | {_ci(report['answerability_kappa_ci'])} | {report['answerability_disagreements']} |",
        f"| answerability, collapsed (answerable / partial / not answerable) | Cohen's kappa | {report['answerability_collapsed_kappa']:.6f} | {_ci(report['answerability_collapsed_kappa_ci'])} | {report['answerability_collapsed_disagreements']} |",
        f"| expected_behavior | Cohen's kappa | {report['expected_behavior_kappa']:.6f} | {_ci(report['expected_behavior_kappa_ci'])} | {report['expected_behavior_disagreements']} |",
        f"| branch_attributes | Mean Jaccard | {report['branch_attributes_jaccard']:.6f} | | {report['branch_attributes_disagreements']} |",
        f"| gold_evidence | Mean character span F1 | {report['gold_evidence_span_f1']:.6f} | | {report['gold_evidence_disagreements']} |",
        "",
    ]
    (out_dir / "agreement.md").write_text("\n".join(markdown), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = agreement(args.a, args.b, args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
