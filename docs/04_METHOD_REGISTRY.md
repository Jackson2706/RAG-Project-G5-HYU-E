# 04 · The Method Registry

`backend/app/rag/registry.py` is the **single list** of every pipeline block, every algorithm for
each block, its implementation status and its hyperparameters. Nothing else in the project keeps
such a list. The API, the UI and the pipeline runner all read it.

## Why a registry?

Without one, adding an algorithm would mean editing the runner, the API and the React code. With the
registry you add **one entry**, and then:

- FastAPI sends it to the browser (`GET /api/pipeline/registry`),
- the UI shows the method in its block's dropdown and its hyperparameters as controls,
- FastAPI validates the values users choose,
- the runner creates your class and calls it through the block's abstract method.

```mermaid
flowchart LR
  B["blocks/&lt;group&gt;/&lt;block&gt;/my_method.py<br/>class MyMethod(BaseX)"] -->|imported by| REG["registry.py<br/>PIPELINE = [Stage(..., methods=[Method(...)])]"]
  REG -->|registry_json()| API1["GET /api/pipeline/registry"]
  API1 --> HOOK["usePipelineConfig.ts"]
  HOOK --> UI["Configuration tab<br/>StageConfigCard · ParamControl · DisabledStage"]
  UI -->|"every change"| VAL["POST /api/pipeline/config/validate"]
  VAL -->|"errors per stage/param"| UI
  UI -->|"question + stages"| CHAT["POST /api/chat/stream"]
  CHAT --> RUN["run_rag() in pipeline.py"]
  RUN -->|"create_block(stage, method, params)"| REG
  RUN -->|"block.retrieve(...) etc."| B
```

Import direction: `registry.py` imports the algorithm classes. Algorithm files never import the
registry. That avoids circular imports.

## The three building blocks

```python
@dataclass(frozen=True)
class Param:            # one hyperparameter
    type: "integer" | "float" | "boolean" | "enum" | "string"
    default: Any
    label: str           # shown in the UI
    description: str     # shown under the control
    ui: "slider" | "number" | "toggle" | "select" | "text" | "ollama_model" = "slider"
    min / max / step     # allowed range (numbers)
    options              # allowed values (enum)
    scope: "runtime" | "ingestion" | "index" = "runtime"
    advanced: bool = False   # True = shown under "Advanced settings" (folded) in the UI

@dataclass(frozen=True)
class Method:           # one algorithm (= one file in the block's folder)
    method_id: str       # unique ID, used in configurations and traces
    name: str            # shown in the dropdown
    cls: type            # the class; must inherit from the block's abstract class
    implemented: bool    # False = shown greyed out, cannot run
    description: str
    parameters: dict[str, Param]

@dataclass(frozen=True)
class Stage:            # one block (= one folder in app/rag/blocks/<group>/)
    stage_id: str        # also the folder name, e.g. "dense_retrieval"
    name: str            # e.g. "Metadata Prefiltering"
    phase: "offline" | "online"
    base_class: type     # the abstract class from the folder's base.py
    description: str
    methods: list[Method]
    default_method: str | None   # None = off by default (optional stages only)
    optional: bool = False       # optional stages can be off; then they are skipped
    # derived, not written by hand:
    folder -> str        # from base_class's module, e.g. "retrieval/dense_retrieval"
    group  -> str        # GROUPS[group folder], e.g. "retrieval" -> "Candidate Retrieval"
```

The group of a block is **where its folder is**. Move a block folder into another group folder and the
UI heading follows; there is no `group=` argument to keep in sync. The six group folders and their
labels are the `GROUPS` dictionary in `registry.py`.

A real entry, with the import that belongs to it:

