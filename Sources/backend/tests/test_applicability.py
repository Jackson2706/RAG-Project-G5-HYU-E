"""AAES applicability: vocabulary v0, the chunk condition format, and the rule tagger on 12 real
snapshot chunks (hyu-20261110-97dc1269) with hand-written expected tags.

Written by Claude Code before the implementation (T08). Fixture: tests/fixtures/applicability_chunks.json.
"""

import json
from pathlib import Path

import pytest

from app.rag.applicability import VOCABULARY, ChunkCondition, term_of

CASES = json.loads((Path(__file__).parent / "fixtures" / "applicability_chunks.json").read_text())


def tag_chunk(chunk, llm=None):
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk as impl

    return impl(chunk, llm=llm)


# --- the condition format (runs without the tagger) ---------------------------------------------


def test_vocabulary_has_the_v0_attributes():
    assert set(VOCABULARY) == {"campus", "degree_level", "year", "student_type", "visa", "topik_level",
                               "english_track", "academic_status"}  # fmt: skip


def test_validate_rejects_values_outside_the_vocabulary():
    with pytest.raises(ValueError, match="degree_level"):
        ChunkCondition(constraints={"degree_level": ["bachelor"]}, campus=["seoul"]).validate()
    with pytest.raises(ValueError, match="unknown attribute"):
        ChunkCondition(constraints={"gpa": ["3.0"]}, campus=["seoul"]).validate()
    with pytest.raises(ValueError, match="both campuses"):
        ChunkCondition(scope="national", campus=["erica"]).validate()
    with pytest.raises(ValueError, match="effective_term"):
        ChunkCondition(campus=["seoul"], effective_term="2026-fall").validate()


def test_validate_requires_an_evidence_quote_for_llm_fields():
    text = "Applicants with a student visa (D-2) may work part-time."
    good = ChunkCondition(constraints={"visa": ["D-2"]}, campus=["erica"],
                          extraction_method={"visa": "llm"}, evidence={"visa": "student visa (D-2)"})  # fmt: skip
    good.validate(text)
    with pytest.raises(ValueError, match="substring"):
        ChunkCondition(**{**good.__dict__, "evidence": {"visa": "D-2 visa holders"}}).validate(text)
    with pytest.raises(ValueError, match="without an evidence quote"):
        ChunkCondition(**{**good.__dict__, "evidence": {}}).validate(text)


def test_normalized_sorts_in_vocabulary_order_and_round_trips():
    c = ChunkCondition(constraints={"topik_level": ["6", "4", "4"], "year": []}, campus=["erica", "seoul"], scope="national")
    assert c.to_dict()["constraints"] == {"topik_level": ["4", "6"]}
    assert c.to_dict()["campus"] == ["seoul", "erica"]
    assert ChunkCondition.from_dict(c.to_dict()).to_dict() == c.to_dict()
    assert c.to_payload() == {"app_topik_level": ["4", "6"], "app_scope": "national", "app_campus": ["seoul", "erica"],
                              "app_superseded": False}  # fmt: skip


def test_term_of():
    assert [term_of(2026, 1), term_of(2026, 6), term_of(2026, 7), term_of(2026, 12)] == ["2026-1", "2026-1", "2026-2", "2026-2"]


# --- the rule tagger on real chunks --------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_rule_tagger_on_real_chunks(case):
    chunk, exp = case["chunk"], case["expected"]
    got = tag_chunk(chunk).normalized()
    got.validate(chunk["text"])
    assert got.constraints == exp["constraints"], case["note"]
    assert (got.scope, got.campus) == (exp["scope"], exp["campus"]), case["note"]
    assert got.effective_term == exp["effective_term"], case["note"]
    assert got.superseded_by == exp["superseded_by"]
    for needle in exp["requirements_contain"]:
        assert any(needle.lower() in r.lower() for r in got.requirements), f"no requirement mentions {needle!r}"
    # how each field was found
    assert got.extraction_method["campus"] == ("rule" if exp["scope"] == "national" else "site_default")
    if exp["superseded_by"]:
        assert got.extraction_method["superseded_by"] == "snapshot"
    assert all(got.extraction_method.get(a) in ("rule", "llm") for a in got.constraints)


def test_the_fixture_covers_the_planned_groups():
    groups = [c["group"] for c in CASES]
    assert sum(g.startswith("erica") for g in groups) == 4 and sum(g.startswith("seoul") for g in groups) == 4
    assert groups.count("unconditioned") == 2 and groups.count("temporal") == 2


# --- LLM fallback (fake LLM, no Ollama) ----------------------------------------------------------

PLAIN = {"doc_id": "x", "site": "erica", "title": "Notice", "source_uri": "https://global.hanyang.ac.kr/eng/x",
         "post_date": None, "superseded_by": None, "kind": "paragraph", "heading_path": [],
         "text": "Holders of a student residence permit for regular degree courses may work up to 25 hours."}  # fmt: skip


