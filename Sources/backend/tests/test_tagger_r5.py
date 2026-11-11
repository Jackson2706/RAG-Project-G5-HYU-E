"""T08e rule fixes for index r5 (PLAYBOOK A24), on 12 real r4 chunks from the dev-100 audit sample.
Written by Claude Code before the implementation. Fixture: tests/fixtures/applicability_chunks_r5.json
(each case has a `note`; chunk_ids point into hyu_20261110_97dc1269_r4). Each test checks only the
attribute its fix is about.
"""

import json
from pathlib import Path

import pytest

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures" / "applicability_chunks_r5.json").read_text())}


def tag(case_id):
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk

    return tag_chunk(CASES[case_id]["chunk"]).constraints


# --- fix 1: an admission guide's own title sets the degree level ------------------------------------


@pytest.mark.parametrize("case_id", ["S01", "S02", "S03", "S04"])
def test_graduate_admission_guides_give_master_and_doctoral(case_id):
    assert tag(case_id).get("degree_level") == ["master", "doctoral"]


def test_undergraduate_admission_guide_gives_undergraduate():
    assert tag("S05").get("degree_level") == ["undergraduate"]


def test_degree_is_inherited_only_inside_the_guide():
    from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk

    outside = {**CASES["S01"]["chunk"], "title": "Scholarship Information", "heading_path": ["Scholarship Information"]}
    assert "degree_level" not in tag_chunk(outside).constraints


def test_inherited_degree_count_is_logged():
    from app.rag.registry import create_block, validate_config
    from app.rag.schemas import Services

    config = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {"llm_fallback": False}}})
    step = config["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], Services(db=None, ollama=None, settings=None))
    block.tag_chunks([CASES["S01"]["chunk"], CASES["S07"]["chunk"]])
    assert block.summary["degree_inherited"] == 1


# --- fix 1b and 2: prior qualifications and institution names are not the audience ------------------


@pytest.mark.parametrize("case_id", ["S06", "S07"])
def test_prior_qualification_and_institution_name_give_no_degree(case_id):
    assert "degree_level" not in tag(case_id)


# --- fix 3: student_type phrases ---------------------------------------------------------------------


@pytest.mark.parametrize("case_id, expected", [
    ("S08", ["degree_seeking"]),
    ("S09", ["degree_seeking", "language_program"]),
    ("S10", ["language_program"]),
    ("S12", ["degree_seeking", "exchange", "language_program"]),
])
def test_student_type_phrases(case_id, expected):
    assert tag(case_id).get("student_type") == expected


# --- fix 4: contact lines and misuse warnings are not visa conditions --------------------------------


@pytest.mark.parametrize("case_id", ["S04", "S05", "S11"])
def test_contact_lines_and_warnings_give_no_visa(case_id):
    assert "visa" not in tag(case_id)
