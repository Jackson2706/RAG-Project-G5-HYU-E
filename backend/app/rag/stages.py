"""Online pipeline stages.

Every stage implements ``PipelineStage.execute(ctx, call) -> StageResult``:
it reads/writes typed fields of the shared ``PipelineContext`` and returns the
*actual* input/output it worked on, which the orchestrator records in the
trace. A stage that intentionally does nothing returns ``status="bypassed"``
with a reason instead of pretending to run.
"""

from __future__ import annotations

import asyncio
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from app.ingestion.metadata import AUDIENCES, CAMPUSES, detect_academic_year
from app.models.config import ResolvedConfig
from app.models.pipeline import AnswerResult, Candidate, MetadataFilterSpec, PipelineContext, SufficiencyDecision
from app.rag import generation as gen
from app.rag.retrieval import bm25_tokens, build_qdrant_filter, describe_filter, fuse
from app.services.ollama import model_options
from app.services.tracing import vector_preview

if TYPE_CHECKING:  # avoids an import cycle with app.rag.pipeline
    from app.rag.pipeline import RAGServices


class PipelineValidationError(Exception):
    """Request rejected before retrieval (e.g. conflicting or unknown constraints)."""


@dataclass
class StageCall:
    method: str
    params: dict[str, Any]
    config: ResolvedConfig
    emit_delta: Callable[[str], Awaitable[None]]


@dataclass
class StageResult:
    summary: str
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    status: Literal["completed", "bypassed"] = "completed"
    bypass_reason: str | None = None


def bypass(reason: str, summary: str | None = None, **output: Any) -> StageResult:
    return StageResult(summary=summary or reason, status="bypassed", bypass_reason=reason, output=output)


def candidate_view(c: Candidate, text_chars: int = 300) -> dict[str, Any]:
    """Compact candidate representation for traces."""
    view: dict[str, Any] = {"chunk_id": c.chunk_id, "doc_id": c.doc_id}
    for name in ("dense_rank", "dense_score", "lexical_rank", "lexical_score", "fused_rank", "fused_score"):
        value = getattr(c, name)
        if value is not None:
            view[name] = round(value, 5) if isinstance(value, float) else value
    if c.title:
        view["title"] = c.title
    if c.section_path:
        view["section"] = " › ".join(c.section_path)
    if c.page_number:
        view["page"] = c.page_number
    if c.text is not None:
        view["text"] = c.text if len(c.text) <= text_chars else c.text[:text_chars] + "…"
    return view


class PipelineStage(ABC):
    stage_id: ClassVar[str]

    def __init__(self, services: RAGServices) -> None:
        self.services = services

    @abstractmethod
    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult: ...


class PlannedStage(PipelineStage):
    """Stage whose methods are all planned. Validation never lets it run enabled."""

    def __init__(self, services: RAGServices, stage_id: str) -> None:
        super().__init__(services)
        self.stage_id = stage_id  # type: ignore[misc]

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        raise NotImplementedError(f"{self.stage_id}: method '{call.method}' is not implemented")


# --------------------------------------------------------------------------- query side

AUDIENCE_RULES = {
    "international": re.compile(r"\b(international|foreign)\s+students?\b", re.I),
    "exchange": re.compile(r"\bexchange\s+students?\b", re.I),
    "graduate": re.compile(r"\b(graduate\s+(students?|school)|master'?s|ph\.?d)\b", re.I),
    "undergraduate": re.compile(r"\bundergrad(uate)?s?\b", re.I),
    "freshman": re.compile(r"\b(freshm[ae]n|first[- ]year|new\s+students?|incoming\s+students?)\b", re.I),
}
CAMPUS_QUERY_RULES = {"SEOUL": re.compile(r"\bseoul\s+campus\b", re.I), "ERICA": re.compile(r"\berica\b", re.I)}


