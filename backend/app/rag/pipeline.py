"""The pipeline runners: `run_ingestion()` (offline) and `run_rag()` (one question).

The runners only decide the ORDER of the blocks and pass data from one to the next. They never
contain an algorithm: every block is created from the registry and called through the abstract
method in its folder's base.py (e.g. `retriever.retrieve(query, prefilter)`), so any registered
method can be used.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.rag.registry import PIPELINE, STAGES, create_block, get_method
from app.rag.schemas import (INSUFFICIENT_ANSWER, INSUFFICIENT_MARKER, Evidence, FilterCriteria, FinalAnswer, GenerationResult,
                             PostfilterResult, PromptContext, QueryAnalysis, RetrievalResult, RewrittenQuery, Services,
                             SourceReference, make_chunk_id, make_doc_id)  # fmt: skip
from app.tracing import Tracer, to_jsonable


def _with_embedder(config: dict, services: Services) -> Services:
    """Create the configured embedder once; other blocks reach it as self.services.embedder."""
    choice = config["embedding"]
    return replace(services, embedder=create_block("embedding", choice["method"], choice["params"], services))


# =========================================================================== offline: ingestion and indexing


def run_ingestion(folder: Path, config: dict, services: Services) -> dict:
    """Document Loading → Parsing → Chunking → Metadata Extraction → Embedding → Vector Indexing.

    Replaces the whole index. Nothing is written until every file has been processed, so a crash
    never leaves half an index.
    """
    services = _with_embedder(config, services)
    block = {s: create_block(s, config[s]["method"], config[s]["params"], services)
             for s in ("document_loading", "parsing", "chunking", "metadata_extraction", "vector_indexing")}  # fmt: skip
    files, skipped = block["document_loading"].load(folder)
    documents, chunks, errors = [], [], []
    for path in files:
        try:
            parsed = block["parsing"].parse(path)
            doc_chunks = block["chunking"].chunk(parsed)
            metadata = block["metadata_extraction"].extract(parsed)
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


# =========================================================================== online: source attribution and abstention


def attach_sources(generated: GenerationResult | None, prompt: PromptContext | None) -> FinalAnswer:
    """Turn the generated text into the final answer with source references.

    - No answer was generated (no evidence, or evidence sufficiency said no) → abstention.
    - The model replied INSUFFICIENT_CONTEXT → abstention.
    - Otherwise every evidence block in the prompt becomes a SourceReference; `cited` is True when
      the answer contains its [E#] label. Labels that match no evidence block are removed.

    This is source ATTRIBUTION (where the text came from). It does not check whether a sentence is
    actually supported by its source.
    """
    if generated is None or prompt is None:
        return FinalAnswer(answer=INSUFFICIENT_ANSWER, outcome="insufficient_context")
    answer = generated.answer
    if answer.upper().startswith(INSUFFICIENT_MARKER):
        note = answer[len(INSUFFICIENT_MARKER):].strip(" :\n")
        return FinalAnswer(answer=INSUFFICIENT_ANSWER + (f"\n\n_Model note: {note}_" if note else ""), outcome="insufficient_context")
    labels = {e.label for e in prompt.evidence}
    used = set(re.findall(r"\[(E\d+)\]", answer))
    for unknown in used - labels:  # a label the model made up: never show a source that does not exist
        answer = answer.replace(f"[{unknown}]", "")
    sources = [
        SourceReference(label=e.label, cited=e.label in used, chunk_id=e.chunk_id, doc_id=e.doc_id, title=e.title,
                        source_uri=e.source_uri, section=e.section, page_number=e.page_number, score=e.score, excerpt=e.text[:500])
        for e in prompt.evidence
    ]  # fmt: skip
    return FinalAnswer(answer=answer, outcome="answered", sources=sources)


def summarize(result: Any) -> str:
    """One readable line for the stage list in the Execution tab."""
    if isinstance(result, RetrievalResult):
        best = f", best score {result.candidates[0].score}" if result.candidates else ""
        where = " (prefiltered)" if result.applied_filter else ""
        return f"{len(result.candidates)} candidates{best}{where}"
    if isinstance(result, PostfilterResult):
        return f"{len(result.kept)} kept, {len(result.removed)} removed"
    if isinstance(result, PromptContext):
        return f"{len(result.evidence)} evidence blocks, {result.token_count} tokens"
    if isinstance(result, GenerationResult):
        return f"{result.model}: {len(result.answer)} characters"
    if isinstance(result, list) and all(isinstance(e, Evidence) for e in result):
        return f"{len(result)} evidence chunks ({sum(e.token_count for e in result)} tokens)"
    return str(result)[:120]


# =========================================================================== online: question answering


async def run_rag(question: str, config: dict, services: Services, emit: Callable[[dict], None] = lambda event: None) -> dict:
    """Answer one question with the validated `config`. Returns the full trace (also saved to MongoDB)."""
    request_id = uuid.uuid4().hex
    tracer = Tracer(request_id, emit)
    trace: dict[str, Any] = {"request_id": request_id, "question": question, "created_at": datetime.now(UTC).isoformat(),
                             "config": config, "status": "running", "stages": tracer.stages, "answer": "", "outcome": None,
                             "sources": [], "model": None, "error": None}  # fmt: skip
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

        # ---- before candidate retrieval
        analysis = await step("query_understanding", lambda b: b.analyze(question), {"question": question}, default=QueryAnalysis())
        criteria: FilterCriteria = analysis.criteria  # the eligibility conditions both filters enforce
        rewritten = await step("query_rewriting", lambda b: b.rewrite(question), {"question": question},
                               default=RewrittenQuery(query=question))  # fmt: skip
        query = rewritten.query
        # Prefiltering builds a predicate; it is NOT applied here but passed INTO candidate retrieval.
        prefilter = await step("metadata_prefiltering", lambda b: b.build_filter(criteria), {"criteria": criteria})

        # ---- candidate retrieval: dense, lexical, or both merged by hybrid fusion (all use the same prefilter)
        dense = await step("dense_retrieval", lambda b: b.retrieve(query, prefilter), {"query": query, "prefilter": prefilter})
        lexical = await step("lexical_retrieval", lambda b: b.retrieve(query, prefilter), {"query": query, "prefilter": prefilter})
        fused = await step("hybrid_fusion", lambda b: b.fuse(dense, lexical), {"dense": dense, "lexical": lexical})
        candidates = (fused or dense or lexical).candidates

        # ---- Postfiltering works on the candidates retrieval already returned.
        postfiltered = await step("metadata_postfiltering", lambda b: b.filter_candidates(candidates, criteria),
                                  {"candidates": candidates, "criteria": criteria})  # fmt: skip
        if postfiltered is not None:
            candidates = postfiltered.kept

        # ---- evidence
        evidence = await step("metadata_enrichment", lambda b: b.enrich(candidates), {"candidates": candidates})
        evidence = await step("reranking", lambda b: b.rerank(query, evidence), {"query": query, "evidence": evidence}, default=evidence)
        evidence = await step("evidence_selection", lambda b: b.select(evidence), {"evidence": evidence})
        decision = await step("evidence_sufficiency", lambda b: b.check(question, evidence), {"question": question, "evidence": evidence})

        # ---- grounded generation, or abstention when there is no (sufficient) evidence
        prompt = generated = None
        if not evidence or (decision is not None and not decision.sufficient):
            reason = "Skipped: no evidence, so the model is not asked to guess (abstention)." if not evidence else f"Skipped: {decision.reason}"
            for stage_id in ("context_construction", "generation"):
                tracer.skip(stage_id, STAGES[stage_id].name, reason)
        else:
            prompt = await step("context_construction", lambda b: b.build(question, evidence), {"question": question, "evidence": evidence})
            on_token = lambda text: emit({"type": "answer_delta", "request_id": request_id, "text": text})  # noqa: E731
            generated = await step("generation", lambda b: b.generate(prompt, on_token), {"messages": prompt.messages})
            trace["model"] = generated.model
        final = attach_sources(generated, prompt)
        trace.update(status="completed", answer=final.answer, outcome=final.outcome, sources=to_jsonable(final.sources))
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
