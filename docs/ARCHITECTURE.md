# Architecture

## Overview

```mermaid
flowchart LR
  subgraph Browser
    UI["React + Vite<br/>127.0.0.1:5173"]
  end
  subgraph Backend["FastAPI · Conda env RAG · 127.0.0.1:8000"]
    API["Routers<br/>chat · pipeline · documents · system"]
    REG["Registry<br/>(stages, methods, params)"]
    PIPE["RAGPipeline<br/>15 online stages"]
    ING["IngestionPipeline<br/>6 offline stages"]
    EMB["Sentence Transformers<br/>BGE-small-en-v1.5"]
  end
  subgraph Docker["Docker Compose (localhost only)"]
    MDB[("MongoDB 8.0<br/>:27017")]
    QD[("Qdrant 1.19<br/>:6333")]
  end
  OLL["Ollama<br/>:11434"]

  UI -- "REST + SSE (fetch)" --> API
  API --> REG
  API --> PIPE
  API --> ING
  PIPE --> EMB
  ING --> EMB
  PIPE --> MDB & QD
  ING --> MDB & QD
  PIPE -- "/api/chat (stream)" --> OLL
  API -- "/api/tags, /api/show" --> OLL
```

Only FastAPI talks to MongoDB, Qdrant and Ollama. In development the Vite dev server proxies
`/api` to FastAPI, so the browser sees a single origin (CORS is still configured for
`127.0.0.1:5173` and `localhost:5173`).

## Responsibilities

| Component | Owns | Code |
|---|---|---|
| **MongoDB** | documents (one record per version, incl. normalized text), chunks (text, spans, metadata), index revisions, execution traces, presets, `extracted_facts` schema | `backend/app/repositories/mongodb.py` |
| **Qdrant** | one point per chunk: vector + compact payload (`doc_id`, `chunk_id`, `version_id`, campus, language, audience, document_type, topics, academic_year); versioned collections + the `*_active` alias | `backend/app/repositories/qdrant.py` |
| **Sentence Transformers** | document and query embeddings under an explicit contract | `backend/app/services/embeddings.py` |
| **Ollama** | answer generation only (never embeddings in the MVP) | `backend/app/services/ollama.py` |
| **Registry** | every stage/method/hyperparameter, defaults, validation, presets | `backend/app/rag/registry.py` |
| **Frontend** | rendering registry controls, streaming chat, trace inspection | `frontend/src/` |

## Offline ingestion

```mermaid
flowchart TD
  A["data/raw or data/samples"] --> B["Load: sorted scan, SHA-256,<br/>doc_id = uuid5(source_uri)"]
  B --> C["Parse + normalize<br/>blocks with section path, page, span"]
  C --> D["version_id = hash(sha256, parser_id, parse params)"]
  D --> E["Chunk (BGE tokenizer)<br/>deterministic chunk_id"]
  E --> F["Metadata (declared / rule) + provenance"]
  F --> G["revision_id = hash(contract, offline config, doc versions, chunk ids)"]
  G -->|"revision exists & verifies"| R["Reuse (optionally re-activate)"]
  G -->|new| H["Create collection hyu_chunks_&lt;revision&gt;"]
  H --> I["Embed (reuse vectors of unchanged chunks)"]
  I --> J["Upsert Qdrant points + MongoDB docs/chunks"]
  J --> K{"verify_revision"}
  K -->|ok| L["Move alias hyu_chunks_active → new collection<br/>mark revision active"]
  K -->|fail| M["Delete new collection, mark failed<br/>active alias untouched"]
  L --> N["data/manifests/&lt;revision&gt;.json<br/>data/processed/&lt;revision&gt;/chunks.jsonl"]
```

### Document versioning & provenance

- **Identity vs. version:** `doc_id = uuid5(source_uri)` never changes for a file path;
  `version_id` changes when the bytes or the parser contract change.
- **Immutable versions:** MongoDB stores documents with `_id = "<doc_id>:<version_id>"`, so a
  rebuild never overwrites the text that an older (still active) revision's spans point into.
- **Deterministic chunk IDs:** `uuid5(doc_id | version_id | chunker_id | config_hash | span | sha256(text))`.
- **Revisions:** an *index revision* is a hash of the embedding contract, offline configuration,
  document versions and chunk IDs. Two teammates ingesting the same files with the same settings
  obtain the same revision ID (verified: two fresh rebuilds both produced `c384769ff7b0`).
- **Spans:** `chunk.text == document.content[span.start:span.end]` is checked for every chunk
  during verification and again for every cited chunk at answer time.

### Safe publishing

