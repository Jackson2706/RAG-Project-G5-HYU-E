"""P8 metric tests with hand-computed examples (written by Claude Code before the code)."""

import pytest

from evaluation.metrics.aaes import (action_metrics, applicable_recall_at, chunk_class, flag_rate, inapplicable_intrusion_at,
                                     label_action, cited_error)  # fmt: skip
from evaluation.metrics.stats import holm, mean, paired_compare

GOLD = [{"doc_id": "D1", "char_start": 100, "char_end": 200}, {"doc_id": "D2", "char_start": 0, "char_end": 50}]
INAPP = [{"doc_id": "D1", "char_start": 300, "char_end": 400}]
OLD = [{"doc_id": "D9", "char_start": 0, "char_end": 10}]
CASE = {"gold_evidence": GOLD, "inapplicable_evidence": INAPP, "outdated_evidence": OLD}


def chunk(doc, *spans):
    return {"doc_id": doc, "source_spans": [list(s) for s in spans]}


G1, G2 = chunk("D1", (150, 250)), chunk("D2", (40, 60))
BAD, STALE, OTHER = chunk("D1", (350, 360)), chunk("D9", (5, 6)), chunk("D3", (0, 99))
EDGE = chunk("D1", (200, 300))  # touches gold end and inapplicable start, overlaps neither (half-open spans)


def test_chunk_class_priority_and_half_open_spans():
    assert [chunk_class(c, CASE) for c in (G1, BAD, STALE, OTHER, EDGE)] == ["gold", "inapplicable", "outdated", "other", "other"]
    assert chunk_class(chunk("D1", (190, 310)), CASE) == "gold"  # overlaps both: gold wins


def test_applicable_recall_and_intrusion_hand_computed():
    ranked = [BAD, G1, OTHER, G2]
    assert applicable_recall_at(ranked, CASE, 2) == 0.5  # D1 gold span covered, D2 not yet
    assert applicable_recall_at(ranked, CASE, 4) == 1.0
    assert inapplicable_intrusion_at(ranked, CASE, 2) == 0.5  # 1 of the top 2
    assert inapplicable_intrusion_at(ranked, CASE, 4) == 0.25
    assert applicable_recall_at(ranked, {**CASE, "gold_evidence": []}, 4) is None
    assert inapplicable_intrusion_at(ranked, {**CASE, "inapplicable_evidence": []}, 4) is None


def test_cited_error_counts_only_cited_chunks_of_answered_cases():
    assert cited_error([G1, BAD], CASE, "answer", "inapplicable") == 1
    assert cited_error([G1], CASE, "conditional_answer", "inapplicable") == 0
    assert cited_error([BAD], CASE, "abstain", "inapplicable") is None  # not answered
    assert cited_error([STALE], CASE, "answer", "outdated") == 1
    assert cited_error([BAD], {**CASE, "inapplicable_evidence": []}, "answer", "inapplicable") is None


def test_label_action_mapping():
    assert [label_action(a, "answered") for a in ("ANSWER", "CONDITIONAL", "CLARIFY", "CONFIRM", "ABSTAIN")] == \
           ["answer", "conditional_answer", "clarify", "clarify", "abstain"]
    assert label_action(None, "answered") == "answer" and label_action(None, "insufficient_context") == "abstain"


def test_action_metrics_hand_computed():
    # expected, acceptable, predicted
    rows = [("answer", ["answer"], "answer"),
            ("answer", ["answer"], "clarify"),                                   # unnecessary clarification
            ("conditional_answer", ["conditional_answer", "clarify"], "clarify"),  # acceptable, not exact
            ("clarify", ["clarify"], "clarify"),
            ("abstain", ["abstain", "answer"], "answer")]
    m = action_metrics(rows)
    assert m["accuracy"] == pytest.approx(2 / 5) and m["acceptable_rate"] == pytest.approx(4 / 5)  # rows 1, 3, 4, 5
    assert m["confusion"]["answer"]["clarify"] == 1 and m["confusion"]["abstain"]["answer"] == 1
    # F1: answer P 1/2 R 1/2 -> 1/2; conditional 0; clarify P 1/3 R 1 -> 1/2; abstain 0  => macro 1/4
    assert m["macro_f1"] == pytest.approx(0.25)
    assert m["clarify_precision"] == pytest.approx(1 / 3) and m["clarify_recall"] == 1.0
    assert m["unnecessary_clarification_rate"] == pytest.approx(1 / 3)  # clarify not acceptable in rows 1, 2, 5
    assert m["gate"]["FP"] == 1 and m["gate"]["FN"] == 2  # abstain->answer proceeds; rows 2 and 3 withhold


def test_flag_rate_ignores_unanswered():
    assert flag_rate([(True, "answer"), (False, "conditional_answer"), (True, "abstain")]) == 0.5
    assert flag_rate([(True, "clarify")]) is None


def test_permutation_and_holm():
    same = paired_compare([1, 0, 1, 0], [1, 0, 1, 0], mean, resamples=500)
    assert same["diff"] == 0 and same["p"] == 1.0 and same["ci_low"] == same["ci_high"] == 0
    better = paired_compare([1] * 12, [0] * 12, mean, resamples=2000)
    assert better["diff"] == 1 and better["ci_low"] == 1 and better["p"] < 0.01  # only swap-all / swap-none reach |diff| 1
    with pytest.raises(ValueError):
        paired_compare([1], [1, 0], mean)
    # Holm: sorted p 0.01, 0.03, 0.04 -> 0.03, 0.06, 0.06 (monotone), back in input order
    assert holm([0.04, 0.01, 0.03]) == pytest.approx([0.06, 0.03, 0.06])


def test_an_aaes_answer_that_still_abstained_counts_as_abstain():
    assert label_action("CONDITIONAL", "insufficient_context") == "abstain" and label_action("CLARIFY", "clarify") == "clarify"