class QueryUnderstandingStage(PipelineStage):
    stage_id = "query_understanding"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        inp = {"question": ctx.question}
        if call.method == "passthrough":
            return StageResult(summary="Pass-through: no constraints extracted", input=inp, status="bypassed",
                               bypass_reason="Pass-through method: the question is forwarded unchanged.",
                               output={"language": "en", "detected_constraints": {}})  # fmt: skip
        p, detected, rules = call.params, {}, []
        if p["detect_campus"]:
            campuses = [c for c, rx in CAMPUS_QUERY_RULES.items() if rx.search(ctx.question)]
            if len(campuses) == 1:
                detected["campus"] = campuses[0]
                rules.append(f"campus:{campuses[0]}")
        if p["detect_audience"]:
            audiences = [a for a, rx in AUDIENCE_RULES.items() if rx.search(ctx.question)]
            if audiences:
                detected["audience"] = audiences
                rules += [f"audience:{a}" for a in audiences]
        if p["detect_academic_year"]:
            year = detect_academic_year(ctx.question)
            if year:
                detected["academic_year"] = year
                rules.append(f"academic_year:{year}")
        ctx.understanding.detected_constraints = detected
        ctx.understanding.matched_rules = rules
        summary = f"Detected {', '.join(rules)}" if rules else "No constraints detected"
        return StageResult(summary=summary, input=inp, output=ctx.understanding.model_dump())


class ConstraintValidationStage(PipelineStage):
    stage_id = "constraint_validation"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        mf = call.config.stage("metadata_filtering")
        detected = ctx.understanding.detected_constraints
        if not mf.enabled:
            return bypass("Metadata filtering is disabled, so no constraints are applied.", detected_constraints=detected)
        f = mf.params
        configured = {"campus": None if f["campus"] == "any" else f["campus"], "audience": f["audience"],
                      "document_type": None if f["document_type"] == "any" else f["document_type"],
                      "academic_year": f["academic_year"].strip() or None}  # fmt: skip
        inp = {"configured": configured, "detected": detected, "use_detected_constraints": f["use_detected_constraints"]}
        resolved = dict(configured)
        notes: list[str] = []
        if call.method == "deterministic" and f["use_detected_constraints"]:
            for key, value in detected.items():
                if not resolved.get(key):
                    resolved[key] = value
                    notes.append(f"{key}={value} taken from the question")
                elif resolved[key] != value:
                    msg = f"question mentions {key}={value} but the configured filter is {key}={resolved[key]}"
                    if call.params["conflict_policy"] == "reject":
                        raise PipelineValidationError(f"Constraint conflict: {msg}")
                    notes.append(f"conflict: {msg}; configured value kept")
        if resolved["campus"] and resolved["campus"] not in CAMPUSES:
            raise PipelineValidationError(f"Unknown campus '{resolved['campus']}'")
        unknown = [a for a in resolved["audience"] if a not in AUDIENCES]
        if unknown:
            raise PipelineValidationError(f"Unknown audience value(s): {unknown}")
        if resolved["academic_year"] and not re.fullmatch(r"20\d{2}(-20\d{2})?", resolved["academic_year"]):
            raise PipelineValidationError(f"Academic year '{resolved['academic_year']}' must look like 2025 or 2025-2026")
        ctx.filter_spec = MetadataFilterSpec(**resolved, include_unknown=f["include_unknown"], include_university_wide=f["include_university_wide"])
        active = {k: v for k, v in resolved.items() if v}
        return StageResult(summary=f"Validated constraints: {active or 'none'}", input=inp,
                           output={"filter_spec": ctx.filter_spec.model_dump(), "notes": notes})  # fmt: skip


class MetadataFilteringStage(PipelineStage):
    stage_id = "metadata_filtering"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        spec = ctx.filter_spec
        inp = {"filter_spec": spec.model_dump() if spec else None}
        if spec is None or spec.is_empty():
            return StageResult(summary="No constraints: retrieval is unfiltered", input=inp, status="bypassed",
                               bypass_reason="No validated constraints to filter on.", output={"qdrant_filter": None})  # fmt: skip
        compiled = describe_filter(build_qdrant_filter(spec))
        return StageResult(summary="Compiled Qdrant payload filter", input=inp, output={"qdrant_filter": compiled})


