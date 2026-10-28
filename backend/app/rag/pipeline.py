"""The pipeline runners: `run_ingestion()` (offline) and `run_rag()` (one question).

The runners only decide the ORDER of the blocks and pass data from one to the next. They
never contain an algorithm: every block is created from the registry and called through
its abstract method (e.g. `retriever.retrieve(query)`), so any registered method can be used.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.rag.registry import PIPELINE, STAGES, create_block, get_method
from app.rag.schemas import (CitationResult, Evidence, FinalAnswer, GenerationResult, PromptContext, QueryAnalysis, RetrievalResult,
                             Services, make_chunk_id, make_doc_id)  # fmt: skip
from app.tracing import Tracer, to_jsonable


def _with_embedder(config: dict, services: Services) -> Services:
    """Create the configured embedder once; other blocks reach it as self.services.embedder."""
    choice = config["embedding"]
    return replace(services, embedder=create_block("embedding", choice["method"], choice["params"], services))


# =========================================================================== offline


def run_ingestion(folder: Path, config: dict, services: Services) -> dict:
    """Load → parse → extract metadata → chunk → embed → index. Replaces the whole index.

    Nothing is written until every file has been processed, so a crash never leaves half an index.
    """
    services = _with_embedder(config, services)
    block = {s: create_block(s, config[s]["method"], config[s]["params"], services)
             for s in ("document_loading", "parsing", "chunking", "metadata_extraction", "vector_indexing")}  # fmt: skip
    files, skipped = block["document_loading"].load(folder)
    documents, chunks, errors = [], [], []
    for path in files:
        try:
            parsed = block["parsing"].parse(path)
            metadata = block["metadata_extraction"].extract(parsed)
            doc_chunks = block["chunking"].chunk(parsed)
        except Exception as exc:  # report the bad file and continue with the others
            errors.append(f"{path.name}: {exc}")
            continue
        doc_id = make_doc_id(parsed.source_uri)
        documents.append({
            "doc_id": doc_id, "title": metadata.title, "source_uri": parsed.source_uri, "language": metadata.language,
            "source_hash": hashlib.sha256(path.read_bytes()).hexdigest(), "file_type": parsed.file_type,
            "metadata": metadata.extra, "chunk_count": len(doc_chunks), "created_at": datetime.now(UTC),
            # how this document was indexed (shown in the UI, compared with the current settings)
            "chunking": {"method": config["chunking"]["method"], **config["chunking"]["params"]},
            "embedding_method": config["embedding"]["method"],
        })  # fmt: skip
        for index, c in enumerate(doc_chunks):
            chunks.append({"chunk_id": make_chunk_id(doc_id, index, c.text), "doc_id": doc_id, "chunk_index": index, "text": c.text,
                           "section": c.section, "page_number": c.page_number, "token_count": c.token_count})  # fmt: skip
    if not chunks:
        raise ValueError(f"No documents could be ingested from {folder}. " + "; ".join(errors + skipped))
    # Embed "heading + text", so a chunk also matches words from its section title.
    vectors = services.embedder.embed_documents([f"{c['section']}\n{c['text']}" if c["section"] else c["text"] for c in chunks])
    block["vector_indexing"].index(documents, chunks, vectors, services.embedder.dimension())
    return {"documents": len(documents), "chunks": len(chunks), "dimension": services.embedder.dimension(),
            "files": [{"source_uri": d["source_uri"], "title": d["title"], "chunks": d["chunk_count"]} for d in documents],
            "errors": errors, "skipped": skipped}  # fmt: skip


# =========================================================================== online


def summarize(result: Any) -> str:
    """One readable line for the stage list in the Execution tab."""
    if isinstance(result, RetrievalResult):
        best = f", best score {result.candidates[0].score}" if result.candidates else ""
        return f"{len(result.candidates)} candidates{best}"
    if isinstance(result, PromptContext):
        return f"{len(result.evidence)} evidence blocks, {result.token_count} tokens"
    if isinstance(result, GenerationResult):
        return f"{result.model}: {len(result.answer)} characters"
    if isinstance(result, CitationResult):
        cited = sum(c.cited for c in result.citations)
        return f"{cited} citation(s) resolved" + (f", {len(result.invalid_markers)} invalid removed" if result.invalid_markers else "")
    if isinstance(result, FinalAnswer):
        return f"Outcome: {result.outcome}"
    if isinstance(result, list) and all(isinstance(e, Evidence) for e in result):
        return f"{len(result)} evidence chunks ({sum(e.token_count for e in result)} tokens)"
    return str(result)[:120]


async def run_rag(question: str, config: dict, services: Services, emit: Callable[[dict], None] = lambda event: None) -> dict:
    """Answer one question with the validated `config`. Returns the full trace (also saved to MongoDB)."""
    request_id = uuid.uuid4().hex
    tracer = Tracer(request_id, emit)
    trace: dict[str, Any] = {"request_id": request_id, "question": question, "created_at": datetime.now(UTC).isoformat(),
                             "config": config, "status": "running", "stages": tracer.stages, "answer": "", "outcome": None,
                             "citations": [], "model": None, "error": None}  # fmt: skip
    emit({"type": "started", "request_id": request_id, "config": config})
    start = time.perf_counter()

    try:
        services = _with_embedder(config, services)
        # One block object per online stage that has a selected method.
        blocks = {s.stage_id: create_block(s.stage_id, config[s.stage_id]["method"], config[s.stage_id]["params"], services)
                  for s in PIPELINE if s.phase == "online" and config[s.stage_id]["method"]}  # fmt: skip

        async def step(stage_id: str, work: Callable[[Any], Awaitable[Any]], input: Any, default: Any = None) -> Any:
            """Run one stage through its block (or record why it was skipped) and trace it."""
            stage = STAGES[stage_id]
            block = blocks.get(stage_id)
            if block is None:
                reason = "Switched off in the configuration." if any(m.implemented for m in stage.methods) else "Not implemented yet."
                tracer.skip(stage_id, stage.name, reason)
                return default
            method = get_method(stage_id, block.method_id)
            with tracer.stage(stage_id, stage.name, method.method_id, method.name, input, block.params) as record:
                result = await work(block)
                record["output"] = to_jsonable(result)
                record["summary"] = summarize(result)
            return result

        def skip_because_no_evidence(*stage_ids: str) -> None:
            for stage_id in stage_ids:
                tracer.skip(stage_id, STAGES[stage_id].name, "Skipped: no evidence, so the model is not asked to guess.")

        # ---- before retrieval
        analysis = await step("query_understanding", lambda b: b.analyze(question), {"question": question}, QueryAnalysis())
        query = await step("query_rewriting", lambda b: b.rewrite(question), {"question": question}, default=question)
        constraints = await step("constraint_validation", lambda b: b.validate(analysis), {"analysis": analysis}, default={})
        filters = await step("metadata_filtering", lambda b: b.build_filter(constraints), {"constraints": constraints})

        # ---- retrieval (dense, lexical, or both merged by fusion)
        dense = await step("dense_retrieval", lambda b: b.retrieve(query, filters), {"query": query, "filters": filters})
        lexical = await step("lexical_retrieval", lambda b: b.retrieve(query, filters), {"query": query, "filters": filters})
        fused = await step("hybrid_fusion", lambda b: b.fuse(dense.candidates, lexical.candidates),
                           {"dense": dense and dense.candidates, "lexical": lexical and lexical.candidates})  # fmt: skip
        retrieved = fused or dense or lexical

        # ---- evidence
        evidence = await step("metadata_enrichment", lambda b: b.enrich(retrieved.candidates), {"candidates": retrieved.candidates})
        evidence = await step("reranking", lambda b: b.rerank(query, evidence), {"query": query, "evidence": evidence}, default=evidence)
        evidence = await step("evidence_selection", lambda b: b.select(evidence), {"evidence": evidence})
        decision = await step("sufficiency_gate", lambda b: b.check(question, evidence), {"question": question, "evidence": evidence})

        # ---- answer
        verified: CitationResult | None = None
        if not evidence or (decision is not None and not decision.sufficient):
            skip_because_no_evidence("context_builder", "generation", "citation_verification")
        else:
            prompt = await step("context_builder", lambda b: b.build(question, evidence), {"question": question, "evidence": evidence})
            on_token = lambda text: emit({"type": "answer_delta", "request_id": request_id, "text": text})  # noqa: E731
            generated = await step("generation", lambda b: b.generate(prompt, on_token), {"messages": prompt.messages})
            trace["model"] = generated.model
            verified = await step("citation_verification", lambda b: b.verify(generated.answer, prompt.evidence),
                                  {"answer": generated.answer, "evidence_labels": [e.label for e in prompt.evidence]})  # fmt: skip
        final = await step("response_guard", lambda b: b.finalize(verified), {"citation_result": verified})

        trace.update(status="completed", answer=final.answer, outcome=final.outcome, citations=to_jsonable(final.citations))
    except Exception as exc:
        trace.update(status="failed", outcome="error", error=f"{exc.__class__.__name__}: {exc}")
    finally:
        trace["total_ms"] = round((time.perf_counter() - start) * 1000, 1)
        if trace["status"] == "running":  # the browser disconnected mid-request
            trace["status"] = "cancelled"
        try:
            services.db.save_trace(dict(trace))
        except Exception:
            pass  # a trace that cannot be saved must not hide the answer
    emit({"type": "done", "request_id": request_id, "trace": trace})
    return trace
