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

from app.rag.blocks.retrieval.hybrid_fusion.rrf import reciprocal_rank_fusion
from app.rag.registry import PIPELINE, STAGES, create_block, get_method
from app.rag.schemas import (INSUFFICIENT_ANSWER, INSUFFICIENT_MARKER, Evidence, FilterCriteria, FinalAnswer, GenerationResult,
                             ParsedDocument, PostfilterResult, PromptContext, QueryAnalysis, RetrievalFilter, RetrievalResult,
                             RewrittenQuery, Services, SourceReference, make_chunk_id, make_doc_id)  # fmt: skip
from app.tracing import Tracer, to_jsonable


def _with_embedder(config: dict, services: Services) -> Services:
    """Create the configured embedder once; other blocks reach it as self.services.embedder."""
    choice = config["embedding"]
    return replace(services, embedder=create_block("embedding", choice["method"], choice["params"], services))


# =========================================================================== offline: ingestion and indexing


def run_ingestion(folder: Path, config: dict, services: Services) -> dict:
    """Document Loading → Parsing, then index_documents() (Chunking → … → Vector Indexing).

    Replaces the whole index. Nothing is written until every file has been processed, so a crash
    never leaves half an index.
    """
    services = _with_embedder(config, services)
    loader = create_block("document_loading", config["document_loading"]["method"], config["document_loading"]["params"], services)
    parser = create_block("parsing", config["parsing"]["method"], config["parsing"]["params"], services)
    start = time.perf_counter()
    files, skipped = loader.load(folder)
    parsed, hashes, errors = [], {}, []
    for path in files:
        try:
            document = parser.parse(path)
        except Exception as exc:  # report the bad file and continue with the others
            errors.append(f"{path.name}: {exc}")
            continue
        parsed.append(document)
        hashes[document.source_uri] = hashlib.sha256(path.read_bytes()).hexdigest()
    parse_ms = (time.perf_counter() - start) * 1000
    if not parsed:
        raise ValueError(f"No documents could be ingested from {folder}. " + "; ".join(errors + skipped))
    report = index_documents(parsed, config, services, source_hashes=hashes, corpus={"source": str(folder)}, parse_ms=parse_ms)
    report["errors"] = errors + report["errors"]
    report["skipped"] = skipped
    return report