class DenseRetrievalStage(PipelineStage):
    stage_id = "dense_retrieval"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        revision = await self.services.require_active_revision()
        embedder = await asyncio.to_thread(self.services.embedder_for, revision)
        p = call.params
        t0 = time.perf_counter()
        vector = await asyncio.to_thread(embedder.embed_query, ctx.query)
        embed_ms = (time.perf_counter() - t0) * 1000
        qfilter = build_qdrant_filter(ctx.filter_spec)
        t1 = time.perf_counter()
        points = await asyncio.to_thread(self.services.qdrant.search, vector, p["top_k"], qfilter, p["exact"], p["hnsw_ef"], p["score_threshold"])
        search_ms = (time.perf_counter() - t1) * 1000
        ctx.dense_candidates = [
            Candidate(chunk_id=str(pt.id), doc_id=pt.payload.get("doc_id", ""), version_id=pt.payload.get("version_id"),
                      dense_score=float(pt.score), dense_rank=i + 1, payload=pt.payload or {})
            for i, pt in enumerate(points)
        ]  # fmt: skip
        contract = embedder.contract
        exact = p["exact"] or self.services.qdrant.local_mode
        return StageResult(
            summary=f"{len(points)} candidates from Qdrant ({'exact' if exact else 'HNSW'} {contract.distance})",
            input={"query": ctx.query, "query_instruction": contract.query_instruction, "top_k": p["top_k"],
                   "filter": describe_filter(qfilter), "collection": revision.collection_name},
            output={"embedding": {"model": contract.model_id, **vector_preview(vector)}, "search_mode": "exact" if exact else "hnsw",
                    "timings_ms": {"embed": round(embed_ms, 1), "search": round(search_ms, 1)},
                    "candidates": [candidate_view(c) | {"payload": c.payload} for c in ctx.dense_candidates]},
        )  # fmt: skip


class LexicalRetrievalStage(PipelineStage):
    stage_id = "lexical_retrieval"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        revision = await self.services.require_active_revision()
        p = call.params
        index = await self.services.bm25_for(revision, p["remove_stopwords"])
        hits, terms = await asyncio.to_thread(index.search, ctx.query, p["top_k"], p["k1"], p["b"], ctx.filter_spec)
        ctx.lexical_candidates = [
            Candidate(chunk_id=c.chunk_id, doc_id=c.doc_id, version_id=c.version_id, lexical_score=score, lexical_rank=i + 1,
                      text=c.text, title=c.metadata.get("title"), section_path=c.section_path)
            for i, (c, score) in enumerate(hits)
        ]  # fmt: skip
        return StageResult(
            summary=f"{len(hits)} BM25 candidates for {len(terms)} query terms",
            input={"query": ctx.query, "query_terms": terms, "top_k": p["top_k"], "k1": p["k1"], "b": p["b"],
                   "filter": ctx.filter_spec.model_dump() if ctx.filter_spec else None},
            output={"indexed_chunks": len(index.chunks), "avg_chunk_terms": round(index.avgdl, 1),
                    "candidates": [candidate_view(c) for c in ctx.lexical_candidates]},
        )  # fmt: skip


