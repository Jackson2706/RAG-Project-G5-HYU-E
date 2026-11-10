from __future__ import annotations

import csv
import json

import pytest

from labeling.agreement import CSV_COLUMNS, agreement, cohens_kappa, mean_jaccard, span_f1


def test_kappa_matches_hand_computed_two_by_two_example():
    a = ["yes", "yes", "yes", "no", "no", "no"]
    b = ["yes", "yes", "no", "yes", "no", "no"]
    assert cohens_kappa(a, b) == pytest.approx(1 / 3)


def test_jaccard_and_span_f1():
    assert mean_jaccard([["campus", "visa"], []], [["visa", "year"], []]) == pytest.approx(2 / 3)
    assert span_f1(
        [{"doc_id": "doc", "char_start": 0, "char_end": 10}],
        [{"doc_id": "doc", "char_start": 5, "char_end": 15}],
    ) == pytest.approx(0.5)
    assert span_f1([], []) == 1.0


def _case(case_id, annotator, answerability, behavior, branches, start):
    return {
        "case_id": case_id,
        "annotator": annotator,
        "answerability": answerability,
        "expected_behavior": behavior,
        "branch_attributes": branches,
        "gold_evidence": [{"doc_id": "doc", "char_start": start, "char_end": start + 10}],
    }


def test_agreement_writes_adjudication_columns_and_markdown(tmp_path):
    a = [
        _case("hyu-1", "codex:gpt", "answerable", "answer", [], 0),
        _case("hyu-2", "codex:gpt", "partial", "clarify", ["visa"], 20),
    ]
    b = [
        _case("hyu-1", "claude-code:sonnet", "answerable", "answer", [], 0),
        _case("hyu-2", "claude-code:sonnet", "answerable", "abstain", ["campus"], 25),
    ]
    a_path, b_path, out = tmp_path / "a.jsonl", tmp_path / "b.jsonl", tmp_path / "out"
    a_path.write_text("".join(json.dumps(case) + "\n" for case in a), encoding="utf-8")
    b_path.write_text("".join(json.dumps(case) + "\n" for case in b), encoding="utf-8")

    report = agreement(a_path, b_path, out)
    with (out / "adjudication.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[0]["agree"] == "yes" and rows[1]["agree"] == "no"
    assert rows[0]["final_answerability"] == rows[0]["adjudicator"] == ""
    assert report["answerability_disagreements"] == 1
    assert "Cohen's kappa" in (out / "agreement.md").read_text(encoding="utf-8")
