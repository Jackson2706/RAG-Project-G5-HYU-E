"""Online pipeline orchestrator: runs the registered stages in order and records an execution trace.

Execution contract:
* The configuration is resolved and frozen *before* the run; it never changes mid-request.
* Disabled stages are recorded as ``bypassed`` with a reason; data passes through unchanged.
* A failing stage is recorded as ``failed``; downstream stages are not executed and stay ``pending``.
* Every stage's actual input/output, parameters and measured duration go into the trace
  (bounded in size) and are streamed as events.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import Settings
from app.ingestion.chunking import Tokenizer, load_tokenizer
from app.models.config import ResolvedConfig
from app.models.documents import IndexRevision
from app.models.pipeline import EventType, ExecutionTrace, PipelineContext, PipelineEvent, StageTrace
from app.rag import stages as st
from app.rag.registry import ONLINE_ORDER, STAGES
from app.rag.retrieval import BM25Index
from app.repositories.mongodb import MongoRepository
from app.repositories.qdrant import QdrantRepository
from app.services.embeddings import EmbeddingProvider, load_embedder
from app.services.ollama import OllamaClient
from app.services.tracing import bound, utcnow

log = logging.getLogger(__name__)
Emit = Callable[[PipelineEvent], Awaitable[None]]


class NoActiveIndexError(RuntimeError):
    pass


class RAGServices:
    """Shared dependencies of the online stages (one instance per application)."""

    def __init__(self, settings: Settings, mongo: MongoRepository, qdrant: QdrantRepository, ollama: OllamaClient,
                 embedder_factory: Callable[[IndexRevision], EmbeddingProvider] | None = None,
                 tokenizer_factory: Callable[[IndexRevision], Tokenizer] | None = None) -> None:  # fmt: skip
        self.settings = settings
        self.mongo = mongo
        self.qdrant = qdrant
        self.ollama = ollama
        self._embedder_factory = embedder_factory or self._default_embedder
        self._tokenizer_factory = tokenizer_factory or self._default_tokenizer
        self._bm25: BM25Index | None = None
        self._bm25_lock = asyncio.Lock()
        self._model_info: dict[str, dict[str, Any]] = {}

    def _default_embedder(self, revision: IndexRevision) -> EmbeddingProvider:
        c = revision.embedding
        return load_embedder(c.model_id, c.model_revision, c.normalize, c.query_instruction, c.distance, self.settings.embedding_device)

    def _default_tokenizer(self, revision: IndexRevision) -> Tokenizer:
        tok_id = revision.offline_config["chunking"]["params"]["tokenizer_id"]
        rev = revision.embedding.model_revision if tok_id == revision.embedding.model_id else None
        return load_tokenizer(tok_id, rev)

    def embedder_for(self, revision: IndexRevision) -> EmbeddingProvider:
        """Query embedder matching the revision's embedding contract (validated, never mixed)."""
        embedder = self._embedder_factory(revision)
        if embedder.contract.contract_hash() != revision.embedding.contract_hash():
            raise RuntimeError("Query embedder does not match the active index's embedding contract")
        return embedder

    def tokenizer_for(self, revision: IndexRevision) -> Tokenizer:
        return self._tokenizer_factory(revision)

    async def active_revision(self) -> IndexRevision | None:
        return await asyncio.to_thread(self.mongo.active_revision)

    async def require_active_revision(self) -> IndexRevision:
        revision = await self.active_revision()
        if revision is None:
            raise NoActiveIndexError("No active index. Ingest documents first: python scripts/ingest.py --path data/raw")
        return revision

    async def bm25_for(self, revision: IndexRevision, remove_stopwords: bool) -> BM25Index:
        async with self._bm25_lock:
            idx = self._bm25
            if idx is None or idx.revision_id != revision.revision_id or idx.remove_stopwords != remove_stopwords:
                chunks = await asyncio.to_thread(self.mongo.chunks_for_revision, revision.revision_id)
                idx = await asyncio.to_thread(BM25Index, chunks, remove_stopwords, revision.revision_id)
                self._bm25 = idx
            return idx

    async def model_info(self, model: str) -> dict[str, Any]:
        if model not in self._model_info:
            self._model_info[model] = await self.ollama.show(model)
        return self._model_info[model]


def build_stages(services: RAGServices) -> dict[str, st.PipelineStage]:
    implemented = [st.QueryUnderstandingStage, st.ConstraintValidationStage, st.MetadataFilteringStage, st.DenseRetrievalStage,
                   st.LexicalRetrievalStage, st.HybridFusionStage, st.MetadataEnrichmentStage, st.EvidenceSelectionStage,
                   st.SufficiencyGateStage, st.ContextBuilderStage, st.GenerationStage, st.CitationVerificationStage,
                   st.ResponseGuardStage]  # fmt: skip
    out: dict[str, st.PipelineStage] = {cls.stage_id: cls(services) for cls in implemented}
    for stage_id in ONLINE_ORDER:
        out.setdefault(stage_id, st.PlannedStage(services, stage_id))
    return out