class HybridFusionStage(PipelineStage):
    stage_id = "hybrid_fusion"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        inp = {"dense": len(ctx.dense_candidates), "lexical": len(ctx.lexical_candidates), "params": call.params}
        ctx.candidates = fuse(ctx.dense_candidates, ctx.lexical_candidates, call.method, call.params)
        if call.method == "none":
            source = "dense" if ctx.dense_candidates else "lexical"
            return StageResult(summary=f"Single retriever: {len(ctx.candidates)} {source} candidates forwarded", input=inp,
                               status="bypassed", bypass_reason="Only one retriever is enabled; its ranking is kept unchanged.",
                               output={"candidates": [candidate_view(c) for c in ctx.candidates]})  # fmt: skip
        both = sum(1 for c in ctx.candidates if c.dense_rank and c.lexical_rank)
        return StageResult(summary=f"{call.method.upper()} fused {len(ctx.candidates)} candidates ({both} found by both)", input=inp,
                           output={"candidates": [candidate_view(c) for c in ctx.candidates]})  # fmt: skip


class MetadataEnrichmentStage(PipelineStage):
    stage_id = "metadata_enrichment"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        ids = [c.chunk_id for c in ctx.candidates]
        mongo = self.services.mongo
        chunks = await asyncio.to_thread(mongo.get_chunks, ids)
        versions = {c.doc_id: c.version_id for c in chunks.values()}
        docs = await asyncio.to_thread(mongo.get_documents, versions, False)
        fields = call.params["include_fields"]
        enriched, missing = [], []
        for c in ctx.candidates:
            chunk = chunks.get(c.chunk_id)
            doc = docs.get(c.doc_id)
            if chunk is None or doc is None:
                missing.append(c.chunk_id)
                continue
            meta = {f: getattr(doc, f) for f in fields if hasattr(doc, f)}
            if "keywords" in fields:
                meta["keywords"] = chunk.keywords
            enriched.append(c.model_copy(update={
                "version_id": chunk.version_id, "text": chunk.text, "token_count": chunk.token_count, "title": doc.title,
                "source_uri": doc.source_uri, "section_path": chunk.section_path, "page_number": chunk.page_number,
                "page_end": chunk.page_end, "source_span": chunk.source_span, "metadata": meta}))  # fmt: skip
        ctx.candidates = enriched
        summary = f"Enriched {len(enriched)} candidates from MongoDB" + (f"; {len(missing)} missing chunks dropped" if missing else "")
        return StageResult(summary=summary, input={"chunk_ids": ids, "include_fields": fields},
                           output={"missing_chunk_ids": missing, "candidates": [candidate_view(c, 1200) | {"metadata": c.metadata, "source_uri": c.source_uri}
                                                                                 for c in enriched]})  # fmt: skip


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


class EvidenceSelectionStage(PipelineStage):
    stage_id = "evidence_selection"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        p = call.params
        selected: list[Candidate] = []
        token_sets: list[set[str]] = []
        rejected: list[dict[str, Any]] = []
        tokens_used = 0
        for c in ctx.candidates:
            if len(selected) >= p["max_chunks"]:
                rejected.append({"chunk_id": c.chunk_id, "reason": "max_chunks reached"})
                continue
            terms = set(bm25_tokens(c.text or "", True))
            if p["deduplicate"]:
                sim = max((_jaccard(terms, s) for s in token_sets), default=0.0)
                if sim >= p["dedup_similarity"]:
                    rejected.append({"chunk_id": c.chunk_id, "reason": f"near-duplicate (Jaccard {sim:.2f})"})
                    continue
            if call.method == "token_budget" and tokens_used + (c.token_count or 0) > p["max_tokens"]:
                rejected.append({"chunk_id": c.chunk_id, "reason": f"token budget ({tokens_used}+{c.token_count} > {p['max_tokens']})"})
                continue
            selected.append(c)
            token_sets.append(terms)
            tokens_used += c.token_count or 0
        ctx.evidence = selected
        return StageResult(summary=f"Selected {len(selected)} of {len(ctx.candidates)} candidates ({tokens_used} tokens)",
                           input={"candidates": len(ctx.candidates), "params": p},
                           output={"evidence": [candidate_view(c, 1200) for c in selected], "rejected": rejected, "evidence_tokens": tokens_used})  # fmt: skip