```python
from app.rag.blocks.retrieval.dense_retrieval.base import BaseDenseRetriever
from app.rag.blocks.retrieval.dense_retrieval.qdrant_cosine import QdrantDenseRetriever
...
Stage("dense_retrieval", "Dense Retrieval", "online", BaseDenseRetriever,
      "Find the chunks whose meaning is closest to the question.", default_method="qdrant_cosine", optional=True,
      methods=[
          Method("qdrant_cosine", "Qdrant cosine", QdrantDenseRetriever, True, "Embed the question and find the nearest chunk vectors.", parameters={
              "top_k": Param("integer", 5, "Top K", "How many of the most similar chunks to retrieve (benchmarks use up to 1000).",
                             ui="number", min=1, max=1000),
              "search_mode": Param("enum", "exact", "Search mode", "exact = compare with every vector; hnsw = approximate HNSW graph search.",
                                   ui="select", options=("exact", "hnsw"), advanced=True),
              "hnsw_ef": Param("integer", 100, "HNSW ef", "Search breadth for hnsw mode: larger = closer to exact, slower.",
                               ui="number", min=4, max=1024, advanced=True),
          }),
      ]),
```

A planned method next to working ones (Chunking), and a shared parameter set:

```python
Method("recursive", "Recursive splitting", RecursiveChunker, True, "...", parameters=_chunk_params()),
Method("semantic", "Semantic chunking", SemanticChunker, False, "Cut where the topic changes."),
```

Small helper functions (`_chunk_params()`, `_llm_params()`, `_filter_params()`, `_rerank_depth()`)
return the parameter definitions several methods share, so e.g. prefiltering and postfiltering have
exactly the same policy settings.

The order of `PIPELINE` is the order the UI shows: offline blocks first, then online. The order of
execution is written out in `run_rag()`.

## Method IDs and implementation status

- `method_id` must be **unique in the whole registry** (e.g. `qdrant_cosine`, `bm25`,
  `candidate_postfilter`). It appears in configurations, traces and the UI.
- `implemented=False` = planned. The UI shows it greyed out, validation rejects it, and
  `create_block()` refuses to create it.
- A block whose methods are all planned is drawn as a darkened, disabled block with
  "Not implemented". As soon as one method is `implemented=True`, the block becomes a normal card.
- Never set `implemented=True` just because a skeleton file exists. Only do it when the algorithm
  works and its test passes.

## Hyperparameters and their scope

| scope | means | example | takes effect |
|---|---|---|---|
| `runtime` | used while answering | Top K, temperature | the next question |
| `ingestion` | used while indexing | chunk size, chunk overlap | after **re-indexing** |
| `index` | changes how vectors are stored/indexed | HNSW `m`, `ef_construct`, indexing threshold | needs a fresh index |

Non-runtime parameters get a yellow **re-index needed** badge. The Configuration tab also warns when
your chunk settings differ from how the current index was built (`index_info()` in `database.py`).
Stored vectors are never changed silently.

Every implemented hyperparameter (generated from `registry.py`):