def _revision_summary(revision: IndexRevision | None) -> dict[str, Any]:
    if revision is None:
        return {}
    return {"revision_id": revision.revision_id, "collection": revision.collection_name, "doc_count": revision.doc_count,
            "chunk_count": revision.chunk_count, "embedding": revision.embedding.model_dump(),
            "chunking": revision.offline_config.get("chunking")}  # fmt: skip


class RAGPipeline:
    def __init__(self, services: RAGServices) -> None:
        self.services = services
        self.stages = build_stages(services)

    async def run(self, question: str, config: ResolvedConfig, session_id: str | None = None, emit: Emit | None = None,
                  stop_after: str | None = None, persist: bool = True) -> ExecutionTrace:  # fmt: skip
        """Execute the online pipeline. `stop_after` ends the run after that stage (used for retrieval-only evaluation)."""
        settings = self.services.settings
        request_id = uuid.uuid4().hex
        started = time.perf_counter()

        async def send(type_: EventType, **kw: Any) -> None:
            if emit:
                await emit(PipelineEvent(type=type_, request_id=request_id, timestamp=utcnow(), **kw))

        ctx = PipelineContext(request_id=request_id, session_id=session_id, question=question, query=question)
        trace = ExecutionTrace(request_id=request_id, session_id=session_id, created_at=utcnow(), question=question, status="running", config=config)
        trace.stages = [StageTrace(request_id=request_id, stage_id=s, stage_name=STAGES[s].stage_name, method_id=config.stage(s).method,
                                   status="pending", configuration=config.stage(s).params) for s in ONLINE_ORDER]  # fmt: skip

        async def delta(text: str) -> None:
            await send("answer_delta", delta=text)

        try:
            try:
                ctx.index_revision = trace.index_revision = _revision_summary(await self.services.active_revision())
            except Exception as exc:  # database unreachable: the dense stage will report the error too
                log.warning("could not read active revision: %s", exc)
            await send("pipeline_started", data={"question": question, "config_hash": config.config_hash, "index_revision": trace.index_revision})
            for st_trace in trace.stages:
                spec = STAGES[st_trace.stage_id]
                sc = config.stage(st_trace.stage_id)
                method = spec.method(sc.method)
                st_trace.implementation_status = method.status.value if method else None
                if not sc.enabled:
                    st_trace.status, st_trace.bypass_reason = "bypassed", f"{spec.stage_name} is disabled in this configuration; input passed through unchanged."
                    st_trace.summary = "Disabled"
                    st_trace.started_at = st_trace.completed_at = utcnow()
                    st_trace.duration_ms = 0.0
                    await send("stage_bypassed", stage=st_trace)
                    continue
                st_trace.status, st_trace.started_at = "running", utcnow()
                await send("stage_started", stage=st_trace)
                t0 = time.perf_counter()
                try:
                    result = await self.stages[st_trace.stage_id].execute(ctx, st.StageCall(sc.method, sc.params, config, delta))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    st_trace.status, st_trace.error = "failed", f"{exc.__class__.__name__}: {exc}"
                    st_trace.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                    st_trace.completed_at = utcnow()
                    st_trace.summary = "Failed"
                    trace.status, trace.error = "failed", f"{spec.stage_name}: {exc}"
                    await send("stage_failed", stage=st_trace, error=st_trace.error)
                    break
                st_trace.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                st_trace.completed_at = utcnow()
                st_trace.status, st_trace.summary, st_trace.bypass_reason = result.status, result.summary, result.bypass_reason
                st_trace.input = bound(result.input, settings.trace_max_string, settings.trace_max_items)
                st_trace.output = bound(result.output, settings.trace_max_string, settings.trace_max_items)
                await send("stage_completed" if result.status == "completed" else "stage_bypassed", stage=st_trace)
                if stop_after == st_trace.stage_id:
                    break
            if trace.status == "running":
                trace.status = "completed"
                trace.result = ctx.result
                if ctx.result:
                    await send("answer_completed", result=ctx.result)
        except asyncio.CancelledError:
            trace.status, trace.error = "cancelled", "Client disconnected or request was cancelled"
            raise
        finally:
            trace.total_ms = round((time.perf_counter() - started) * 1000, 2)
            if persist:
                try:
                    await asyncio.shield(asyncio.to_thread(self.services.mongo.save_trace, trace))
                except Exception as exc:
                    log.warning("could not persist trace %s: %s", request_id, exc)
        if trace.status == "completed":
            await send("pipeline_completed", trace=trace)
        else:
            await send("pipeline_error", error=trace.error, trace=trace)
        return trace