class SufficiencyGateStage(PipelineStage):
    stage_id = "sufficiency_gate"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        p = call.params
        n = len(ctx.evidence)
        dense_scores = [c.dense_score for c in ctx.evidence if c.dense_score is not None]
        top = max(dense_scores) if dense_scores else None
        checks: dict[str, Any] = {"evidence_chunks": n, "min_evidence_chunks": p["min_evidence_chunks"],
                                  "top_dense_score": round(top, 4) if top is not None else None, "min_dense_score": p["min_dense_score"]}  # fmt: skip
        if n < p["min_evidence_chunks"]:
            decision = SufficiencyDecision(sufficient=False, reason=f"Only {n} evidence chunk(s); at least {p['min_evidence_chunks']} required", checks=checks)
        elif p["min_dense_score"] is not None and top is not None and top < p["min_dense_score"]:
            decision = SufficiencyDecision(sufficient=False, reason=f"Top dense score {top:.3f} is below {p['min_dense_score']}", checks=checks)
        else:
            note = " (dense threshold not applied: no dense scores)" if p["min_dense_score"] is not None and top is None else ""
            decision = SufficiencyDecision(sufficient=True, reason=f"{n} evidence chunk(s) available{note}. Presence of evidence is not proof of support.", checks=checks)
        ctx.sufficiency = decision
        return StageResult(summary=("PASS: " if decision.sufficient else "ABSTAIN: ") + decision.reason, input=checks, output=decision.model_dump())


class ContextBuilderStage(PipelineStage):
    stage_id = "context_builder"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        if ctx.sufficiency and not ctx.sufficiency.sufficient:
            return bypass("Evidence gate failed; no prompt is built.")
        revision = await self.services.require_active_revision()
        tokenizer = await asyncio.to_thread(self.services.tokenizer_for, revision)
        ctx.context_text, ctx.citations, stats = gen.build_context(ctx.evidence, call.method, call.params, tokenizer)
        ctx.messages = gen.build_messages(ctx.question, ctx.context_text)
        return StageResult(summary=f"{len(ctx.citations)} sources, ~{stats['context_tokens']} tokens", input={"evidence": len(ctx.evidence), "params": call.params},
                           output={"stats": stats, "source_labels": {c.marker: c.chunk_id for c in ctx.citations}, "messages": ctx.messages})  # fmt: skip


class GenerationStage(PipelineStage):
    stage_id = "generation"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        if not ctx.messages:
            return bypass("No prompt was built (insufficient evidence); the model is not called.")
        p = call.params
        ollama = self.services.ollama
        model = await ollama.resolve_model(p["model"], self.services.settings.ollama_chat_model)
        info = await self.services.model_info(model)
        thinking_model = "thinking" in info.get("capabilities", [])
        think = False if thinking_model else None
        options = model_options(p)
        ctx.model = model
        parts: list[str] = []
        stats: dict[str, Any] = {}
        t0 = time.perf_counter()
        first_token_ms = None
        async for event in ollama.chat_stream(model, ctx.messages, options, think=think, timeout=p["timeout_s"],
                                                 strip_reasoning=thinking_model):
            if "delta" in event:
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - t0) * 1000
                parts.append(event["delta"])
                if p["stream"]:
                    await call.emit_delta(event["delta"])
            else:
                stats = event
        ctx.raw_answer = "".join(parts).strip()
        if not p["stream"] and ctx.raw_answer:
            await call.emit_delta(ctx.raw_answer)
        return StageResult(
            summary=f"{model}: {stats.get('eval_count') or len(parts)} tokens" + (f", first token {first_token_ms:.0f} ms" if first_token_ms else ""),
            input={"model": model, "options": options, "think": think, "messages": len(ctx.messages)},
            output={"answer": ctx.raw_answer, "first_token_ms": round(first_token_ms, 1) if first_token_ms else None,
                    "done_reason": stats.get("done_reason"), "prompt_tokens": stats.get("prompt_eval_count"),
                    "output_tokens": stats.get("eval_count"), "ollama_total_ms": round(stats.get("total_duration_ms") or 0, 1),
                    "reasoning_chars_removed": stats.get("reasoning_chars_removed", 0)},
        )  # fmt: skip


