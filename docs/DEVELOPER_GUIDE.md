# Developer Guide

## Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| Conda env **`RAG`** | Python 3.13.12 | The only Python environment for this project. Do not create a venv. |
| Docker Desktop (Compose v2) | — | Runs MongoDB 8.0.32 and Qdrant v1.19.0 |
| Ollama | 0.40.11 | Native API on `127.0.0.1:11434` |
| Node.js / npm | 26.4 / 11.17 | Frontend |

```bash
conda info --envs              # RAG must be listed
conda activate RAG
python --version               # 3.13.x
python -m pip --version        # …/envs/RAG/…
python -m pip install -r backend/requirements.txt
```

If `conda activate` fails in a non-interactive shell, run
`source "$(conda info --base)/etc/profile.d/conda.sh"` first, or use `conda run -n RAG python …`.
The scripts print a warning when they are not running inside `RAG`.

## Repository structure

```
hyu-compass/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app factory, wiring (build_state)
│   │   ├── config.py               Settings (env / backend/.env)
│   │   ├── api/                    deps.py (AppState) · chat.py · pipeline.py · documents.py · system.py
│   │   ├── models/                 config.py (registry schema) · documents.py · pipeline.py (context, traces, events)
│   │   ├── ingestion/              loaders · parsers · chunking · metadata · pipeline (build + verify + publish)
│   │   ├── rag/                    registry · stages · retrieval · generation · pipeline (orchestrator, RAGServices)
│   │   ├── repositories/           mongodb.py · qdrant.py
│   │   └── services/               embeddings.py · ollama.py · tracing.py
│   ├── tests/                      pytest (no Docker/Ollama needed)
│   ├── requirements.txt · pytest.ini · .env.example
├── frontend/                       React + TS + Vite + Tailwind v4 (see ARCHITECTURE.md › Frontend)
├── data/
│   ├── raw/                        real, approved documents (yours)
│   ├── samples/                    5 synthetic documents for development
│   ├── eval/                       sample_questions.jsonl, results/
│   ├── manifests/                  <revision>.json written by ingestion (commit these)
│   └── processed/                  <revision>/chunks.jsonl (generated, git-ignored)
├── scripts/                        ingest.py · verify_index.py · evaluate.py · export_registry.py
├── docs/
└── docker-compose.yml · .env.example
```

## Important classes

| Class / function | File | Role |
|---|---|---|
| `Settings` | `app/config.py` | all configuration |
| `StageSpec`, `MethodSpec`, `ParameterSpec` | `app/models/config.py` | registry schema + `validate_value` |
| `STAGES`, `resolve_config`, `BUILTIN_PRESETS` | `app/rag/registry.py` | the registry and validator |
| `PipelineContext`, `Candidate`, `StageTrace`, `PipelineEvent` | `app/models/pipeline.py` | typed online state and trace/event contracts |
| `PipelineStage` (ABC), `StageCall`, `StageResult` | `app/rag/stages.py` | stage interface |
| `RAGPipeline.run` | `app/rag/pipeline.py` | executes stages, emits events, persists traces |
| `RAGServices` | `app/rag/pipeline.py` | shared dependencies (repos, embedder, BM25 cache, Ollama) |
| `IngestionPipeline.run`, `verify_revision` | `app/ingestion/pipeline.py` | offline build, verification, publishing |
| `MongoRepository`, `QdrantRepository` | `app/repositories/` | the only database access code |
| `OllamaClient` | `app/services/ollama.py` | native Ollama API |

## API

