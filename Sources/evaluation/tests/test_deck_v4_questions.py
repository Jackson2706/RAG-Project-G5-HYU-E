import json

from scripts import deck_v4_questions


def _write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_assemble_keeps_consensus_and_replaces_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(deck_v4_questions, "Q", tmp_path)
    base = {"acceptable_behaviors": ["answer"], "branch_attributes": [], "exclude": False}
    a = [{**base, "case_id": "N001", "expected_behavior": "answer", "annotator": "A"},
         {**base, "case_id": "N002", "expected_behavior": "answer", "annotator": "A"}]
    b = [{**base, "case_id": "N001", "expected_behavior": "answer", "annotator": "B"},
         {**base, "case_id": "N002", "expected_behavior": "clarify", "branch_attributes": ["campus"], "annotator": "B"}]
    resolved = [{**base, "case_id": "N002", "expected_behavior": "conditional_answer",
                 "branch_attributes": ["campus"], "annotator": "C", "adjudicated_by": "C"}]
    _write(tmp_path / "a.jsonl", a)
    _write(tmp_path / "b.jsonl", b)
    _write(tmp_path / "resolved.jsonl", resolved)

    assert deck_v4_questions.assemble("a.jsonl", "b.jsonl", "resolved.jsonl") == 0

    rows = [json.loads(line) for line in (tmp_path / "adjudicated.jsonl").read_text().splitlines()]
    assert rows[0]["decision_provenance"] == "independent_consensus"
    assert rows[0]["consensus_with"] == "B"
    assert rows[1]["expected_behavior"] == "conditional_answer"
    assert rows[1]["decision_provenance"] == "third_model_adjudication"
    assert rows[1]["annotator"] == "A"
    assert rows[1]["adjudicated_by"] == "C"


def test_buffer_inputs_keeps_stable_buffer_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(deck_v4_questions, "Q", tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    row = {"qid": "DBUF001", "question": "Which rule applies?", "session_history": [], "gold_profile": {}, "skip": False}
    _write(drafts / "dependent_buffer_out.jsonl", [row])
    monkeypatch.setattr(deck_v4_questions, "_label_items", lambda rows: [{"case_id": r["case_id"]} for r in rows])

    assert deck_v4_questions.buffer_inputs() == 0

    candidate = json.loads((tmp_path / "candidates_buffer.jsonl").read_text())
    blind = json.loads((tmp_path / "label_input_buffer.jsonl").read_text())
    assert candidate["case_id"] == blind["case_id"] == "DBUF001"
    assert candidate["kind"] == "student_dependent"


def test_buffer_inputs_supports_separate_tag(tmp_path, monkeypatch):
    monkeypatch.setattr(deck_v4_questions, "Q", tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    _write(drafts / "dependent_buffer2_out.jsonl", [{"qid": "DBUF201", "question": "Q", "session_history": [], "gold_profile": {}}])
    monkeypatch.setattr(deck_v4_questions, "_label_items", lambda rows: [{"case_id": r["case_id"]} for r in rows])

    assert deck_v4_questions.buffer_inputs("2") == 0
    assert (tmp_path / "candidates_buffer2.jsonl").exists()
    assert (tmp_path / "label_input_buffer2.jsonl").exists()


def test_stratified_take_is_exact_and_deterministic():
    rows = [{"case_id": f"N{i}", "kind": "a" if i < 3 else "b"} for i in range(5)]
    first, reserve = deck_v4_questions._stratified_take(rows, 3, ("kind",), 42)
    second, _ = deck_v4_questions._stratified_take(rows, 3, ("kind",), 42)

    assert len(first) == 3 and len(reserve) == 2
    assert [row["case_id"] for row in first] == [row["case_id"] for row in second]
