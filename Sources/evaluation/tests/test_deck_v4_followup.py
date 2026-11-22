import json

from scripts import deck_v4_followup


def test_merge_judgments_requires_exact_coverage_and_fact_alignment(tmp_path, monkeypatch):
    judge = tmp_path / "judge"
    judge.mkdir()
    monkeypatch.setattr(deck_v4_followup, "OUT", tmp_path)
    items = [{"id": f"F{i:03d}", "reply_type": "answer", "required_facts": ["fact"]} for i in range(1, 4)]
    (judge / "items.jsonl").write_text("".join(json.dumps(row) + "\n" for row in items))
    for number, item in enumerate(items, 1):
        row = {"id": item["id"], "facts": ["correct"], "wrong_group": False, "cited_sentences": 0,
               "supported_sentences": 0, "conditions_match": None, "asks_branch_attribute": None,
               "right_referral": None, "note": ""}
        (judge / f"judgments_part{number}.jsonl").write_text(json.dumps(row) + "\n")

    assert deck_v4_followup.merge_judgments() == 0
    assert len((judge / "judgments.jsonl").read_text().splitlines()) == 3
