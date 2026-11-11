"""Pipeline-level check for the T08d rules-only unknown bucket."""

from app.rag.pipeline import _tag_chunks
from app.rag.registry import create_block, validate_config
from app.rag.schemas import Services


def test_rule_cue_unknown_is_stored_as_unknown_condition_status():
    step = validate_config({
        "metadata_extraction": {"method": "applicability_extractor", "params": {"llm_fallback": False}},
    })["metadata_extraction"]
    block = create_block(
        "metadata_extraction",
        step["method"],
        step["params"],
        Services(db=None, ollama=None, settings=None),
    )
    tag_input = {
        "doc_id": "r4-extra",
        "site": "erica",
        "title": "Notice",
        "heading_path": [],
        "post_date": None,
        "superseded_by": None,
        "text": "International students can read the monthly newsletter.",
    }
    chunks = [{"text": tag_input["text"]}]

    summary = _tag_chunks(block, chunks, [tag_input], {})

    assert chunks[0]["tag_bucket"] == "rule_cue_unknown"
    assert chunks[0]["condition_status"] == "unknown"
    assert summary["partition"]["rule_cue_unknown"] == 1
    assert summary["llm_called"] == 0
