"""Small contract checks not covered by the real r5 audit chunks."""

import pytest

from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import tag_chunk


def chunk(text: str, *, title: str = "Notice", heading_path: list[str] | None = None) -> dict:
    return {"site": "seoul", "title": title, "heading_path": heading_path or [], "text": text,
            "post_date": None, "superseded_by": None}  # fmt: skip


def test_gks_u_heading_overrides_text_degree_without_inventing_evidence():
    result = tag_chunk(chunk("Master's degree holders may apply.", heading_path=["2026 GKS-U Application Guidelines"]))

    assert result.constraints["degree_level"] == ["undergraduate"]
    assert result.extraction_method["degree_level"] == "rule"
    assert "degree_level" not in result.evidence


@pytest.mark.parametrize("qualification", [
    "Applicants must hold a bachelor's degree.",
    "Applicants have completed a bachelor's degree.",
    "Holders of a bachelor's degree may apply.",
    "Applicants graduated with a bachelor's degree.",
    "Applicants completed your undergraduate program.",
    "A bachelor's degree (four years) or higher is required.",
])
def test_prior_qualifications_are_not_undergraduate_audiences(qualification):
    assert "degree_level" not in tag_chunk(chunk(qualification)).constraints


def test_named_school_is_ignored_but_graduate_students_still_match():
    assert "degree_level" not in tag_chunk(chunk("ECE Paris Graduate School of Engineering")).constraints
    assert tag_chunk(chunk("Graduate school students may apply.")).constraints["degree_level"] == ["master", "doctoral"]


def test_visa_noise_does_not_hide_another_visa_condition():
    text = "Regarding the D-4 visa, please contact the IIE. D-2 visa holders may apply."

    assert tag_chunk(chunk(text)).constraints["visa"] == ["D-2"]
