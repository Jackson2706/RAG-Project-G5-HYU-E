"""T09: snapshot → documents, span lookup, LLM cue filter + cache, Qdrant payload, VERIFY logic."""

import json

import pytest

from app.config import DATA_DIR
from app.rag.applicability import ChunkCondition
from app.rag.blocks.ingestion.metadata_extraction import applicability_extractor as extractor_module
from app.rag.registry import create_block, validate_config
from app.rag.schemas import Chunk
from app.rag.snapshot import HANGUL, evaluate_checks, load_snapshot, source_spans_match, to_parsed_document

SNAPSHOT = "hyu-20261110-97dc1269"


def span_row(pieces):
    """A synthetic snapshot row in the real structure: text + spans (kind, char_start, char_end)."""
    text, spans = "", []
    for kind, piece in pieces:
        if text:
            text += "\n"
        spans.append({"kind": kind, "char_start": len(text), "char_end": len(text) + len(piece), "source": "page"})
        text += piece
    return {"doc_id": "d1", "site": "seoul", "campus": "seoul", "title": "/ Undergraduate Admission Guideline / extra",
            "source_uri": "https://oia.hanyang.ac.kr/x", "post_date": "2026-03-05", "superseded_by": None,
            "source_sha256": "abc", "text": text, "spans": spans}  # fmt: skip


ROW = span_row([
    ("paragraph", "Welcome to the guide."),
    ("heading", "Tuition"),
    ("paragraph", "Pay by March 1."),
    ("heading", "등록금 납부 안내"),  # Korean heading: stays in the body, header stays "Tuition"
    ("table_row", "Degree: Bachelor's; Fee: KRW 100"),
    ("table_row", "Degree: Master's; Fee: KRW 200"),
])  # fmt: skip


def test_snapshot_row_becomes_english_sections_with_exact_offsets():
    doc, lookup = to_parsed_document(ROW, SNAPSHOT)
    assert doc.title == "Undergraduate Admission Guideline"
    assert doc.declared_metadata["title_original"] == ROW["title"]
    assert [s.heading for s in doc.sections] == ["Undergraduate Admission Guideline", "Tuition"]
    assert "등록금 납부 안내" in doc.sections[1].text
    full = doc.full_text()
    expected = ["Welcome to the guide.", "Pay by March 1.", "등록금 납부 안내",
                "Degree: Bachelor's; Fee: KRW 100", "Degree: Master's; Fee: KRW 200"]  # fmt: skip
    assert [full[span.start:span.end] for span in lookup.spans] == expected
    assert [s.kind for s in lookup.spans][-2:] == ["table_row", "table_row"]


def test_long_sections_are_cut_at_span_boundaries():
    doc, _ = to_parsed_document(ROW, SNAPSHOT, count_tokens=lambda t: len(t.split()), max_tokens=12)
    tuition = [s for s in doc.sections if s.heading == "Tuition"]
    assert len(tuition) > 1  # same heading, next section
    assert all(not s.text.startswith(";") for s in tuition)


def test_chunk_kind_and_heading_path_come_from_the_covered_spans():
    doc, lookup = to_parsed_document(ROW, SNAPSHOT)
    full = doc.full_text()
    rows = [s for s in lookup.spans if s.kind == "table_row"]
    table = Chunk(text=full[rows[0].start:rows[-1].end], section="Tuition", page_number=None, token_count=1,
                  start=rows[0].start, end=rows[-1].end)  # fmt: skip
    got = lookup.chunk_input(doc, table)
    assert got["kind"] == "table_row" and got["heading_path"] == ["Tuition"] and got["site"] == "seoul"
    assert got["source_spans"] == [[row.snapshot_start, row.snapshot_end] for row in rows]
    first = doc.sections[1]
    start = doc.section_starts()[1]
    mixed = Chunk(text=first.text, section="Tuition", page_number=None, token_count=1, start=start, end=start + len(first.text))
    assert lookup.chunk_input(doc, mixed)["kind"] == "mixed"


def test_real_snapshot_has_english_headers_and_fits_the_embedder():
    if not (DATA_DIR / "HYU" / "snapshots" / SNAPSHOT / "documents.jsonl").exists():
        pytest.skip(f"snapshot {SNAPSHOT} not present (HYU_DATA_DIR override?)")
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5", local_files_only=True)
    except OSError:
        pytest.skip("bge tokenizer not in the local Hugging Face cache")
    count = lambda t: len(tok(t, add_special_tokens=False)["input_ids"])  # noqa: E731
    docs = load_snapshot(SNAPSHOT, count, 320)
    assert len(docs) == 362
    index_ids = {d.declared_metadata["doc_id"] for d, _ in docs}
    newer = [d.declared_metadata["superseded_by"] for d, _ in docs if d.declared_metadata["superseded_by"]]
    assert newer and all(i in index_ids for i in newer)  # superseded_by points at an index doc_id
    for doc, _ in docs:
        assert all(not (s.heading and HANGUL.search(s.heading)) for s in doc.sections), doc.source_uri
        for s in doc.sections:
            if count(s.text) <= 320:  # longer single spans are windowed by the chunker at 320 tokens
                assert count(f"{s.heading}\n{s.text}" if s.heading else s.text) + 2 <= 512