def index_documents(documents: list[ParsedDocument], config: dict, services: Services, *, source_hashes: dict[str, str] | None = None,
                    corpus: dict | None = None, parse_ms: float = 0.0) -> dict:
    """Chunking → Metadata Extraction → Embedding → Vector Indexing for already parsed documents.

    Used by run_ingestion() (files from data/) and by the benchmark runner (BEIR records), so both
    build indexes with exactly the same code. Writes a manifest describing how the index was built
    and returns a report with counts, timings and verification results.
    """
    if services.embedder is None:
        services = _with_embedder(config, services)
    block = {s: create_block(s, config[s]["method"], config[s]["params"], services)
             for s in ("chunking", "metadata_extraction", "vector_indexing")}  # fmt: skip
    timings = {"parse_ms": parse_ms, "chunk_ms": 0.0, "metadata_ms": 0.0}
    records, chunks, errors, bad_spans = [], [], [], 0
    for parsed in documents:
        try:
            start = time.perf_counter()
            doc_chunks = block["chunking"].chunk(parsed)
            middle = time.perf_counter()
            metadata = block["metadata_extraction"].extract(parsed)
            timings["chunk_ms"] += (middle - start) * 1000
            timings["metadata_ms"] += (time.perf_counter() - middle) * 1000
        except Exception as exc:  # report the bad document and continue with the others
            errors.append(f"{parsed.source_uri}: {exc}")
            continue
        doc_id = make_doc_id(parsed.source_uri)
        full_text = parsed.full_text()
        records.append({
            "doc_id": doc_id, "title": metadata.title, "source_uri": parsed.source_uri, "language": metadata.language,
            "source_hash": (source_hashes or {}).get(parsed.source_uri) or hashlib.sha256(full_text.encode()).hexdigest(),
            "file_type": parsed.file_type, "metadata": metadata.extra, "chunk_count": len(doc_chunks), "created_at": datetime.now(UTC),
            # how this document was indexed (shown in the UI, compared with the current settings)
            "chunking": {"method": config["chunking"]["method"], **config["chunking"]["params"]},
            "embedding_method": config["embedding"]["method"],
        })  # fmt: skip
        for index, c in enumerate(doc_chunks):
            bad_spans += c.start is None or full_text[c.start : c.end] != c.text
            chunks.append({"chunk_id": make_chunk_id(doc_id, index, c.text), "doc_id": doc_id, "chunk_index": index, "text": c.text,
                           "section": c.section, "page_number": c.page_number, "token_count": c.token_count,
                           "start": c.start, "end": c.end})  # fmt: skip
    if not chunks:
        raise ValueError("No chunks were produced. " + "; ".join(errors))
    # Embed "heading + text", so a chunk also matches words from its section title.
    start = time.perf_counter()
    texts = [f"{c['section']}\n{c['text']}" if c["section"] else c["text"] for c in chunks]
    vectors = services.embedder.embed_documents(texts)
    timings["embed_ms"] = (time.perf_counter() - start) * 1000
    contract = services.embedder.contract()
    limit = contract.get("max_seq_length")
    truncated = sum(services.embedder.count_tokens(t) + 2 > limit for t in texts) if limit else None  # +2: [CLS] and [SEP]
    start = time.perf_counter()
    status = block["vector_indexing"].index(records, chunks, vectors, services.embedder.dimension())
    timings["index_ms"] = (time.perf_counter() - start) * 1000
    timings = {k: round(v, 1) for k, v in timings.items()}
    timings["total_ms"] = round(sum(timings.values()), 1)
    db = services.db
    manifest = {
        "index_id": db.index_id, "collection": db.collection, "built_at": datetime.now(UTC).isoformat(), "corpus": corpus or {},
        "source_manifest_sha256": hashlib.sha256("".join(sorted(r["source_hash"] for r in records)).encode()).hexdigest(),
        "config": {s: config[s] for s in ("parsing", "chunking", "metadata_extraction", "embedding", "vector_indexing")},
        "embedding_contract": contract, "documents": len(records), "chunks": len(chunks), "vector_index": status,
        "chunk_id_sha256": hashlib.sha256("".join(c["chunk_id"] for c in chunks).encode()).hexdigest(),
        "source_spans_valid": len(chunks) - bad_spans, "source_spans_invalid": bad_spans, "truncated_by_embedder": truncated,
        "timings": timings, "embedding_texts_per_s": round(len(texts) / (timings["embed_ms"] / 1000), 1) if timings["embed_ms"] else None,
    }  # fmt: skip
    db.save_manifest(manifest)
    return {"documents": len(records), "chunks": len(chunks), "dimension": services.embedder.dimension(),
            "files": [{"source_uri": d["source_uri"], "title": d["title"], "chunks": d["chunk_count"]} for d in records],
            "errors": errors, "skipped": [], "manifest": manifest}  # fmt: skip


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


async def answer_from_evidence(question: str, evidence: list[Evidence], config: dict, services: Services) -> dict[str, Any]:
    """Context Construction → Generation → source attribution, for evidence that was ALREADY selected.

    The benchmark uses this so that two backbone LLMs answer from exactly the same evidence (retrieved
    once by run_rag). Same blocks and the same attach_sources() as run_rag; nothing is streamed or saved.
    """
    if not evidence:
        return {"prompt": None, "generated": None, "final": attach_sources(None, None), "context_ms": 0.0, "generation_ms": 0.0}
    services = _with_embedder(config, services)
    builder = create_block("context_construction", config["context_construction"]["method"], config["context_construction"]["params"], services)
    generator = create_block("generation", config["generation"]["method"], config["generation"]["params"], services)
    start = time.perf_counter()
    prompt = await builder.build(question, evidence)
    middle = time.perf_counter()
    generated = await generator.generate(prompt, lambda text: None)
    end = time.perf_counter()
    return {"prompt": prompt, "generated": generated, "final": attach_sources(generated, prompt),
            "context_ms": round((middle - start) * 1000, 1), "generation_ms": round((end - middle) * 1000, 1)}  # fmt: skip


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


async def _retrieve(block: Any, queries: list[str], prefilter: RetrievalFilter | None, rrf_k: int,
                    embedding_text: str | None = None) -> RetrievalResult:
    """Run one retriever for every query. With several queries (multi-query rewriting) the rankings are
    merged with Reciprocal Rank Fusion; HyDE's passage (embedding_text) replaces the query vector."""
    if embedding_text is not None:
        return await block.retrieve(queries[0], prefilter, embedding_text=embedding_text)
    if len(queries) == 1:
        return await block.retrieve(queries[0], prefilter)
    results = [await block.retrieve(q, prefilter) for q in queries]
    merged = reciprocal_rank_fusion({f"query_{i + 1}": r.candidates for i, r in enumerate(results)}, rrf_k, block.params["top_k"])
    details = {"queries": queries, "merged_with": f"RRF (k={rrf_k})", "per_query": [r.details for r in results]}
    return RetrievalResult(candidates=merged, applied_filter=prefilter, details=details)


