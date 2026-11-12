"""HYU suite: trace -> record -> per-slice tables and paired comparisons, on hand-made labels (no databases)."""

import json

import pytest

from evaluation import hyu_suite

SPAN = {"doc_id": "D1", "char_start": 0, "char_end": 100}
BAD = {"doc_id": "D1", "char_start": 200, "char_end": 300}


def case(cid, slice_, expected, acceptable=None):
    return {"case_id": cid, "slice": slice_, "gold_profile": {"campus": "seoul"}, "expected_behavior": expected,
            "acceptable_behaviors": acceptable or [expected], "gold_evidence": [SPAN], "inapplicable_evidence": [BAD],
            "outdated_evidence": [], "question": "Q?", "session_history": [{"role": "user", "text": "I'm at ERICA."}]}


CASES = [case("C1", "conditional", "conditional_answer"), case("C2", "conditional", "answer"), case("C3", "negative", "abstain")]
SPANS = {"good": {"doc_id": "D1", "source_spans": [[10, 20]]}, "bad": {"doc_id": "D1", "source_spans": [[250, 260]]}}


def trace(action, cited, outcome="answered"):
    return {"status": "completed", "error": None, "action": action, "outcome": outcome, "answer": "x", "total_ms": 100.0,
            "unknown_condition_evidence": False, "config": {"generation": {"method": "ollama"}},
            "stages": [{"stage_id": "reranking", "status": "completed", "output": [{"chunk_id": c} for c in ("bad", "good")]},
                       {"stage_id": "generation", "status": "completed", "output": {}}],
            "sources": [{"chunk_id": c, "cited": True} for c in cited]}  # fmt: skip


def test_history_and_trace_record():
    assert hyu_suite.history_of(CASES[0]) == ["I'm at ERICA."]
    rec = hyu_suite.trace_record(CASES[0], trace("CONDITIONAL", ["good"]), lambda ids: {i: SPANS[i] for i in ids})
    assert rec["behavior"] == "conditional_answer" and rec["llm_calls"] == 1
    assert [c["chunk_id"] for c in rec["ranked"]] == ["bad", "good"] and rec["cited"][0]["source_spans"] == [[10, 20]]


def test_tables_and_comparisons(tmp_path):
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "dev.jsonl").write_text("".join(json.dumps(c) + "\n" for c in CASES))
    raw = tmp_path / "raw" / "hyu" / "dev"
    raw.mkdir(parents=True)
    lookup = lambda ids: {i: SPANS[i] for i in ids}  # noqa: E731
    runs = {"A0_AAES": [trace("CONDITIONAL", ["good"]), trace("ANSWER", ["good"]), trace("ABSTAIN", [], "abstain")],
            "B0_BASIC_DENSE_RAG": [trace(None, ["bad"]), trace(None, ["good", "bad"]), trace(None, ["good"])]}
    for preset, traces in runs.items():
        (raw / f"{preset}__-.jsonl").write_text("".join(json.dumps({**hyu_suite.trace_record(c, t, lookup), "status": "completed"}) + "\n"
                                                        for c, t in zip(CASES, traces)))  # fmt: skip
    spec = {"ours": "A0_AAES", "baselines": ["B0_BASIC_DENSE_RAG"], "ablation": "A4_QUESTION_ONLY_AMBIGUITY"}
    summary, per_case, confusion, compared = hyu_suite.hyu_tables(tmp_path, "dev", spec, labels, resamples=200)
    rows = {(r["preset"], r["slice"]): r for r in summary}
    assert rows[("A0_AAES", "all")]["action_accuracy"] == 1.0 and rows[("A0_AAES", "all")]["aer"] == 0.0
    # B0: C1 answer (expected conditional) cites bad, C2 answer cites bad, C3 answers (expected abstain) cites good only
    assert rows[("B0_BASIC_DENSE_RAG", "all")]["action_accuracy"] == pytest.approx(1 / 3)
    assert rows[("B0_BASIC_DENSE_RAG", "all")]["aer"] == pytest.approx(2 / 3)
    assert rows[("B0_BASIC_DENSE_RAG", "conditional")]["cases"] == 2 and len(per_case) == 6
    aer = next(c for c in compared if c["metric"] == "aer")
    assert aer["diff"] == -1.0 and aer["cases"] == 2 and "p_holm" in aer  # both answered C1 and C2
    assert next(c for c in compared if c["metric"] == "macro_f1")["status"].startswith("NOT_RUN")
    assert next(c for c in compared if c["metric"] == "correctness")["status"].startswith("NOT_COMPUTED")


def test_index_doc_ids_map_to_snapshot_ids_and_baselines_get_the_history():
    ids = hyu_suite.snapshot_doc_ids("hyu-20261110-97dc1269")
    assert len(ids) == 362 and all(k != v for k, v in ids.items())
    assert hyu_suite.question_for(CASES[0], {}) == "I'm at ERICA.\n" + CASES[0]["question"] if "question" in CASES[0] else True
