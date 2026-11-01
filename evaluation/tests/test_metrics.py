"""Metric tests: Lesson 6 fixtures, hand-calculated cases, undefined cases, and the official pytrec_eval."""

import math
import random

import pytest

from evaluation.beir import documents_from_chunks
from evaluation.metrics.answer import abstention_correct, exact_match, token_f1
from evaluation.metrics.attribution import claim_metrics, marker_validity, reference_coverage
from evaluation.metrics.gate import gate_metrics
from evaluation.metrics.retrieval import (average_precision_at, capped_recall_at, clean_ranking, evaluate_run, hit_at, hole_at,
                                          ndcg_at, precision_at, recall_at, reciprocal_rank_at)  # fmt: skip

# Lesson 6, slides 13-18: ranking B, A, D, C; known relevant A, D, E; k = 4.
RANKING, RELEVANT = ["B", "A", "D", "C"], {"A", "D", "E"}
GRADES = {"A": 1, "D": 1, "E": 1, "B": 0, "C": 0}


def test_lesson6_fixture():
    assert recall_at(RANKING, RELEVANT, 4) == pytest.approx(2 / 3)
    assert precision_at(RANKING, RELEVANT, 4) == 0.5
    assert reciprocal_rank_at(RANKING, RELEVANT, 4) == 0.5
    assert ndcg_at(RANKING, GRADES, 4) == pytest.approx(0.531, abs=5e-4)  # DCG 1.131 / IDCG 2.131
    assert hit_at(RANKING, RELEVANT, 1) == 0.0 and hit_at(RANKING, RELEVANT, 2) == 1.0


def test_lesson6_mrr_example():
    assert sum([1, 0.5, 0]) / 3 == 0.5


def test_hand_calculated_map_capped_recall_and_hole():
    # relevant at ranks 2 and 3 of 3 relevant: AP@4 = (1/2 + 2/3) / 3
    assert average_precision_at(RANKING, RELEVANT, 4) == pytest.approx((0.5 + 2 / 3) / 3)
    assert capped_recall_at(RANKING, RELEVANT, 2) == pytest.approx(1 / 2)  # 1 relevant in top 2, min(2, 3) = 2
    assert hole_at(["A", "X", "Y", "B"], {"A", "B", "C"}, 4) == 0.5  # X, Y were never judged
    assert hole_at(["A"], {"A"}, 10) == 0.0  # BEIR divides by k


def test_graded_ndcg():
    grades = {"a": 2, "b": 1}
    expected = (1 / math.log2(2) + 2 / math.log2(3)) / (2 / math.log2(2) + 1 / math.log2(3))
    assert ndcg_at(["b", "a"], grades, 10) == pytest.approx(expected)


def test_undefined_values_are_none_not_zero():
    for value in (recall_at(["a"], set(), 5), average_precision_at(["a"], set(), 5), ndcg_at(["a"], {"a": 0}, 5),
                  reciprocal_rank_at(["a"], set(), 5), hit_at(["a"], set(), 5), capped_recall_at(["a"], set(), 5)):  # fmt: skip
        assert value is None
    per_query, mean = evaluate_run({"q1": ["a"], "q2": ["x"]}, {"q1": {"a": 1}, "q2": {"x": 0}})
    assert per_query["q2"]["Recall@5"] is None and mean["Recall@5"] == {"mean": 1.0, "n": 1, "undefined": 1}
    assert per_query["q2"]["P@5"] == 0.0  # precision is defined: 0 relevant of 5 positions


def test_short_lists_duplicates_identical_ids_and_missing_runs():
    assert precision_at(["a"], {"a"}, 10) == 0.1  # missing ranks count as misses
    assert clean_ranking(["q1", "a", "a", "b"], "q1") == ["a", "b"]  # BEIR drops the query's own id
    per_query, _ = evaluate_run({}, {"q1": {"a": 1}})
    assert per_query["q1"]["Recall@100"] == 0.0  # a failed query is an empty ranking, not dropped