The active index is the Qdrant alias `hyu_chunks_active` plus the MongoDB revision with
`status = "active"`. A rebuild writes a *new* collection while the old one keeps serving; only
after `verify_revision` passes are the alias (atomic delete+create in one request) and the
MongoDB status switched. `scripts/verify_index.py` checks that both agree.

## Online request

```mermaid
sequenceDiagram
  participant UI as React (fetch + SSE parser)
  participant API as FastAPI /chat/stream
  participant P as RAGPipeline
  participant Q as Qdrant
  participant M as MongoDB
  participant O as Ollama

  UI->>API: POST {question, session_id, config draft}
  API->>API: resolve_config → frozen ResolvedConfig (422 if invalid)
  API-->>UI: event: pipeline_started
  loop 15 registered stages
    API-->>UI: stage_started / stage_completed / stage_bypassed / stage_failed
  end
  P->>Q: query_points(vector, payload filter)
  P->>M: chunks + documents by id
  P->>O: /api/chat (stream, options, think=false)
  O-->>P: content chunks
  P-->>UI: answer_delta …
  P->>M: re-read spans of cited chunks
  API-->>UI: answer_completed {answer, outcome, citations}
  P->>M: save execution trace
  API-->>UI: pipeline_completed {full trace}
```

- The configuration snapshot is resolved and frozen **before** execution and stored with the
  trace (`config_hash`).
- The pipeline runs in an `asyncio` task that pushes events to a queue; the SSE generator drains
  it and sends a keep-alive comment every 10 s. If the client disconnects, the task is cancelled
  (closing the Ollama stream) and the trace is saved with status `cancelled`.
- Blocking work (PyMongo, Qdrant client, Sentence Transformers) runs via `asyncio.to_thread`;
  Ollama is called with an async `httpx` client.

## Pipeline registry

```mermaid
flowchart LR
  R["registry.py<br/>StageSpec → MethodSpec → ParameterSpec"] -->|"GET /pipeline/registry"| UI["Configuration tab<br/>(controls generated)"]
  UI -->|"draft"| V["POST /pipeline/config/validate"]
  V -->|"errors / warnings / resolved"| UI
  UI -->|"draft (online stages)"| C["POST /chat/stream"]
  C --> RC["resolve_config()"] --> RUN["RAGPipeline.run()"]
  R --> RC
```

The UI never hardcodes an algorithm list. A planned method is visible but cannot be selected while
its stage is enabled, and the backend rejects it regardless (`ImplementationStatus.planned`).

## Real-time trace events

| Event | Payload |
|---|---|
| `pipeline_started` | question, config hash, active index revision |
| `stage_started` | `StageTrace` with status `running` |
| `stage_completed` / `stage_bypassed` / `stage_failed` | full `StageTrace`: method, implementation status, applied parameters, bounded input/output, measured `duration_ms`, error/bypass reason |
| `answer_delta` | generated text fragment |
| `answer_completed` | `AnswerResult` (final answer after the guard, outcome, citations, notes) |
| `pipeline_completed` / `pipeline_error` | full `ExecutionTrace` (also persisted in `execution_traces`) |

Schemas: `backend/app/models/pipeline.py` (`PipelineEvent`, `StageTrace`, `ExecutionTrace`) and
their TypeScript mirrors in `frontend/src/types/api.ts`. Payloads are bounded by
`app/services/tracing.py::bound` (strings ≤ 4000 chars, lists ≤ 50 items, explicit truncation
markers); embeddings are shown as model/dimension/norm/8-value preview, never in full.

## Frontend structure

```
src/
  App.tsx                    state wiring (config, chat, system), tab switching
  services/api.ts            REST client + fetch-based SSE parser
  hooks/                     usePipelineConfig (registry/draft/validation/presets), useChat (conversations,
                             streaming, per-request live traces), useSystem (health, Ollama), useMediaQuery
  lib/config.ts              pure draft-editing helpers (unit-tested)
  components/layout/         Header (service status), Workspace (resizable panels / mobile view)
  components/pipeline/       Configuration & Execution tabs, ParamControl, StageConfigCard, StageTraceCard, JsonView
  components/chat/           ChatPanel, MessageItem (markdown + citation links), Citations
  components/documents/      IndexDialog (active revision, documents, rebuild)
  components/ui/primitives   shadcn-style components on Radix (Tabs, Switch, Slider, Tooltip, Dialog)
```

Per-viewer preferences (panel sizes, theme, draft configuration, conversation list) are kept in
`localStorage`; execution traces are fetched from `GET /api/v1/traces/{request_id}` when an older
request is selected, so each request always shows its own trace.