| Block | Method | Parameter | Default | Range / options | Scope | Basic/Advanced |
|---|---|---|---|---|---|---|
| Chunking | `section_tokens` | `chunk_size` | 256 | 64–512 | ingestion | basic |
| Chunking | `section_tokens` | `chunk_overlap` | 32 | 0–128 | ingestion | basic |
| Chunking | `fixed_tokens` | `chunk_size` | 256 | 64–512 | ingestion | basic |
| Chunking | `fixed_tokens` | `chunk_overlap` | 32 | 0–128 | ingestion | basic |
| Chunking | `recursive` | `chunk_size` | 256 | 64–512 | ingestion | basic |
| Chunking | `recursive` | `chunk_overlap` | 32 | 0–128 | ingestion | basic |
| Vector Indexing | `qdrant_mongodb` | `hnsw_m` | 16 | 4–64 | index | advanced |
| Vector Indexing | `qdrant_mongodb` | `hnsw_ef_construct` | 100 | 16–512 | index | advanced |
| Vector Indexing | `qdrant_mongodb` | `indexing_threshold_kb` | 20000 | 1–1e+06 | index | advanced |
| Query Understanding | `stated_criteria` | `campus` | "" | text | runtime | basic |
| Query Understanding | `stated_criteria` | `audience` | "" | text | runtime | basic |
| Query Understanding | `stated_criteria` | `academic_year` | "" | text | runtime | basic |
| Query Understanding | `stated_criteria` | `document_type` | "" | text | runtime | basic |
| Query Rewriting | `llm_rewrite` | `model` | "" | installed Ollama models | runtime | basic |
| Query Rewriting | `llm_rewrite` | `temperature` | 0.0 | 0–1 | runtime | advanced |
| Query Rewriting | `llm_rewrite` | `max_tokens` | 64 | 16–1024 | runtime | advanced |
| Query Rewriting | `multi_query` | `model` | "" | installed Ollama models | runtime | basic |
| Query Rewriting | `multi_query` | `temperature` | 0.0 | 0–1 | runtime | advanced |
| Query Rewriting | `multi_query` | `max_tokens` | 192 | 16–1024 | runtime | advanced |
| Query Rewriting | `multi_query` | `num_queries` | 3 | 2–6 | runtime | basic |
| Query Rewriting | `multi_query` | `include_original` | true | text | runtime | basic |
| Query Rewriting | `multi_query` | `rrf_k` | 60 | 1–200 | runtime | advanced |
| Query Rewriting | `hyde` | `model` | "" | installed Ollama models | runtime | basic |
| Query Rewriting | `hyde` | `temperature` | 0.0 | 0–1 | runtime | advanced |
| Query Rewriting | `hyde` | `max_tokens` | 160 | 16–1024 | runtime | advanced |
| Metadata Prefiltering | `qdrant_prefilter` | `include_unknown` | true | text | runtime | basic |
| Metadata Prefiltering | `qdrant_prefilter` | `include_campus_wide` | true | text | runtime | basic |
| Dense Retrieval | `qdrant_cosine` | `top_k` | 5 | 1–1000 | runtime | basic |
| Dense Retrieval | `qdrant_cosine` | `search_mode` | exact | exact / hnsw | runtime | advanced |
| Dense Retrieval | `qdrant_cosine` | `hnsw_ef` | 100 | 4–1024 | runtime | advanced |
| Lexical Retrieval | `bm25` | `top_k` | 5 | 1–1000 | runtime | basic |
| Lexical Retrieval | `bm25` | `k1` | 1.2 | 0–3 | runtime | advanced |
| Lexical Retrieval | `bm25` | `b` | 0.75 | 0–1 | runtime | advanced |
| Hybrid Retrieval (Fusion) | `rrf` | `rrf_k` | 60 | 1–200 | runtime | advanced |
| Hybrid Retrieval (Fusion) | `rrf` | `top_k` | 5 | 1–1000 | runtime | basic |
| Metadata Postfiltering | `candidate_postfilter` | `include_unknown` | true | text | runtime | basic |
| Metadata Postfiltering | `candidate_postfilter` | `include_campus_wide` | true | text | runtime | basic |
| Reranking | `coverage` | `rerank_depth` | 20 | 1–1000 | runtime | basic |
| Reranking | `cross_encoder` | `rerank_depth` | 20 | 1–1000 | runtime | basic |
| Reranking | `cross_encoder` | `batch_size` | 32 | 1–256 | runtime | advanced |
| Reranking | `cross_encoder` | `device` | auto | auto / cpu / mps | runtime | advanced |
| Reranking | `rankgpt` | `model` | "" | installed Ollama models | runtime | basic |
| Reranking | `rankgpt` | `temperature` | 0.0 | 0–1 | runtime | advanced |
| Reranking | `rankgpt` | `max_tokens` | 160 | 16–512 | runtime | advanced |
| Reranking | `rankgpt` | `rerank_depth` | 10 | 1–1000 | runtime | basic |
| Reranking | `rankgpt` | `max_words` | 80 | 20–300 | runtime | advanced |
| Evidence Selection | `top_k` | `top_k` | 3 | 1–20 | runtime | basic |
| Evidence Selection | `token_budget` | `max_evidence_tokens` | 2000 | 200–8000 | runtime | basic |
| Evidence Selection | `token_budget` | `deduplicate` | false | text | runtime | advanced |
| Evidence Sufficiency | `score_threshold` | `signal` | query_coverage | query_coverage / dense_similarity | runtime | basic |
| Evidence Sufficiency | `score_threshold` | `threshold` | 0.3 | 0–1 | runtime | basic |
| Evidence Sufficiency | `score_threshold` | `on_missing_signal` | abstain | abstain / proceed | runtime | advanced |
| Generation | `ollama_chat` | `model` | "" | installed Ollama models | runtime | basic |
| Generation | `ollama_chat` | `temperature` | 0.2 | 0–2 | runtime | basic |
| Generation | `ollama_chat` | `max_tokens` | 1024 | 64–4096 | runtime | basic |
| Generation | `ollama_chat` | `context_window` | 4096 | 1024–32768 | runtime | advanced |
| Generation | `ollama_chat` | `top_p` | 0.9 | 0.05–1 | runtime | advanced |
| Generation | `ollama_chat` | `top_k` | 40 | 1–200 | runtime | advanced |
| Generation | `ollama_chat` | `seed` | -1 | -1–2.14748e+09 | runtime | advanced |
| Generation | `ollama_chat` | `thinking` | off | off / on / model_default | runtime | advanced |
| Generation | `ollama_chat` | `timeout_s` | 300 | 10–3600 | runtime | advanced |