# --- LLM cue filter and cache (fake Ollama) -------------------------------------------------------

UNTAGGED = {"doc_id": "x", "site": "erica", "title": "", "source_uri": "u", "post_date": None, "superseded_by": None,
            "kind": "paragraph", "heading_path": []}  # fmt: skip


def test_llm_is_asked_only_with_a_cue_and_answers_are_cached(services, fake_ollama, tmp_path):
    fake_ollama.models = [{"name": "qwen3.5:4b", "details": {}, "capabilities": ["completion", "thinking"], "digest": "sha256:x"}]
    fake_ollama.answer = json.dumps({"constraints": {"student_type": ["exchange"]}, "evidence": {"student_type": "partner-university applicants"}})
    step = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {}}})["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], services)
    no_cue = {**UNTAGGED, "text": "The office opens at 9:00."}
    cue = {**UNTAGGED, "text": "Only partner-university applicants may join."}  # cue, but no rule tag
    cache = tmp_path / "llm_tags.jsonl"

    first = block.tag_chunks([no_cue, cue], cache_path=cache)
    assert len(fake_ollama.requests) == 1  # the chunk without a cue never reaches the LLM
    assert block.summary["llm_called"] == 1 and block.summary["llm_accepted"] == 1
    assert first[1].constraints == {"student_type": ["exchange"]} and first[1].extraction_method["student_type"] == "llm"
    assert block.summary["llm"] == {"enabled": True, "role": "auxiliary", "model": "qwen3.5:4b", "digest": "sha256:x",
                                    "prompt_version": extractor_module.TAG_PROMPT_VERSION, "temperature": 0, "num_ctx": 4096, "seed": 42,
                                    "thinking": "off", "cache_path": str(cache), "postcheck_version": extractor_module.POSTCHECK_VERSION,
                                    "vocabulary_version": "v1"}  # fmt: skip
    assert fake_ollama.requests[0]["options"] | {"think": fake_ollama.requests[0]["think"]} == {
        "temperature": 0, "num_predict": 256, "num_ctx": 4096, "seed": 42, "think": False,
    }

    again = block.tag_chunks([no_cue, cue], cache_path=cache)
    assert len(fake_ollama.requests) == 1 and block.summary["llm_cache_hits"] == 1
    assert again[1].to_dict() == first[1].to_dict()


def test_llm_cache_key_uses_digest_prompt_version_and_chunk_text(services, fake_ollama, tmp_path, monkeypatch):
    fake_ollama.models = [{"name": "qwen3.5:4b", "details": {}, "capabilities": ["completion"], "digest": "digest-a"}]
    fake_ollama.answer = json.dumps({"constraints": {"student_type": ["exchange"]},
                                     "evidence": {"student_type": "partner-university applicants"}})  # fmt: skip
    step = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {}}})["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], services)
    chunk = {**UNTAGGED, "text": "Only partner-university applicants may join."}
    cache = tmp_path / "llm_tags.jsonl"

    block.tag_chunks([chunk], cache_path=cache)
    block.tag_chunks([chunk], cache_path=cache)
    assert len(fake_ollama.requests) == 1 and block.summary["llm_cache_hits"] == 1

    fake_ollama.models[0]["digest"] = "digest-b"
    block.tag_chunks([chunk], cache_path=cache)
    assert len(fake_ollama.requests) == 2 and block.summary["llm_cache_hits"] == 0

    monkeypatch.setattr(extractor_module, "TAG_PROMPT_VERSION", extractor_module.TAG_PROMPT_VERSION + "-next")
    block.tag_chunks([chunk], cache_path=cache)
    assert len(fake_ollama.requests) == 3 and block.summary["llm_cache_hits"] == 0
    assert len(cache.read_text().splitlines()) == 3


# --- Qdrant payload and VERIFY ---------------------------------------------------------------------


def test_qdrant_payload_has_the_compact_applicability_fields(db):
    condition = ChunkCondition(constraints={"degree_level": ["undergraduate"]}, campus=["erica"], effective_term="2026-1")
    chunk = {"chunk_id": "00000000-0000-0000-0000-000000000001", "doc_id": "d", "text": "t", "applicability": condition.to_dict()}
    db.replace_index([{"doc_id": "d", "metadata": {}}], [chunk], [[1.0, 0.0, 0.0, 0.0]], 4)
    payload = db.qdrant.scroll(db.collection, limit=1, with_payload=True)[0][0].payload
    assert {k: payload[k] for k in condition.to_payload()} == condition.to_payload()
    assert payload["app_degree_level"] == ["undergraduate"] and payload["app_campus"] == ["erica"]


GOOD = {"expected_documents": 362, "mongo_documents": 362, "mongo_chunks": 10, "qdrant_points": 10, "dimension": 384,
        "unique_chunk_ids": 10, "points_without_chunk": 0, "max_embedded_tokens": 344, "truncated_by_embedder": 0,
        "invalid_applicability": 0, "llm_errors": 0, "span_text_mismatches": 0,
        "partition": {"rule_tagged": 4, "rule_unconditioned": 3, "llm_tagged": 1, "llm_unconditioned": 1, "llm_rejected": 1},
        "points_missing_app_fields": 0, "unmasked_emails": 0, "hangul_headers": 0,
        "default_before": {"documents": 5}, "default_after": {"documents": 5}}  # fmt: skip


def test_llm_error_is_not_cached_and_blocks_verify(services, fake_ollama, tmp_path):
    fake_ollama.models = [{"name": "qwen3.5:4b", "details": {}, "capabilities": ["completion"], "digest": "sha256:x"}]
    fake_ollama.fail = "500"
    step = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {}}})["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], services)
    cache = tmp_path / "llm_tags.jsonl"

    block.tag_chunks([{**UNTAGGED, "text": "Only partner-university applicants may join."}], cache_path=cache)

    assert block.summary["llm_errors"] == 1 and block.summary["llm_rejected_total"] == 0
    assert not cache.exists()
    checks, status = evaluate_checks({**GOOD, "llm_errors": 1})
    assert status == "built" and not checks["llm_errors_zero"]


def test_source_span_text_accepts_whole_spans_and_one_span_window():
    snapshot_text = "Alpha\nBeta\nA long source span"
    assert source_spans_match("Alpha\nBeta", snapshot_text, [[0, 5], [6, 10]])
    assert source_spans_match("long source", snapshot_text, [[11, 29]])
    assert not source_spans_match("Alpha", snapshot_text, [[0, 5], [6, 10]])


def test_verify_passes_only_when_every_check_passes():
    checks, status = evaluate_checks(GOOD)
    assert status == "verified" and all(checks.values())
    checks, status = evaluate_checks({**GOOD, "default_after": {"documents": 4}})
    assert status == "built" and not checks["default_index_unchanged"]
    assert evaluate_checks({**GOOD, "unmasked_emails": 1})[1] == "built"
    checks, status = evaluate_checks({**GOOD, "span_text_mismatches": 1})
    assert status == "built" and not checks["span_text_matches"]


def test_every_chunk_lands_in_one_bucket_and_refused_answers_are_unknown(services, fake_ollama, tmp_path):
    from app.rag.pipeline import _tag_chunks

    fake_ollama.models = [{"name": "qwen3.5:4b", "details": {}, "capabilities": ["completion"], "digest": "sha256:x"}]
    step = validate_config({"metadata_extraction": {"method": "applicability_extractor", "params": {}}})["metadata_extraction"]
    block = create_block("metadata_extraction", step["method"], step["params"], services)
    inputs = [{**UNTAGGED, "text": t} for t in ("Year 1-2 Bachelor's students may apply.",  # rule_tagged
                                               "The office opens at 9:00.",  # no cue -> rule_unconditioned
                                               "Only partner-university applicants may join.")]  # cue -> LLM  # fmt: skip
    answers = {"llm_unconditioned": {"constraints": {}, "evidence": {}},
               "llm_rejected": {"constraints": {"student_type": ["full_time"]}, "evidence": {"student_type": "applicants"}}}
    for expected, answer in answers.items():
        fake_ollama.answer = json.dumps(answer)
        chunks = [{"text": i["text"]} for i in inputs]
        summary = _tag_chunks(block, chunks, inputs, {})
        assert [c["tag_bucket"] for c in chunks] == ["rule_tagged", "rule_unconditioned", expected]
        assert chunks[2]["condition_status"] == ("unconditioned" if expected == "llm_unconditioned" else "unknown")
        assert sum(summary["partition"].values()) == 3
    assert not evaluate_checks({**GOOD, "partition": {"rule_tagged": 9}})[0]["partition_complete"]
