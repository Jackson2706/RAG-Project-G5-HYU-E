import csv
import json

import pytest

from labeling import review


def _setup(tmp_path):
    labels = tmp_path / "labels"
    (labels / "drafts").mkdir(parents=True)
    (labels / "personas.json").write_text(json.dumps([
        {"persona_id": "p1", "gold_profile": {"campus": "seoul"}},
        {"persona_id": "p2", "gold_profile": {"campus": "erica"}},
    ]))
    drafts = [
        {"draft_id": f"T14-00{i}", "slice": s, "campus": c, "persona_id": p, "topic_doc_ids": ["d"],
         "question": f"q{i}?", "session_history": h, "intended_attributes": ["visa"],
         "intended_answerability": "answerable", "why": "w", "annotator": "codex:gpt", "origin": "agent_draft"}
        for i, (s, c, p, h) in enumerate([("unconditional", "seoul", "p1", []), ("conditional", "erica", "p2", []),
                                          ("multi_session", "erica", "p2", ["I hold D-4.", "Now D-2."])], 1)
    ]
    (labels / "drafts" / "questions_codex.jsonl").write_text("".join(json.dumps(d) + "\n" for d in drafts))
    return labels


def _decide(labels, decisions, new_rows=()):
    sheet = labels / "drafts" / "review.csv"
    with open(sheet, newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.update(decisions.get(row["id"], {}))
    rows.extend(new_rows)
    with open(sheet, "w", newline="") as f:
        writer = csv.DictWriter(f, review.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_make_keeps_hints_out_of_the_sheet_and_refuses_overwrite(tmp_path):
    labels = _setup(tmp_path)
    assert review.make(labels) == 3
    header = (labels / "drafts" / "review.csv").read_text().splitlines()[0].split(",")
    assert header == review.COLUMNS
    assert "intended_attributes" in (labels / "drafts" / "hints.jsonl").read_text()
    with pytest.raises(SystemExit):
        review.make(labels)


def test_apply_sets_origins_appends_new_and_reports_human_share(tmp_path):
    labels = _setup(tmp_path)
    review.make(labels)
    _decide(labels, {"T14-001": {"decision": "keep"}, "T14-002": {"decision": "delete"},
                     "T14-003": {"decision": "edit", "edited_question": "Can I work now?"}},
            [{"id": "", "slice": "unconditional", "campus": "seoul", "persona": "p1", "session_history": "",
              "question": "Where is the OIA?", "decision": "new", "edited_question": "", "notes": ""}])
    report = review.apply(labels, initials="JK")
    assert report["origins"] == {"agent_draft": 1, "agent_draft_human_edited": 1, "human": 1}
    assert report["human_share"] == pytest.approx(2 / 3)
    annotator_view = [json.loads(line) for line in (labels / "questions.jsonl").read_text().splitlines()]
    assert {tuple(sorted(r)) for r in annotator_view} == {("case_id", "persona_id", "question", "session_history")}
    assert annotator_view[1]["session_history"] == ["I hold D-4.", "Now D-2."]


def test_apply_rejects_missing_decisions_and_wrong_campus(tmp_path):
    labels = _setup(tmp_path)
    review.make(labels)
    _decide(labels, {"T14-001": {"decision": "keep"}},
            [{"id": "", "slice": "unconditional", "campus": "seoul", "persona": "p2", "session_history": "",
              "question": "x?", "decision": "new", "edited_question": "", "notes": ""}])
    with pytest.raises(SystemExit, match="no decision row|not a seoul persona"):
        review.apply(labels, initials="JK")
    assert not (labels / "questions.jsonl").exists()


def test_agent_edit_is_not_human(tmp_path):
    labels = _setup(tmp_path)
    review.make(labels)
    _decide(labels, {"T14-001": {"decision": "agent_edit", "edited_question": "where do i start?"},
                     "T14-002": {"decision": "keep"}, "T14-003": {"decision": "keep"}})
    report = review.apply(labels)
    assert report["origins"] == {"agent_edited": 1, "agent_draft": 2}
    assert report["human_share"] == 0