def test_chunk_to_document_aggregation_keeps_first_appearance():
    assert documents_from_chunks(["d2", "d1", "d2", "d3", "d1"], 10) == ["d2", "d1", "d3"]
    assert documents_from_chunks(["d2", "d1", "d3"], 2) == ["d2", "d1"]


def test_matches_official_pytrec_eval_on_random_runs():
    pytrec_eval = pytest.importorskip("pytrec_eval")
    rng = random.Random(7)
    docs = [f"d{i}" for i in range(60)]
    qrels = {f"q{i}": {d: rng.choice([0, 1, 1, 2]) for d in rng.sample(docs, rng.randint(1, 8))} for i in range(40)}
    run = {q: rng.sample(docs, rng.randint(0, 40)) for q in qrels}
    ours, _ = evaluate_run(run, qrels, ignore_identical_ids=False)
    scored = {q: {d: float(len(r) - i) for i, d in enumerate(r)} for q, r in run.items()}
    official = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut.5,10", "map_cut.100", "recall.5,10,100", "P.5,10"}).evaluate(scored)
    for q in qrels:
        if not any(g > 0 for g in qrels[q].values()):
            continue  # pytrec_eval scores these 0; we report them as undefined (tested above)
        o = official.get(q, {})
        for ours_name, trec_name in (("nDCG@10", "ndcg_cut_10"), ("nDCG@5", "ndcg_cut_5"), ("MAP@100", "map_cut_100"),
                                     ("Recall@5", "recall_5"), ("Recall@100", "recall_100"), ("P@10", "P_10")):  # fmt: skip
            assert ours[q][ours_name] == pytest.approx(o.get(trec_name, 0.0), abs=1e-4), (q, ours_name)


def test_lesson6_gate_thresholds_have_equal_accuracy():
    scores, sufficient = [0.90, 0.80, 0.60, 0.30], [True, False, True, False]
    for threshold, expected in ((0.50, {"TP": 2, "FP": 1, "TN": 1, "FN": 0}), (0.85, {"TP": 1, "FP": 0, "TN": 2, "FN": 1})):
        m = gate_metrics([(s >= threshold, ok) for s, ok in zip(scores, sufficient)])
        assert {k: m[k] for k in expected} == expected and m["accuracy"] == 0.75


def test_gate_rates_and_undefined_denominators():
    m = gate_metrics([(True, True), (True, False), (False, False), (False, True), (False, True)])
    assert m["precision"] == 0.5 and m["recall"] == pytest.approx(1 / 3) and m["false_positive_rate"] == 0.5
    assert m["false_negative_rate"] == pytest.approx(2 / 3) and m["abstention_rate"] == 0.6
    assert gate_metrics([(True, True)])["false_positive_rate"] is None  # no insufficient case


def test_lesson6_citation_example():
    claims = [{"supported": True, "cited": True, "citation_supports": True},     # loan 3 days [A]
              {"supported": True, "cited": True, "citation_supports": False},    # help desk [D], D gives hours
              {"supported": True, "cited": False, "citation_supports": False},   # closes 20:00, no citation
              {"supported": False, "cited": True, "citation_supports": False}]   # renewals unlimited [E]  # fmt: skip
    m = claim_metrics(claims)
    assert m["grounding_support"] == 0.75 and m["citation_precision"] == pytest.approx(1 / 3) and m["citation_coverage"] == 0.25
    assert reference_coverage([True, True, True]) == 1.0 and reference_coverage([]) is None


def test_marker_validity_and_answer_metrics():
    m = marker_validity("18 credits [E1]. Also [E7] and [E1].", ["E1", "E2"])
    assert m["markers"] == 3 and m["invalid_markers"] == 1 and m["marker_validity"] == pytest.approx(2 / 3)
    assert marker_validity("no citations", ["E1"])["marker_validity"] is None
    assert exact_match("The 18 credits.", "18 credits") == 1.0 and token_f1("18 credits per term", "18 credits") == pytest.approx(2 / 3)
    assert abstention_correct("insufficient_context", "abstain") and not abstention_correct("answered", "abstain")
