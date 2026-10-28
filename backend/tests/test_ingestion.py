from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ingestion import metadata as md
from app.ingestion.chunking import chunk_document
from app.ingestion.loaders import discover_files, stable_uuid
from app.ingestion.parsers import parse_file
from app.services.embeddings import validate_vectors
from tests.conftest import SAMPLES, RegexTokenizer

LOAD = {"file_types": ["pdf", "txt", "md", "html"], "recursive": True, "max_file_mb": 1}
PARSE = {"preserve_tables": True, "normalize_unicode": True}
CHUNK = {"chunk_size": 40, "chunk_overlap": 8, "min_chunk_size": 4, "max_chunk_size": 60, "preserve_headings": True, "tokenizer_id": "regex"}


def make_pdf(pages: list[str]) -> bytes:
    """Minimal valid PDF with one text line per page (Helvetica)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for text in pages:
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        page_no = len(objs) + 1
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {page_no + 1} 0 R /Resources << /Font << /F1 {{FONT}} 0 R >> >> >>")
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content.decode()}\nendstream")
        kids.append(f"{page_no} 0 R")
    font_no = len(objs) + 1
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body.replace('{FONT}', str(font_no))}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


# ------------------------------------------------------------------ loading & identity


def test_discover_reports_unsupported_and_empty_files(tmp_path: Path):
    (tmp_path / "b.md").write_text("# B\n\ntext")
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "empty.md").write_text("")
    (tmp_path / "big.txt").write_bytes(b"x" * (2 * 1024 * 1024))
    files, issues = discover_files(tmp_path, tmp_path, LOAD)
    assert [f.path.name for f in files] == ["a.txt", "b.md"]  # sorted, deterministic
    reasons = {Path(i.path).name: i.error for i in issues}
    assert "unsupported" in reasons["image.png"]
    assert "empty" in reasons["empty.md"]
    assert "limit" in reasons["big.txt"]


def test_doc_identity_is_stable_but_hash_tracks_content(tmp_path: Path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nversion one")
    first = discover_files(tmp_path, tmp_path, LOAD)[0][0]
    p.write_text("# Title\n\nversion two")
    second = discover_files(tmp_path, tmp_path, LOAD)[0][0]
    assert first.doc_id == second.doc_id == stable_uuid("local://doc.md")
    assert first.sha256 != second.sha256


# ------------------------------------------------------------------ parsing


def test_markdown_front_matter_sections_tables_and_spans():
    doc = parse_file(SAMPLES / "orientation_guide.md", "md", "structure_aware", PARSE)
    assert doc.title == "New Student Orientation Guide (Sample)"
    assert doc.declared_metadata["campus"] == "SEOUL"
    kinds = {b.kind for b in doc.blocks}
    assert {"heading", "paragraph", "table", "list"} <= kinds
    table = next(b for b in doc.blocks if b.kind == "table")
    assert table.section_path[-1] == "Schedule" and "---" not in table.text
    for b in doc.blocks:
        assert doc.content[b.span.start : b.span.end] == b.text


def test_basic_parser_records_no_structure():
    doc = parse_file(SAMPLES / "orientation_guide.md", "md", "basic", PARSE)
    assert all(b.kind == "paragraph" and b.section_path == [] for b in doc.blocks)


def test_html_meta_headings_and_tables():
    doc = parse_file(SAMPLES / "scholarships.html", "html", "structure_aware", PARSE)
    assert doc.title == "Scholarship Application Guide (Sample)"
    assert doc.declared_metadata["campus"] == "ALL" and doc.declared_metadata["language"] == "en"
    table = next(b for b in doc.blocks if b.kind == "table")
    assert "Need-based | Household income certificate" in table.text
    assert table.section_path == ["Scholarship Application Guide (Sample)", "Required Documents"]


def test_pdf_pages_are_recorded(tmp_path: Path):
    path = tmp_path / "guide.pdf"
    path.write_bytes(make_pdf(["Orientation starts on Monday.", "Scholarship applications close in February."]))
    doc = parse_file(path, "pdf", "structure_aware", PARSE)
    assert doc.page_count == 2
    assert [b.page_number for b in doc.blocks] == [1, 2]
    assert "Scholarship applications" in doc.blocks[1].text
    assert any("headings and table structure are not detected" in w for w in doc.warnings)


def test_unparseable_input_raises(tmp_path: Path):
    path = tmp_path / "blank.md"
    path.write_text("\n\n   \n")
    with pytest.raises(ValueError, match="no extractable text"):
        parse_file(path, "md", "structure_aware", PARSE)


# ------------------------------------------------------------------ chunking


def _chunks(method="structure_aware", params=CHUNK, name="course_registration.md"):
    doc = parse_file(SAMPLES / name, "md", "structure_aware", PARSE)
    return doc, chunk_document(doc, "doc", "v1", method, params, RegexTokenizer())


def test_chunk_ids_are_deterministic_and_spans_exact():
    doc, a = _chunks()
    _, b = _chunks()
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert len({c.chunk_id for c in a}) == len(a)
    for c in a:
        assert doc.content[c.source_span.start : c.source_span.end] == c.text
        assert c.token_count == len(RegexTokenizer().offsets(c.text))
        assert c.token_count <= CHUNK["max_chunk_size"]


def test_chunk_ids_change_with_configuration():
    _, a = _chunks()
    _, b = _chunks(params={**CHUNK, "chunk_size": 48})
    assert {c.chunk_id for c in a}.isdisjoint({c.chunk_id for c in b})


def test_structure_aware_keeps_sections_separate_and_headings_in_header():
    _, chunks = _chunks()
    for c in chunks:
        assert c.section_path, "every chunk of a headed document has a section"
        assert c.context_header.startswith("Course Registration Handbook (Sample)")
    sections = [c.section_title for c in chunks]
    assert "Credit Limits" in sections and "Dropping a Course" in sections


def test_fixed_windows_overlap_exactly():
    params = {"chunk_size": 30, "chunk_overlap": 10, "preserve_headings": False, "tokenizer_id": "regex"}
    doc, chunks = _chunks("fixed", params)
    tok = RegexTokenizer().offsets(doc.content)
    starts = [next(i for i, (s, _) in enumerate(tok) if s == c.source_span.start) for c in chunks]
    assert all(b - a == 20 for a, b in zip(starts, starts[1:]))  # step = size − overlap
    assert all(c.token_count == 30 for c in chunks[:-1])
    assert chunks[-1].source_span.end == tok[-1][1]  # nothing lost at the end


def test_long_block_falls_back_to_windows(tmp_path: Path):
    path = tmp_path / "long.md"
    path.write_text("# Rules\n\n" + " ".join(f"word{i}" for i in range(200)) + ".")
    doc = parse_file(path, "md", "structure_aware", PARSE)
    chunks = chunk_document(doc, "d", "v", "structure_aware", CHUNK, RegexTokenizer())
    assert len(chunks) > 3
    assert all(c.token_count <= CHUNK["max_chunk_size"] for c in chunks)
    assert chunks[0].text.startswith("Rules")  # heading attached to the first window


# ------------------------------------------------------------------ metadata


def test_declared_metadata_never_invents_values():
    fields, prov, warnings = md.extract_document_metadata({"campus": "Mars", "audience": "international, aliens"}, "T", "text", "declared", {}, "en")
    assert "campus" not in fields and fields["audience"] == ["international"]
    assert len(warnings) == 2
    assert prov["language"] == "configured_default"
    assert "topics" not in fields and "academic_year" not in fields


def test_rule_based_metadata_is_marked_as_rule():
    text = "Scholarship applications for the 2026 academic year at the ERICA campus."
    fields, prov, _ = md.extract_document_metadata({}, None, text, "rule_based",
                                                   {"detect_topics": True, "detect_campus": True, "detect_academic_year": True}, "en")  # fmt: skip
    assert fields["campus"] == "ERICA" and prov["campus"] == "rule"
    assert fields["academic_year"] == "2026" and "scholarship" in fields["topics"]


def test_campus_rule_requires_a_single_mention():
    assert md.detect_campus("Seoul campus and ERICA students") is None


# ------------------------------------------------------------------ embeddings


def test_vector_validation_rejects_wrong_dimension_and_count():
    with pytest.raises(ValueError, match="dimension"):
        validate_vectors(np.zeros((2, 10), dtype=np.float32), 2, 384)
    with pytest.raises(ValueError, match="shape"):
        validate_vectors(np.zeros((1, 384), dtype=np.float32), 2, 384)
    with pytest.raises(ValueError, match="non-finite"):
        validate_vectors(np.full((1, 384), np.nan, dtype=np.float32), 1, 384)


# ------------------------------------------------------------------ end-to-end ingestion


def test_ingestion_links_mongo_and_qdrant(ingested, repos):
    mongo, qdrant = repos
    assert ingested.doc_count == 5 and ingested.activated
    revision = mongo.active_revision()
    assert revision.revision_id == ingested.revision_id
    assert qdrant.active_collection() == ingested.collection
    assert qdrant.count(ingested.collection) == ingested.chunk_count == len(mongo.chunks_for_revision(revision.revision_id))
    assert ingested.verification["ok"], ingested.verification
    points = set(qdrant.all_point_ids(ingested.collection))
    assert points == {c.chunk_id for c in mongo.chunks_for_revision(revision.revision_id)}


def test_reingesting_same_corpus_reuses_revision(ingestion, ingested, corpus, offline_config, embedder):
    calls = embedder.calls
    again = ingestion.run(corpus, offline_config)
    assert again.status == "reused" and again.revision_id == ingested.revision_id
    assert embedder.calls - calls <= 5  # only the verification probe embeds


def test_changed_document_creates_new_revision_and_reuses_unchanged_vectors(ingestion, ingested, corpus, offline_config, repos):
    mongo, qdrant = repos
    path = corpus / "student_services.txt"
    path.write_text(path.read_text() + "\nLibrary. The library is open until midnight during exams in this sample.\n")
    report = ingestion.run(corpus, offline_config)
    assert report.status == "completed" and report.revision_id != ingested.revision_id
    assert report.vectors_reused > 0 and report.vectors_computed > 0
    assert qdrant.active_collection() == report.collection
    old = mongo.get_revision(ingested.revision_id)
    assert old.status == "superseded"
    # the old version's document text is still stored, so the old revision stays verifiable
    assert mongo.get_documents(old.doc_versions).keys() == old.doc_versions.keys()


def test_failed_verification_keeps_previous_alias(ingestion, ingested, corpus, offline_config, repos, monkeypatch):
    mongo, qdrant = repos
    (corpus / "new.md").write_text("# New\n\nA new synthetic document.")
    monkeypatch.setattr("app.ingestion.pipeline.verify_revision", lambda *a, **k: {"ok": False, "errors": ["forced"], "warnings": [], "checks": {}})
    report = ingestion.run(corpus, offline_config)
    assert report.status == "failed" and "forced" in report.error
    assert qdrant.active_collection() == ingested.collection
    assert mongo.active_revision().revision_id == ingested.revision_id
    assert not qdrant.collection_exists(report.collection)
    assert mongo.get_revision(report.revision_id).status == "failed"


def test_bad_file_is_reported_not_silently_skipped(ingestion, corpus, offline_config):
    (corpus / "broken.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    report = ingestion.run(corpus, offline_config)
    broken = next(d for d in report.documents if d.source_uri.endswith("broken.pdf"))
    assert broken.status == "failed" and broken.error
    assert report.status == "completed" and report.doc_count == 5


@pytest.mark.integration
def test_real_bge_embedding_contract():
    from huggingface_hub import try_to_load_from_cache

    rev = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    if not try_to_load_from_cache("BAAI/bge-small-en-v1.5", "config.json", revision=rev):
        pytest.skip("BGE model not cached")
    from app.rag.registry import BGE_QUERY_INSTRUCTION
    from app.services.embeddings import load_embedder

    e = load_embedder("BAAI/bge-small-en-v1.5", rev, True, BGE_QUERY_INSTRUCTION)
    assert e.contract.dimension == 384
    vecs = e.embed_documents(["Course registration opens in February.", "Dormitory application"])
    assert len(vecs) == 2 and all(abs(np.linalg.norm(v) - 1) < 1e-4 for v in vecs)
    q = e.embed_query("When does course registration open?")
    assert np.dot(q, vecs[0]) > np.dot(q, vecs[1])