class CitationVerificationStage(PipelineStage):
    stage_id = "citation_verification"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        if not ctx.raw_answer:
            return bypass("No generated answer to verify.")
        mongo = self.services.mongo
        chunks = await asyncio.to_thread(mongo.get_chunks, [c.chunk_id for c in ctx.citations])
        docs = await asyncio.to_thread(mongo.get_documents, {c.doc_id: c.version_id for c in chunks.values()}, call.params["verify_spans"])
        ctx.citations, ctx.citation_report = gen.verify_citations(ctx.raw_answer, ctx.citations, chunks, docs, call.params["verify_spans"])
        r = ctx.citation_report
        return StageResult(
            summary=f"{len(r.cited_markers)} valid citation(s), {len(r.invalid_markers)} invalid, {r.sentences_with_citation}/{r.sentences_total} sentences cited",
            input={"answer_chars": len(ctx.raw_answer), "available_markers": [c.marker for c in ctx.citations], "params": call.params},
            output={"report": r.model_dump(), "citations": [c.model_dump(exclude={"excerpt"}) for c in ctx.citations]},
        )  # fmt: skip


class ResponseGuardStage(PipelineStage):
    stage_id = "response_guard"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        p = call.params
        cv = call.config.stage("citation_verification")
        notes: list[str] = []
        answer = ctx.raw_answer
        if ctx.sufficiency and not ctx.sufficiency.sufficient:
            outcome, answer = "insufficient_evidence", p["abstention_message"]
            notes.append(f"Evidence gate: {ctx.sufficiency.reason}")
        elif answer.lstrip().upper().startswith(gen.INSUFFICIENT_MARKER):
            outcome = "insufficient_evidence"
            explanation = answer.lstrip()[len(gen.INSUFFICIENT_MARKER):].strip(" :—-\n")
            answer = p["abstention_message"] + (f"\n\n_Model note: {explanation}_" if explanation else "")
            notes.append("The model reported that the sources do not contain the answer.")
        else:
            outcome = "answered"
            report = ctx.citation_report
            if report and report.invalid_markers:
                for m in report.invalid_markers:
                    answer = re.sub(rf"\[\s*{m}\s*\]", "", answer)
                notes.append(f"Removed citation(s) to non-existent sources: {', '.join(report.invalid_markers)}")
            if cv.params["require_citations"] and (report is None or not report.cited_markers):
                if p["on_missing_citations"] == "abstain":
                    outcome, answer = "abstained", p["abstention_message"]
                    notes.append("No valid citation in the answer; replaced with abstention (policy: abstain).")
                else:
                    notes.append("Warning: the answer contains no valid citation; treat it as unsupported.")
            if report and report.span_failures:
                notes.append(f"Source span check failed for {', '.join(report.span_failures)}")
        if outcome == "answered":
            cited = [c for c in ctx.citations if c.cited]
            others = [c for c in ctx.citations if not c.cited]
        else:  # an abstention cites nothing; markers in the model's explanation are not support
            cited, others = [], [c.model_copy(update={"cited": False}) for c in ctx.citations]
        ctx.result = AnswerResult(answer=answer, outcome=outcome, citations=cited + others, citation_report=ctx.citation_report,
                                  guard_notes=notes, model=ctx.model)  # fmt: skip
        return StageResult(summary=f"Outcome: {outcome}" + (f" ({len(notes)} note(s))" if notes else ""),
                           input={"sufficient": ctx.sufficiency.sufficient if ctx.sufficiency else None, "raw_answer": ctx.raw_answer},
                           output={"outcome": outcome, "answer": answer, "notes": notes, "cited_sources": [c.marker for c in cited]})  # fmt: skip
