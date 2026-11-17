from scripts.deck_v4_local_label import normalize, parse, validate


CASE = {"case_id": "N001", "question": "Which rule applies?", "passages": [{"chunk_id": "c1", "text": "Rule."}]}


def test_local_label_parser_and_boundary_validation():
    raw = ('prefix {"case_id":"N001","expected_behavior":"answer","acceptable_behaviors":["answer"],'
           '"branch_attributes":[],"stated_profile":{"campus":"seoul"},"required_facts":["Rule"],'
           '"gold_evidence":["c1"],"inapplicable_evidence":[],"answerability":"answerable",'
           '"exclude":false,"notes":""} suffix')
    value = parse(raw)
    assert validate(value, CASE) == []
    value["gold_evidence"] = ["invented"]
    value["branch_attributes"] = ["gpa"]
    assert validate(value, CASE) == ["branch_attributes", "gold_evidence"]
    assert parse("not json") is None


def test_local_label_enum_normalization_is_structural_only():
    value, changes = normalize({"expected_behavior": "partial", "acceptable_behaviors": ["a fact"], "answerability": True})
    assert value == {"expected_behavior": "abstain", "acceptable_behaviors": ["abstain"], "answerability": "partial"}
    assert changes == ["answerability_was_expected_behavior", "invalid_acceptable_behaviors"]


def test_local_label_normalization_drops_only_invalid_boundary_values():
    value, changes = normalize({"expected_behavior": "answer", "acceptable_behaviors": ["answer"], "answerability": "answer",
                                "stated_profile": {"campus": "unknown", "visa": "D-2"}, "gold_evidence": ["c1", "made-up"],
                                "inapplicable_evidence": []}, CASE)  # fmt: skip
    assert value["answerability"] == "answerable" and value["stated_profile"] == {"visa": "D-2"}
    assert value["gold_evidence"] == ["c1"]
    assert changes == ["behavior_was_answerability", "invalid_stated_values_removed", "invalid_gold_evidence_removed"]
