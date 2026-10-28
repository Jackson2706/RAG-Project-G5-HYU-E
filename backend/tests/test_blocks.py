"""Tests for the abstract classes and the working block implementations."""

from pathlib import Path

import pytest

from app.rag.blocks.base import PipelineBlock
from app.rag.blocks.chunking import BaseChunker, SectionTokenChunker
from app.rag.blocks.embedding import SentenceTransformerEmbedder
from app.rag.blocks.embedding import load_sentence_transformer as real_model_loader  # saved before the fake replaces it
from app.rag.blocks.loading import LocalFolderLoader
from app.rag.blocks.parsing import BasicDocumentParser
from app.rag.blocks.reranking import BaseReranker, CrossEncoderReranker
from app.rag.blocks.retrieval import BaseDenseRetriever
from app.rag.registry import PIPELINE
from app.rag.schemas import ParsedDocument, RetrievalResult, Section, make_chunk_id, make_doc_id
from tests.conftest import SAMPLES

pytestmark = pytest.mark.anyio


def make_pdf(pages: list[str]) -> bytes:
    """Build a tiny valid PDF with one line of text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        n = len(objects) + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {n + 1} 0 R /Resources << /Font << /F1 FONT 0 R >> >> >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        kids.append(f"{n} 0 R")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body.replace('FONT', str(len(objects)))}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


# ------------------------------------------------------------------ abstract classes


def test_abstract_classes_cannot_be_instantiated(services):
    for stage in PIPELINE:
        with pytest.raises(TypeError, match="abstract"):
            stage.base_class({}, services)


def test_subclass_missing_the_abstract_method_fails(services):
    class ForgotToImplement(BaseReranker):
        pass

    with pytest.raises(TypeError, match="rerank"):
        ForgotToImplement({}, services)


async def test_a_correct_subclass_works(services):
    class EmptyRetriever(BaseDenseRetriever):
        async def retrieve(self, query, filters=None):
            return RetrievalResult(candidates=[])

    retriever = EmptyRetriever({"top_k": 3}, services)
    assert isinstance(retriever, PipelineBlock) and retriever.params == {"top_k": 3}
    assert (await retriever.retrieve("hello")).candidates == []


async def test_skeletons_refuse_to_run(services):
    with pytest.raises(NotImplementedError):
        await CrossEncoderReranker({}, services).rerank("q", [])


# ------------------------------------------------------------------ loading & parsing


def test_loader_reports_unsupported_files(tmp_path: Path, services):
    (tmp_path / "photo.png").write_bytes(b"png")
    (tmp_path / "notes.md").write_text("# Notes\n\nSome text.")
    files, skipped = LocalFolderLoader({}, services).load(tmp_path)
    assert [f.name for f in files] == ["notes.md"] and "photo.png" in skipped[0]


def test_markdown_sections_and_front_matter(services):
    doc = BasicDocumentParser({}, services).parse(SAMPLES / "orientation_guide.md")
    assert doc.title == "New Student Orientation Guide (Sample)" and doc.file_type == "md"
    assert doc.declared_metadata["campus"] == "SEOUL"  # front matter becomes declared metadata
    assert "Schedule" in [s.heading for s in doc.sections]
    assert "title:" not in doc.sections[0].text


def test_html_txt_and_pdf(tmp_path: Path, services):
    parser = BasicDocumentParser({}, services)
    html = parser.parse(SAMPLES / "scholarships.html")
    assert "Need-based | Household income certificate" in next(s.text for s in html.sections if s.heading == "Required Documents")
    assert parser.parse(SAMPLES / "student_services.txt").title == "Student Services Overview (Sample)"
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(make_pdf(["Orientation starts on Monday.", "Scholarships close in February."]))
    assert [s.page for s in parser.parse(pdf).sections] == [1, 2]


def test_empty_file_is_an_error(tmp_path: Path, services):
    (tmp_path / "empty.md").write_text("   ")
    with pytest.raises(ValueError, match="no text"):
        BasicDocumentParser({}, services).parse(tmp_path / "empty.md")


# ------------------------------------------------------------------ chunking & embedding


def _chunker(services, size, overlap) -> BaseChunker:
    services.embedder = SentenceTransformerEmbedder({}, services)
    return SectionTokenChunker({"chunk_size": size, "chunk_overlap": overlap}, services)


def test_short_sections_stay_whole(services):
    doc = ParsedDocument(Path("x.md"), "x.md", "md", "X", [Section("A", "Short text."), Section("B", "Another one.")])
    assert [c.text for c in _chunker(services, 64, 8).chunk(doc)] == ["Short text.", "Another one."]


def test_long_section_is_windowed_with_overlap(services):
    text = " ".join(f"w{i}" for i in range(100))  # 100 tokens with the fake tokenizer
    doc = ParsedDocument(Path("x.md"), "x.md", "md", "X", [Section("Long", text, page=3)])
    chunks = _chunker(services, 40, 10).chunk(doc)
    words = [c.text.split() for c in chunks]
    assert [len(w) for w in words] == [40, 40, 40]  # windows start at tokens 0, 30, 60
    assert words[0][-10:] == words[1][:10] and words[-1][-1] == "w99"
    assert all(c.section == "Long" and c.page_number == 3 and c.token_count == 40 for c in chunks)


def test_embedder_shapes(services, fake_model):
    embedder = SentenceTransformerEmbedder({}, services)
    vectors = embedder.embed_documents(["one text", "two texts"])
    assert len(vectors) == 2 and all(len(v) == fake_model.dim == embedder.dimension() for v in vectors)
    assert len(embedder.embed_query("a question")) == fake_model.dim


def test_ids_are_stable():
    assert make_doc_id("raw/a.md") == make_doc_id("raw/a.md") != make_doc_id("raw/b.md")
    assert make_chunk_id("d", 0, "t") == make_chunk_id("d", 0, "t") != make_chunk_id("d", 1, "t")


@pytest.mark.integration
def test_real_bge_model_has_384_dimensions(services, monkeypatch):
    from huggingface_hub import try_to_load_from_cache

    s = services.settings
    if not try_to_load_from_cache(s.embedding_model, "config.json", revision=s.embedding_revision):
        pytest.skip("BGE model is not downloaded yet")
    monkeypatch.setattr("app.rag.blocks.embedding.load_sentence_transformer", real_model_loader)
    embedder = SentenceTransformerEmbedder({}, services)
    assert embedder.dimension() == 384 and len(embedder.embed_query("How do I register?")) == 384