Planned methods may declare their expected parameters too; their controls stay hidden until the
method is implemented. *Advanced* parameters are folded under "Advanced settings" in each card.

**Metadata criteria** (campus, audience, academic year, document type) are the parameters of
Query Understanding → *Stated criteria*: what the student states. Both metadata filters read them
from there, so prefiltering and postfiltering always enforce the same conditions.

## Experiment presets

`backend/app/rag/presets.py` names complete configurations: `B0_BASIC_DENSE_RAG`, the offline
baselines `O0`–`O8` (plus `PROTOCOL_A_WHOLE_DOCUMENT`) and the online baselines `R0`–`R14`, and a
disabled `PROPOSED_APPROACH`. A preset stores **only** method IDs and parameter values; everything else
comes from the registry, and `preset_config(id, overrides)` validates it with `validate_config()`:

```python
{"id": "R2_HYBRID_RRF", "kind": "online", "name": "R2 — Hybrid (dense + BM25, RRF)",
 "description": "Both retrievers, merged by Reciprocal Rank Fusion (k = 60).",
 "stages": {"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 10}},
            "lexical_retrieval": {"method": "bm25", "params": {"top_k": 10}},
            "hybrid_fusion": {"method": "rrf", "params": {"rrf_k": 60, "top_k": 20}}}}
```

`GET /api/pipeline/presets` sends them (with their validated configs) to the **Experiment preset**
menu; the benchmark runner (`evaluation/`) runs the same presets.

## The configuration a request carries

The frontend sends the chosen method and parameters per block. Missing blocks use their defaults,
and `"method": null` switches an optional block off.

```json
{
  "question": "How do I register for courses?",
  "stages": {
    "dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 4}},
    "generation": {"method": "ollama_chat", "params": {"model": "qwen3:4b", "temperature": 0.1, "max_tokens": 2048}},
    "metadata_prefiltering": {"method": null, "params": {}}
  }
}
```

`validate_config(stages)` returns the **complete** configuration (every block, all defaults filled
in) or raises `ConfigError`. It runs once, before anything executes, and the result is saved in the
trace. Changing the UI later never changes a running or finished request.

What is checked:
- the block and method exist, and the method is **implemented**;
- required blocks have a method (only optional blocks may be off);
- every parameter exists, has the right type and is within `min`/`max` (or in `options`);
- combinations: `chunk_overlap < chunk_size`; at least one retriever is on; two retrievers need a
  Hybrid Fusion method; fusion needs both retrievers; HyDE needs dense retrieval; the gate's
  `dense_similarity` signal needs dense retrieval; prefiltering/postfiltering need Query
  Understanding (their criteria).

Before a question runs, the API also checks what needs the running services (`check_runnable()` in
`api.py`): the selected **index** exists and was built with the selected embedding method (vectors of
different models cannot be compared), and every selected **Ollama model** is installed (otherwise the
message says `ollama pull …`). Problems that only appear while running are errors of that stage:
e.g. HNSW search on an index without a graph, or a prompt that does not fit the context window.