async def run_rag(question: str, config: dict, services: Services, emit: Callable[[dict], None] = lambda event: None, *,
                  stop_after: str | None = None, save_trace: bool = True) -> dict:
    """Answer one question with the validated `config`. Returns the full trace (also saved to MongoDB).

    stop_after: a stage id; later stages are skipped (the benchmark runner uses "evidence_sufficiency"
                for retrieval-only runs, so no LLM answer is generated).
    save_trace: False = do not store the trace in MongoDB (the benchmark keeps its own results).
    """
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

        stopped: list[str] = []  # becomes non-empty once `stop_after` has run

        async def step(stage_id: str, work: Callable[[Any], Awaitable[Any]], input: Any, default: Any = None) -> Any:
            """Run one stage through its block (or record why it was skipped) and trace it."""
            stage = STAGES[stage_id]
            block = blocks.get(stage_id)
            if stopped:
                tracer.skip(stage_id, stage.name, f"Not run: this run stops after {STAGES[stop_after].name}.")
                return default
            if stage_id == stop_after:
                stopped.append(stage_id)  # this stage still runs (if it is on); the following ones do not
            if block is None:
                reason = "Switched off in the configuration." if any(m.implemented for m in stage.methods) else "Not implemented yet."
                tracer.skip(stage_id, stage.name, reason)
                return default
            method = get_method(stage_id, block.method_id)
            with tracer.stage(stage_id, stage.name, method.method_id, method.name, input, block.params) as record:
                block.trace_details = {}
                result = await work(block)
                record["output"] = to_jsonable(result)
                record["summary"] = summarize(result)
                if block.trace_details:
                    record["details"] = to_jsonable(block.trace_details)
            return result

        # ---- before candidate retrieval
        analysis = await step("query_understanding", lambda b: b.analyze(question), {"question": question}, default=QueryAnalysis())
        criteria: FilterCriteria = analysis.criteria  # the eligibility conditions both filters enforce
        rewritten = await step("query_rewriting", lambda b: b.rewrite(question), {"question": question},
                               default=RewrittenQuery(query=question))  # fmt: skip
        query = rewritten.query
        queries = [query] + rewritten.alternatives  # several queries = multi-query expansion
        rrf_k = blocks["query_rewriting"].params.get("rrf_k", 60) if "query_rewriting" in blocks else 60
        # Prefiltering builds a predicate; it is NOT applied here but passed INTO candidate retrieval.
        prefilter = await step("metadata_prefiltering", lambda b: b.build_filter(criteria), {"criteria": criteria})

        # ---- candidate retrieval: dense, lexical, or both merged by hybrid fusion (all use the same prefilter)
        hyde = rewritten.embedding_text
        dense = await step("dense_retrieval", lambda b: _retrieve(b, queries, prefilter, rrf_k, hyde),
                           {"queries": queries, "prefilter": prefilter, "embedding_text": hyde})  # fmt: skip
        lexical = await step("lexical_retrieval", lambda b: _retrieve(b, queries, prefilter, rrf_k), {"queries": queries, "prefilter": prefilter})
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
        if stopped:  # a retrieval-only run (benchmark): no context, no LLM answer
            for stage_id in ("context_construction", "generation"):
                tracer.skip(stage_id, STAGES[stage_id].name, f"Not run: this run stops after {STAGES[stop_after].name}.")
            trace.update(status="completed", outcome="stopped", decision=to_jsonable(decision))
        else:
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
            trace.update(status="completed", answer=final.answer, outcome=final.outcome, sources=to_jsonable(final.sources),
                         decision=to_jsonable(decision), usage=generated.usage if generated else None)
    except Exception as exc:
        trace.update(status="failed", outcome="error", error=f"{exc.__class__.__name__}: {exc}")
    finally:
        trace["total_ms"] = round((time.perf_counter() - start) * 1000, 1)
        if trace["status"] == "running":  # the browser disconnected mid-request
            trace["status"] = "cancelled"
        if save_trace:
            try:
                services.db.save_trace(dict(trace))
            except Exception:
                pass  # a trace that cannot be saved must not hide the answer
    emit({"type": "done", "request_id": request_id, "trace": trace})
    return trace
