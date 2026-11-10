"""Focused T08c checks that call the extractor directly."""

import json

import pytest

from app.rag.applicability import ChunkCondition
from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import _apply_llm_fallback, tag_chunk


BASE = {
    "doc_id": "x",
    "site": "erica",
    "title": "Notice",
    "source_uri": "https://global.hanyang.ac.kr/eng/x",
    "post_date": None,
    "superseded_by": None,
    "kind": "paragraph",
    "heading_path": [],
}


def fake_llm(answer: dict):
    return lambda prompt: json.dumps(answer)


@pytest.mark.parametrize(
    "answer, expected, mapped",
    [
        ({"constraints": {"visa": ["F-2"]}, "evidence": {"visa": "residence permit"}}, {"visa": ["other"]}, "visa"),
        ({"constraints": {"student_type": ["volunteer"]}, "evidence": {"student_type": "residence permit"}}, {}, "student_type"),
        ({"constraints": {"semester": ["2"]}, "evidence": {"semester": "residence permit"}}, {}, "semester"),
    ],
)
def test_postcheck_p1_fixed_mappings(answer, expected, mapped):
    chunk = {**BASE, "text": "Holders of a student residence permit may work part-time."}
    details = {}
    result = tag_chunk(chunk, llm=fake_llm(answer), trace_details=details)

    assert result.constraints == expected
    assert mapped in details["llm_fallback"]["mapped_fields"]
    assert mapped not in details["llm_fallback"]["rejected_fields"]


def test_postcheck_p1_uses_fixed_rejection_labels():
    text = "TOPIK certificate is optional."
    condition = ChunkCondition(campus=["erica"])
    answer = {"constraints": {"topik_level": ["3"]}, "evidence": {"topik_level": "TOPIK certificate"}}
    details = {}

    _apply_llm_fallback(condition, text, fake_llm(answer), details)

    assert condition.constraints == {}
    assert condition.requirements == ["preference: TOPIK certificate is optional."]
    assert details["llm_fallback"]["rejected_fields"] == {"topik_level": "preference"}


@pytest.mark.parametrize("wording", ["TOPIK 4 or above gives a bonus.", "TOPIK 4 or above is an advantage."])
def test_rule_preferences_are_requirements_not_constraints(wording):
    result = tag_chunk({**BASE, "text": wording})

    assert "topik_level" not in result.constraints
    assert result.requirements[0].startswith("preference:")


def test_exempted_from_the_korean_standard_maps_to_exempt():
    result = tag_chunk({**BASE, "text": "Exempted from the Korean Language Standards"})

    assert result.constraints == {"korean_standard": ["exempt"]}


# --- review fixes (Claude Code): korean_standard=exempt and applicant must not fire on unrelated words ---

from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk as _tag  # noqa: E402

_BASE = {"doc_id": "x", "site": "seoul", "source_uri": "u", "post_date": None, "superseded_by": None, "kind": "paragraph",
         "heading_path": []}  # fmt: skip


def test_bare_exempted_is_not_the_korean_standard():
    got = _tag({**_BASE, "title": "COVID-19 Vaccination for Foreign Residents", "text": "Those vaccinated are exempted from quarantine."})
    assert "korean_standard" not in got.constraints
    got = _tag({**_BASE, "title": "Undergraduate Admission Guideline", "text": "Applicants exempted from the Korean Language Standards must submit proof."})
    assert got.constraints["korean_standard"] == ["exempt"]


def test_visa_application_guideline_is_not_an_admission_guide():
    got = _tag({**_BASE, "title": "Group Visa Application Guideline", "text": "Applicants must submit their passport."})
    assert "applicant" not in got.constraints.get("academic_status", [])
