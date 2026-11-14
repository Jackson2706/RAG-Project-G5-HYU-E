from __future__ import annotations

from copy import deepcopy

import pytest

from labeling.validate import validate_cases

SNAPSHOT = "synthetic"


@pytest.fixture
def rows():
    return [
        {
            "doc_id": "old",
            "text": "An older visa rule.",
            "spans": [{"kind": "paragraph", "char_start": 0, "char_end": 19}],
            "superseded_by": "new",
            "version_family_id": "visa-family",
        },
        {
            "doc_id": "new",
            "text": "The current visa rule applies.",
            "spans": [{"kind": "paragraph", "char_start": 0, "char_end": 30}],
            "superseded_by": None,
            "version_family_id": "visa-family",
        },
    ]


@pytest.fixture
def valid_case():
    return {
        "case_id": "hyu-0001",
        "case_version": "1.0",
        "snapshot_id": SNAPSHOT,
        "slice": "temporal",
        "origin": "agent_draft",
        "annotator": "codex:gpt-5",
        "session_history": [],
        "question": "What is the current visa rule?",
        "stated_profile": {"campus": "erica"},
        "gold_profile": {"campus": "erica", "visa": "D-2"},
        "branch_attributes": [],
        "answerability": "answerable",
        "expected_behavior": "answer",
        "acceptable_behaviors": ["answer"],
        "required_facts": ["the current rule"],
        "gold_evidence": [
            {"doc_id": "new", "char_start": 0, "char_end": 12, "applies_to_gold_profile": True}
        ],
        "inapplicable_evidence": [
            {"doc_id": "new", "char_start": 12, "char_end": 16, "why": "different visa"}
        ],
        "outdated_evidence": [{"doc_id": "old", "char_start": 0, "char_end": 10}],
        "condition_scope": "national",
        "reference_answer": "Use the current rule.",
        "notes": "",
    }


def errors(case, rows):
    return validate_cases([case], rows, SNAPSHOT)


def test_valid_case_has_no_violations(valid_case, rows):
    assert errors(valid_case, rows) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (("remove", "question", None), "question: is required"),
        (("set", "question", 42), "question: must be str"),
        (("set", "answerability", "maybe"), "answerability: must be one of"),
        (("set", "expected_behavior", "guess"), "expected_behavior: must be one of"),
        (("set", "acceptable_behaviors", ["clarify"]), "acceptable_behaviors: must include expected_behavior"),
        (("set", "acceptable_behaviors", ["answer", "guess"]), "acceptable_behaviors: contains invalid values"),
        (("set", "slice", "other"), "slice: must be one of"),
        (("set", "split", "train"), "split: must be dev, test or test2"),
        (("set", "origin", "machine"), "origin: must be one of"),
        (("set", "annotator", "bot"), "annotator: must match"),
        (("set", "condition_scope", "global"), "condition_scope: must be national or campus"),
    ],
)
def test_schema_rules_fail_with_field_message(valid_case, rows, change, expected):
    action, field, value = change
    if action == "remove":
        valid_case.pop(field)
    else:
        valid_case[field] = value
    assert any(expected in error for error in errors(valid_case, rows))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("stated_profile", {"nationality": "Korean"}, "unknown vocabulary attribute 'nationality'"),
        ("gold_profile", {"campus": "other"}, "campus value 'other' is outside the vocabulary"),
        ("branch_attributes", ["gpa"], "unknown vocabulary attribute 'gpa'"),
    ],
)
def test_vocabulary_rules(valid_case, rows, field, value, expected):
    valid_case[field] = value
    assert any(expected in error for error in errors(valid_case, rows))


def test_stated_profile_must_agree_with_gold(valid_case, rows):
    valid_case["stated_profile"]["campus"] = "seoul"
    assert any("campus must agree with gold_profile" in error for error in errors(valid_case, rows))


def test_multi_session_stated_update_may_differ(valid_case, rows):
    valid_case.update(slice="multi_session", stated_profile={"campus": "seoul"})
    valid_case["session_history"] = [{"role": "user", "text": "I transferred and now study at ERICA."}]
    assert not any("must agree with gold_profile" in error for error in errors(valid_case, rows))


@pytest.mark.parametrize(
    ("field", "entry", "expected"),
    [
        ("gold_evidence", {"doc_id": "missing", "char_start": 0, "char_end": 1, "applies_to_gold_profile": True}, "does not exist"),
        ("gold_evidence", {"doc_id": "new", "char_start": 2, "char_end": 2, "applies_to_gold_profile": True}, "span must satisfy"),
        ("gold_evidence", {"doc_id": "new", "char_start": 0, "char_end": 2, "applies_to_gold_profile": False}, "applies_to_gold_profile must be true"),
        ("inapplicable_evidence", {"doc_id": "new", "char_start": 0, "char_end": 2, "why": ""}, "why must be a non-empty string"),
        ("outdated_evidence", {"doc_id": "new", "char_start": 0, "char_end": 2}, "newest linked version"),
        ("gold_evidence", {"doc_id": "new", "char_start": 0, "char_end": 2, "applies_to_gold_profile": True, "branch": {"campus": "mars"}}, "branch must be"),
    ],
)
def test_evidence_rules(valid_case, rows, field, entry, expected):
    valid_case[field] = [entry]
    assert any(expected in error for error in errors(valid_case, rows))


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"gold_evidence": []}, "gold_evidence: is required for answer"),
        (
            {"expected_behavior": "abstain", "acceptable_behaviors": ["abstain"]},
            "answerability: answerable cases cannot abstain",
        ),
        (
            {"expected_behavior": "conditional_answer", "acceptable_behaviors": ["conditional_answer"]},
            "branch_attributes: is required for conditional_answer",
        ),
        (
            {
                "expected_behavior": "conditional_answer",
                "acceptable_behaviors": ["conditional_answer"],
                "branch_attributes": ["visa"],
                "gold_evidence": [],
            },
            "gold_evidence: is required for conditional_answer",
        ),
        (
            {"expected_behavior": "clarify", "acceptable_behaviors": ["clarify"], "gold_evidence": []},
            "branch_attributes: is required for clarify",
        ),
    ],
)
def test_behavior_rules(valid_case, rows, updates, expected):
    valid_case.update(updates)
    assert any(expected in error for error in errors(valid_case, rows))


def test_case_ids_are_unique(valid_case, rows):
    duplicate = deepcopy(valid_case)
    assert any("case_id: must be unique" in error for error in validate_cases([valid_case, duplicate], rows, SNAPSHOT))


@pytest.mark.parametrize("condition_sets, expected", [
    ([{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}], None),
    ([{"english_track": ["yes"]}], "at least two"),
    ([{"topik_level": ["7"]}, {"english_track": ["yes"]}], "outside the vocabulary"),
    ([{"korean_standard": ["pass"]}, {}], "non-empty"),
], ids=["valid", "single_set", "bad_value", "empty_set"])  # fmt: skip
def test_condition_sets_use_vocabulary_v1(valid_case, rows, condition_sets, expected):
    errors = validate_cases([{**valid_case, "condition_sets": condition_sets}], rows, SNAPSHOT)
    assert (not errors) if expected is None else any("condition_sets" in e and expected in e for e in errors)


def test_branch_mark_and_stale_update_are_optional_and_typed(valid_case, rows):
    valid_case["gold_evidence"][0]["branch"] = {"campus": "erica"}
    valid_case["stale_update"] = True
    assert errors(valid_case, rows) == []
    valid_case["stale_update"] = "yes"
    assert any("stale_update: must be true or false" in error for error in errors(valid_case, rows))