```json
{"valid": false, "errors": [{"stage_id": "dense_retrieval", "param": "top_k", "message": "Top K must be at most 1000"}]}
```

The UI shows each message under the right control and blocks sending until it is fixed.

## How the runner uses the registry

In `run_rag()` (`backend/app/rag/pipeline.py`):

```python
blocks = {s.stage_id: create_block(s.stage_id, config[s.stage_id]["method"], config[s.stage_id]["params"], services)
          for s in PIPELINE if s.phase == "online" and config[s.stage_id]["method"]}
...
prefilter = await step("metadata_prefiltering", lambda b: b.build_filter(criteria), {"criteria": criteria})
dense = await step("dense_retrieval", lambda b: b.retrieve(query, prefilter), {"query": query, "prefilter": prefilter})
...
postfiltered = await step("metadata_postfiltering", lambda b: b.filter_candidates(candidates, criteria), {...})
```

- `create_block()` looks up the method's class and creates it with its validated parameters. It
  **refuses** methods with `implemented=False`.
- `step()` runs a block through its abstract method and records it in the trace. A block without a
  selected method is recorded as **skipped** ("Not implemented yet." or "Switched off in the
  configuration.") and returns a default: no prefilter, the original question, the unchanged
  evidence, and so on. Skipped is never reported as completed.

## How React renders it

| Registry information | UI result (file in `frontend/src/components/pipeline/`) |
|---|---|
| block has no implemented method | darkened block, "Not implemented", disabled method list (`DisabledStage.tsx`) |
| block has an implemented method | normal card with a method dropdown (`StageConfigCard.tsx`) |
| `optional: true` | dropdown has "Off — skip this stage" |
| method `implemented: false` | option shown but disabled, "— not implemented" |
| `group` (from the folder) | a heading such as **Candidate Retrieval** above the blocks of `blocks/retrieval/` |
| `Param.advanced` | folded under "Advanced settings (n)" |
| presets (`presets.py`) | the **Experiment preset** menu: loads a preset; *Reset to preset*, *Save custom*, *Export/Import JSON* |
| index revisions (`GET /api/indexes`) | the **Index to search** menu; a warning when offline settings differ from how that index was built |
| `trace_details` of a block | a **Details** tab in the Execution view |
| `Param.ui` | slider / number / toggle / select / text / Ollama model menu (`ParamControl.tsx`) |
| `Param.scope` ≠ runtime | yellow "re-index needed" badge |
| validation errors | red text under the control; Send is blocked |
| `file`, `class_name`, `base_class` | shown under the method, e.g. `blocks/retrieval/dense_retrieval/qdrant_cosine.py · QdrantDenseRetriever ← BaseDenseRetriever` |

React contains **no list** of blocks, methods or parameters. It only knows how to draw each `ui` type.

## Built-in safety checks

`check_registry()` runs every time the backend starts (and in the tests). It stops with
`TypeError: Registry error: …` if:

- two blocks or two methods share an ID,
- a method's class does not inherit from its block's abstract class,
- a class still has unimplemented abstract methods,
- a parameter's default is outside its own range,
- a required block has no implemented default method,
- a block's `base.py` is not at `app/rag/blocks/<group>/<stage_id>/base.py` with `<group>` listed in `GROUPS`.

## Debugging: "my method does not show up in the UI"

1. Is there a `Method(...)` entry inside the right `Stage(...)` in `registry.py`? A file in the block
   folder alone is not enough.
2. Did you add the `from app.rag.blocks.<group>.<block>.<file> import <Class>` line at the top of
   `registry.py`?
3. Did the backend restart cleanly? Look for `Registry error:` or `ImportError` in the uvicorn
   terminal.
4. Open <http://127.0.0.1:8000/api/pipeline/registry> and search for your `method_id`.
5. Reload the browser page (the registry is loaded when the page opens).
6. Greyed out? Then `implemented` is still `False`.
7. Selectable but Send is blocked? Read the red message; a combination rule may apply.