def fake_llm(answer: dict):
    calls = []

    def llm(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(answer)

    llm.calls = calls
    return llm


def test_llm_fallback_is_accepted_only_with_valid_values_and_a_real_quote():
    llm = fake_llm({"constraints": {"student_type": ["degree_seeking"]},
                    "evidence": {"student_type": "regular degree courses"}})  # fmt: skip
    got = tag_chunk(PLAIN, llm=llm)
    assert llm.calls, "the rules found nothing, so the LLM must be asked"
    assert got.constraints == {"student_type": ["degree_seeking"]}
    assert got.extraction_method["student_type"] == "llm"
    got.validate(PLAIN["text"])


@pytest.mark.parametrize("answer", [
    {"constraints": {"student_type": ["full_time"]}, "evidence": {"student_type": "regular degree courses"}},  # not in vocabulary
    {"constraints": {"student_type": ["degree_seeking"]}, "evidence": {"student_type": "degree-seeking students"}},  # invented quote
    {"constraints": {"student_type": ["degree_seeking"]}},  # no quote
], ids=["bad_value", "bad_quote", "no_quote"])  # fmt: skip
def test_llm_fallback_output_that_fails_validation_is_dropped(answer):
    got = tag_chunk(PLAIN, llm=fake_llm(answer))
    assert got.constraints == {}
    got.validate(PLAIN["text"])


def test_llm_garbage_does_not_crash_the_tagger():
    got = tag_chunk(PLAIN, llm=lambda prompt: "Sure! Here are the tags: student_type=degree")
    assert got.constraints == {} and got.campus == ["erica"]


# --- the registered block -------------------------------------------------------------------------


def test_registered_block_tags_chunks_without_the_llm():
    from app.rag.registry import create_block, validate_config
    from app.rag.schemas import Services

    config = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {"llm_fallback": False}}})
    step = config["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], Services(db=None, ollama=None, settings=None))
    tags = block.tag_chunks([CASES[0]["chunk"], CASES[9]["chunk"]])
    assert [t.scope for t in tags] == ["national", "campus"]
    assert tags[0].constraints["year"] == ["1", "2"] and tags[1].constraints == {}


# --- T08b rule fixes (found on non-fixture snapshot spans) ----------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("Column 1: Year 3, 4 / 3, 4 term; Undergraduate: KRW 300,000", {"year": ["3", "4"], "degree_level": ["undergraduate"]}),
    ("Graduate: KRW 300,000", {"degree_level": ["master", "doctoral"]}),
    ("Open to graduate students only.", {"degree_level": ["master", "doctoral"]}),
    ("Undergraduate students may apply.", {"degree_level": ["undergraduate"]}),
    ("All students for 1 semester. (Except students who took a leave of absence, completed coursework)", {}),
    ("Enrolled students must apply (except students on leave of absence).", {"academic_status": ["enrolled"]}),
], ids=["year_comma", "graduate_cell", "graduate_students", "undergraduate_only", "except_clause", "enrolled_except"])  # fmt: skip
def test_t08b_rule_fixes(text, expected):
    got = tag_chunk({**PLAIN, "title": "", "text": text})
    assert got.constraints == expected


# --- topik_level thresholds are ordinal ------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("Applicants with TOPIK 3 or above may apply.", ["3", "4", "5", "6"]),
    ("TOPIK level 4 or higher is required.", ["4", "5", "6"]),
    ("Korean proficiency is required (TOPIK Lv4~6).", ["4", "5", "6"]),
    ("TOPIK level 5+ students get a bonus.", ["5", "6"]),
], ids=["or_above", "or_higher", "range_to_6", "plus"])  # fmt: skip
def test_topik_thresholds_expand_to_every_higher_level(text, expected):
    assert tag_chunk({**PLAIN, "title": "", "text": text}).constraints["topik_level"] == expected


def test_llm_topik_threshold_is_expanded_and_all_levels_is_no_constraint():
    text = "Scholarship for students. Korean: TOPIK three or above, see TOPIK 3 or above in the table."
    narrow = fake_llm({"constraints": {"topik_level": ["3"]}, "evidence": {"topik_level": "TOPIK 3 or above"}})
    # rules see the same threshold here, so call the fallback directly on an untagged condition
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import _apply_llm_fallback

    condition = ChunkCondition(campus=["erica"])
    _apply_llm_fallback(condition, text, narrow, None)
    assert condition.constraints == {"topik_level": ["3", "4", "5", "6"]}
    every = fake_llm({"constraints": {"topik_level": list(VOCABULARY["topik_level"])}, "evidence": {"topik_level": "TOPIK three"}})
    condition = ChunkCondition(campus=["erica"])
    _apply_llm_fallback(condition, text, every, details := {})
    assert condition.constraints == {} and details["llm_fallback"]["rejected_fields"] == {"topik_level": "every value allowed = no constraint"}
