"""T08d rule fixes for index r4 (PLAYBOOK A20/A21), on 14 real r3 chunks that the automated audit
found wrong. Written by Claude Code before the implementation. Fixture: tests/fixtures/applicability_chunks_r4.json
(each case has a `note` with the reason; the chunk_id points into hyu_20261110_97dc1269_r3).

Each test checks only the attributes the fix is about.
"""

import json
from pathlib import Path

import pytest

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures" / "applicability_chunks_r4.json").read_text())}


def tag(case_id):
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk

    return tag_chunk(CASES[case_id]["chunk"])


def status(case_id):
    return tag(case_id).constraints.get("academic_status")


# --- academic_status: applicant / admitted inside admission guides ---------------------------------


def test_every_chunk_of_an_admission_guide_is_for_applicants():
    assert status("R01") == ["applicant"]


@pytest.mark.parametrize("case_id", ["R02", "R03"])
def test_acceptance_sections_of_an_admission_guide_are_for_admitted_students(case_id):
    assert status(case_id) == ["admitted_not_enrolled"]


def test_leave_of_absence_information_in_an_admission_guide_stays_applicant():
    assert status("R04") == ["applicant"]


# --- academic_status: stated status only (decision c) ----------------------------------------------


@pytest.mark.parametrize("case_id", ["R05", "R06"])
def test_a_leave_of_absence_application_is_for_enrolled_students(case_id):
    assert status(case_id) == ["enrolled"]


def test_return_to_school_is_for_students_on_leave():
    assert status("R07") == ["leave_of_absence"]


def test_students_who_enrolled_at_is_a_stated_status():
    assert status("R08") == ["enrolled"]


def test_enrolled_is_never_inferred_from_the_audience():
    assert status("R09") is None


# --- student_type and degree_level: the ineligibility list is not the audience ----------------------


def test_ineligibility_list_gives_no_values_and_degree_program_is_degree_seeking():
    condition = tag("R08")
    assert condition.constraints.get("student_type") == ["degree_seeking"]
    assert "degree_level" not in condition.constraints  # "researchers (PhD)" is in the ineligibility list


# --- year: every range in the chunk, never a duration ----------------------------------------------


@pytest.mark.parametrize("case_id", ["R10", "R11"])
def test_year_unions_every_range_in_the_chunk(case_id):
    assert tag(case_id).constraints.get("year") == ["1", "2", "3", "4"]


def test_a_duration_is_not_a_year_of_study():
    assert "year" not in tag("R14").constraints


# --- visa: the target visa of a change, not the old one --------------------------------------------


@pytest.mark.parametrize("case_id, expected", [("R12", ["D-10"]), ("R07", ["D-2"])])
def test_visa_change_keeps_only_the_target_visa(case_id, expected):
    assert tag(case_id).constraints.get("visa") == expected


# --- audit rule 5b: an alternative outside the vocabulary means no TOPIK constraint -----------------


@pytest.mark.parametrize("case_id, alternative", [("R11", "KIIP"), ("R12", "Social Integration Program")])
def test_topik_with_an_out_of_vocabulary_alternative_is_a_requirement(case_id, alternative):
    condition = tag(case_id)
    assert "topik_level" not in condition.constraints
    assert not any("topik_level" in group for group in condition.any_of)
    assert any(alternative in requirement for requirement in condition.requirements)


def test_plain_topik_threshold_is_still_a_constraint():
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk

    chunk = {**CASES["R12"]["chunk"], "text": "Applicants must hold TOPIK level 4 or higher.", "heading_path": []}
    assert tag_chunk(chunk).constraints.get("topik_level") == ["4", "5", "6"]


# --- LLM off: a cue without a rule is unknown, never unconditioned (A6) -----------------------------


def test_cue_without_a_rule_is_rule_cue_unknown_when_the_llm_is_off():
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import TAG_BUCKETS
    from app.rag.registry import create_block, validate_config
    from app.rag.schemas import Services

    config = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {"llm_fallback": False}}})
    step = config["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], Services(db=None, ollama=None, settings=None))
    no_cue = {**CASES["R13"]["chunk"], "text": "The office opens at 9 am.", "heading_path": []}
    tags = block.tag_chunks([CASES["R13"]["chunk"], no_cue])
    assert "rule_cue_unknown" in TAG_BUCKETS
    assert block.buckets == ["rule_cue_unknown", "rule_unconditioned"]
    assert "english_track" not in tags[0].constraints  # "fluent in Korean" is not a track
    assert block.summary["llm_called"] == 0
