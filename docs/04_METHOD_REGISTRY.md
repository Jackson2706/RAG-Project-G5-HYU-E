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
              "top_k": Param("integer", 5, "Top K", "How many of the most similar chunks to retrieve.", min=1, max=20),
          }),
      ]),
```

A planned block, Metadata Prefiltering:

```python
Stage("metadata_prefiltering", "Metadata Prefiltering", "online", BaseMetadataPrefilter,
      "Restrict candidate retrieval to eligible documents: the predicate is applied DURING the search.",
      default_method=None, optional=True, methods=[
          Method("qdrant_prefilter", "Qdrant payload filter", QdrantMetadataPrefilter, False, "Eligibility predicate on Qdrant payload fields."),
      ]),
```

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
| `index` | changes the stored vectors | (none yet; e.g. another embedding model) | needs a fresh index |

Non-runtime parameters get a yellow **re-index needed** badge. The Configuration tab also warns when
your chunk settings differ from how the current index was built (`index_info()` in `database.py`).
Stored vectors are never changed silently.

The working hyperparameters today:

| Block | Method | Parameter | Default | Range | Scope |
|---|---|---|---|---|---|
| Chunking | `section_tokens` | `chunk_size` | 256 | 64–512 tokens | ingestion |
| Chunking | `section_tokens` | `chunk_overlap` | 32 | 0–128 tokens | ingestion |
| Dense Retrieval | `qdrant_cosine` | `top_k` | 5 | 1–20 | runtime |
| Evidence Selection | `token_budget` | `max_evidence_tokens` | 2000 | 200–8000 | runtime |
| Generation | `ollama_chat` | `model` | "" (default model) | installed models | runtime |
| Generation | `ollama_chat` | `temperature` | 0.2 | 0–2 | runtime |
| Generation | `ollama_chat` | `max_tokens` | 1024 | 64–4096 | runtime |

Planned methods declare their expected parameters (e.g. BM25's `k1` and `b`) so you can see the
extension point. Their controls stay hidden until the method is implemented.

**Metadata criteria are not UI settings today.** The `FilterCriteria` schema (campus, audience,
academic year, document type, effective date) is filled by Query Understanding from what the
question states. If your prefilter or postfilter needs its own controls (e.g. "include
university-wide documents"), register them as `Param`s of that method. They appear only once it is
implemented.

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
  Hybrid Fusion method; fusion needs both retrievers.

```json
{"valid": false, "errors": [{"stage_id": "dense_retrieval", "param": "top_k", "message": "Top K must be at most 20"}]}
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