Swagger UI: <http://127.0.0.1:8000/docs>. All routes are under `/api/v1`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | MongoDB, Qdrant, Ollama status + active index |
| GET | `/pipeline/registry` | stages, methods, parameters |
| GET | `/pipeline/config` | defaults (offline stages show the active index's settings) |
| POST | `/pipeline/config/validate` | validate a draft → errors, warnings, resolved snapshot |
| GET / POST | `/pipeline/presets` | list (with availability) / save |
| GET | `/ollama/status`, `/ollama/models`, `/ollama/show?model=` | Ollama connectivity and models |
| POST | `/chat` | run the pipeline, return answer + full trace |
| POST | `/chat/stream` | same, as Server-Sent Events |
| GET | `/traces/{request_id}` | stored trace |
| GET | `/documents`, `/documents/{doc_id}` | documents of the active index (+ chunks) |
| GET | `/index` | revisions and alias target |
| POST | `/ingest/local` | `{path: "raw" \| "samples" \| …, config, activate}` |
| POST | `/ingest/files` | multipart upload into `data/raw/uploads/`, optional re-ingest |

Try it without the UI:

```bash
curl -s localhost:8000/api/v1/health | python -m json.tool
curl -s -X POST localhost:8000/api/v1/chat -H 'content-type: application/json' \
  -d '{"question":"How do I register for courses?","config":{"stages":{"generation":{"params":{"model":"qwen3:4b"}}}}}'
curl -N -X POST localhost:8000/api/v1/chat/stream -H 'content-type: application/json' -d '{"question":"How do I register for courses?"}'
```

## Method registry design

The registry is a list of `StageSpec`s. Each has methods; each method has `ParameterSpec`s
with type, default, range, control, **scope** and **level**. Rules:

1. A parameter must change backend behaviour. If nothing reads it, don't register it.
2. A method stays `planned` until its code exists *and is tested*. Planned methods may declare
   parameters for documentation; they are shown disabled.
3. Cross-stage rules (e.g. "RRF needs both retrievers") go in `_cross_stage_errors`.
4. After editing the registry run `python scripts/export_registry.py` (updates the docs table and
   the frontend test fixture).

## How to implement a planned method — example: cross-encoder reranking

**1. Implement** the stage branch in `app/rag/stages.py` (replace the `PlannedStage` entry for
`reranking` in `build_stages`):

```python
class RerankingStage(PipelineStage):
    stage_id = "reranking"

    async def execute(self, ctx: PipelineContext, call: StageCall) -> StageResult:
        p = call.params
        head, tail = ctx.candidates[: p["top_n"]], ctx.candidates[p["top_n"]:]
        model = await asyncio.to_thread(self.services.cross_encoder, p["model_id"])
        scores = await asyncio.to_thread(model.predict, [(ctx.query, c.text or "") for c in head])
        before = [c.chunk_id for c in ctx.candidates]
        ranked = sorted(zip(head, scores), key=lambda cs: -float(cs[1]))
        ctx.candidates = [c.model_copy(update={"rerank_score": float(s)}) for c, s in ranked] + tail
        return StageResult(
            summary=f"Re-scored {len(head)} candidates with {p['model_id']}",
            input={"query": ctx.query, "candidates": len(ctx.candidates), "top_n": p["top_n"]},
            output={"order_before": before, "candidates": [candidate_view(c) | {"rerank_score": c.rerank_score} for c in ctx.candidates]},
        )
```

(add `rerank_score: float | None = None` to `Candidate`, a cached `cross_encoder()` loader to
`RAGServices`, and keep the original ranks so the trace shows movement — Lesson 5.)

**2. Register** it: in `registry.py` change the method's `status` to `IMPL`, set
`implementation="app.rag.stages.RerankingStage"` and add real parameters
(`model_id`, `top_n`).

**3. Test** it in `backend/tests/test_rag.py` with a fake model (ordering, unchanged tail,
`rerank_score` present, bypass when disabled).

**4. Regenerate** `python scripts/export_registry.py`, then run the ablation (`evaluate.py`
experiment D becomes available automatically).

## How to add a new stage

1. Add fields it reads/writes to `PipelineContext` (`app/models/pipeline.py`) with descriptions.
2. Add a `StageSpec` to `ONLINE_STAGES` in the right position (order = execution order).
3. Implement a `PipelineStage` subclass and add it to `build_stages`.
4. Mirror any new result fields in `frontend/src/types/api.ts` (only if the UI displays them).
5. Tests: pipeline ordering (`test_registry.py` lists the order), behaviour, and failure path.

## Adding or changing a hyperparameter

```python
integer("max_chunks_per_doc", "Max chunks per document", 0,
        "Limit evidence from one document (0 = no limit).", 0, 10, level="advanced"),
```

Read it in the stage via `call.params["max_chunks_per_doc"]`. The UI control appears
automatically; validation (type, range) is automatic. Use `scope=Scope.ingestion` or
`Scope.index` for offline parameters — those are part of the revision hash.

## Frontend development

```bash
cd frontend
npm ci            # exact versions from package-lock.json
npm run dev       # http://127.0.0.1:5173, proxies /api → 127.0.0.1:8000
npm run typecheck
npm test          # vitest + Testing Library (jsdom)
npm run build
```

- Design tokens are CSS variables in `src/index.css` (light/dark pairs; fonts IBM Plex Sans +
  JetBrains Mono, chosen with the UI/UX Pro Max skill — `.claude/skills/ui-ux-pro-max`).
- Use the primitives in `components/ui/primitives.tsx` (Radix-based) instead of new widgets.
- Never hardcode algorithm or parameter lists — read them from the registry.
- Set `VITE_API_TARGET` to proxy to another backend, or `VITE_API_BASE` to call one directly.

## Testing

```bash
conda activate RAG
cd backend && python -m pytest            # 80 tests: ingestion, registry, RAG, Ollama, API
python -m pytest -m integration           # only tests that use the cached real BGE model
cd ../frontend && npm test                # 11 tests
```

Unit tests use mongomock (MongoDB), in-memory Qdrant, a deterministic **non-semantic** hash
embedder, a regex tokenizer and an httpx mock of Ollama. The BGE integration test is skipped when
the model is not in the Hugging Face cache.

End-to-end check with real services: start everything, then
`python scripts/ingest.py --path data/samples && python scripts/verify_index.py` and ask a question
in the UI.

## Debugging

| Symptom | Check |
|---|---|
| `/health` → MongoDB not ok | `docker compose ps`; credentials in `backend/.env` must match the root `.env` |
| “No active index” | run `scripts/ingest.py`; `GET /api/v1/index` shows revisions |
| “Storage folder … already accessed” | Qdrant **local mode** is single-process: stop the API before CLI scripts, or use `POST /ingest/local` |
| Generation stage failed: connection | `ollama serve` / Ollama app; `curl 127.0.0.1:11434/api/tags` |
| “reasoning used the whole output budget” | thinking model (qwen3): raise *Max output tokens* to 2048 |
| Answers cite nothing / wrong sources | Execution tab → Context Builder (prompt), Generation (raw answer), Citation Verification |
| A document is missing | ingestion report: `load_issues` and per-document `error`; Index & Documents dialog |
| Filter returns nothing | Execution tab → Constraint Validation / Metadata Filtering output; check document metadata (unknown vs. wrong value) |
| `verify_index.py` fails | it lists the inconsistency; rebuild (`ingest.py`) — the failed revision never becomes active |

Every chat response has a `request_id`; `GET /api/v1/traces/<id>` returns everything that happened.

## Conventions

- Type hints everywhere; Pydantic models for anything crossing a boundary.
- Blocking calls in async code go through `asyncio.to_thread`.
- No fabricated outputs: an unimplemented method is `planned`; a stage that does nothing returns
  `bypassed` with a reason.
- Do not change embedding/chunking contracts without a new revision (the code enforces this).
- Keep `data/raw/` documents unmodified; never commit credentials (`.env` files are git-ignored).
- Tests must not need Docker or Ollama; integration tests must skip cleanly.
