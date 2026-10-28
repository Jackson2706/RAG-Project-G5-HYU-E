# 04 · The Method Registry

`backend/app/rag/registry.py` is the **single list** of every pipeline block, every method for
each block, and every hyperparameter. Nothing else in the project keeps such a list. The API, the
UI and the pipeline runner all read it.

## Why a registry?

Without one, adding a method would mean editing the runner, the API and the React code. With the
registry, you add **one entry**, and then:

- FastAPI sends it to the browser (`GET /api/pipeline/registry`),
- the UI draws the method in the dropdown and its hyperparameters as controls,
- FastAPI validates the values users choose,
- the runner creates your class and calls it.

```mermaid
flowchart LR
  REG["registry.py<br/>PIPELINE = [Stage(...), ...]"] -->|registry_json()| API1["GET /api/pipeline/registry"]
  API1 --> HOOK["usePipelineConfig.ts<br/>loads stages + defaults"]
  HOOK --> UI["Configuration tab<br/>StageConfigCard · ParamControl · DisabledStage"]
  UI -->|"every change"| VAL["POST /api/pipeline/config/validate<br/>validate_config()"]
  VAL -->|"errors per stage/param"| UI
  UI -->|"question + stages"| CHAT["POST /api/chat/stream<br/>validate_config()"]
  CHAT --> RUN["run_rag() in pipeline.py"]
  RUN -->|"create_block(stage, method, params)"| REG
  RUN -->|"block.retrieve(...) etc."| BLK["your subclass"]
```

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
class Method:           # one algorithm
    method_id: str       # unique ID, used in configs and traces
    name: str            # shown in the dropdown
    cls: type            # the Python class (a subclass of the stage's abstract class)
    implemented: bool    # False = shown greyed out, cannot run
    description: str
    parameters: dict[str, Param]

@dataclass(frozen=True)
class Stage:            # one pipeline block
    stage_id: str
    name: str
    phase: "offline" | "online"
    base_class: type     # the abstract class every method must inherit from
    description: str
    methods: list[Method]
    default_method: str | None   # None = off by default (optional stages only)
    optional: bool = False       # optional stages can be switched off (then they are skipped)
```

A real entry, the dense retrieval block:

```python
Stage("dense_retrieval", "Dense Retrieval", "online", BaseDenseRetriever,
      "Find the chunks whose meaning is closest to the question.", default_method="qdrant_cosine", optional=True, methods=[
          Method("qdrant_cosine", "Qdrant cosine", QdrantDenseRetriever, True, "Embed the question and find the nearest chunk vectors.", parameters={
              "top_k": Param("integer", 5, "Top K", "How many of the most similar chunks to retrieve.", min=1, max=20),
          }),
      ]),
```

A planned block:

```python
Stage("reranking", "Reranking", "online", BaseReranker,
      "Put the most relevant evidence first.", default_method=None, optional=True, methods=[
          Method("cross_encoder", "Cross-encoder", CrossEncoderReranker, False, "Scores question and chunk together.",
                 parameters={"top_n": Param("integer", 5, "Keep top N", "Evidence kept after reranking.", min=1, max=20)}),
          Method("metadata_aware", "Metadata-aware", MetadataAwareReranker, False, "Prefer chunks matching the student's situation."),
      ]),
```

The order of `PIPELINE` is the order the UI shows (offline blocks first, then online). The
runner's order is written out in `run_rag()`.

## Hyperparameters and their scope

| scope | means | example | when it takes effect |
|---|---|---|---|
| `runtime` | used while answering | Top K, temperature | the next question |
| `ingestion` | used while indexing | chunk size, chunk overlap | only after **re-indexing** |
| `index` | changes the stored vectors | (none yet; e.g. a different embedding model) | needs a fresh index |

Non-runtime parameters get a yellow **re-index needed** badge in the UI. The Configuration tab
also warns when your chunk settings differ from the current index, which records how it was built
(`index_info()` in `database.py`). Changing them never silently changes stored vectors: you choose
when to re-index.

The working hyperparameters today:

| Block | Method | Parameter | Default | Range | Scope |
|---|---|---|---|---|---|
| Chunking | `section_tokens` | `chunk_size` | 256 | 64–512 tokens | ingestion |
| Chunking | `section_tokens` | `chunk_overlap` | 32 | 0–128 tokens | ingestion |
| Dense Retrieval | `qdrant_cosine` | `top_k` | 5 | 1–20 | runtime |
| Evidence Selection | `token_budget` | `max_evidence_tokens` | 2000 | 200–8000 | runtime |
| LLM Generation | `ollama_chat` | `model` | "" (default model) | installed models | runtime |
| LLM Generation | `ollama_chat` | `temperature` | 0.2 | 0–2 | runtime |
| LLM Generation | `ollama_chat` | `max_tokens` | 1024 | 64–4096 | runtime |

Planned methods also declare their expected parameters (e.g. BM25's `k1`, `b`), so you can see the
extension point, but they can't be selected until the method is implemented.

## The configuration a request carries

The frontend sends the chosen method and parameters per stage. A partial config is fine:
missing stages use their defaults.

```json
{
  "question": "How do I register for courses?",
  "stages": {
    "dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 4}},
    "generation": {"method": "ollama_chat", "params": {"model": "qwen3:4b", "temperature": 0.1, "max_tokens": 2048}},
    "reranking": {"method": null, "params": {}}
  }
}
```

`"method": null` switches an optional stage off.

`validate_config(stages)` returns the **complete** configuration (every stage, all defaults filled
in) or raises `ConfigError` with a list of problems. It is checked once, before anything runs,
and the result is stored in the trace, so every trace records exactly which methods and values
were used. Changing the UI later never changes a running or finished request.

What is checked:
- the stage and method exist; the method is **implemented** (planned methods are refused);
- required stages have a method (only optional stages may be off);
- every parameter exists, has the right type and is within `min`/`max` (or in `options`);
- combinations: `chunk_overlap < chunk_size`; at least one retriever is on; two retrievers need a
  Hybrid Fusion method; fusion needs both retrievers.

Errors look like this (from `POST /api/pipeline/config/validate`):

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
dense = await step("dense_retrieval", lambda b: b.retrieve(query, filters), {"query": query, "filters": filters})
```

- `create_block()` looks up the method's class and creates it with its validated parameters. It
  **refuses** methods with `implemented=False`.
- `step()` runs the block through its abstract method and records it in the trace. If the stage
  has no selected method, it records **skipped** ("Not implemented yet." or "Switched off in the
  configuration.") and returns a default, e.g. the original question for query rewriting. Skipped
  is never reported as completed.

## How React renders it

| Registry information | UI result (file) |
|---|---|
| stage has no implemented method | darkened block, "Not implemented", disabled method list (`DisabledStage.tsx`) |
| stage has an implemented method | normal card with a method dropdown (`StageConfigCard.tsx`) |
| `optional: true` | dropdown has "Off — skip this stage" |
| method `implemented: false` | option shown but disabled, "— not implemented" |
| `Param.ui` | slider / number / toggle / select / text / Ollama model menu (`ParamControl.tsx`) |
| `Param.scope` ≠ runtime | yellow "re-index needed" badge |
| validation errors | red text under the control; Send is blocked |

React contains **no list** of stages, methods or parameters. It only knows how to draw each `ui`
type.

## Built-in safety checks

`check_registry()` runs every time the backend starts (and in the tests). It stops with a clear
`TypeError: Registry error: …` if:

- two stages or two methods share an ID,
- a method's class does not inherit from its stage's abstract class,
- a class still has unimplemented abstract methods,
- a parameter's default is outside its own range,
- a required stage has no implemented default method.

## Debugging: "my method does not show up in the UI"

1. Is there a `Method(...)` entry inside the right `Stage(...)` in `registry.py`? (A class in
   `blocks/` alone is not enough.)
2. Did the backend restart cleanly? Look for `Registry error:` or an `ImportError` in the
   terminal running uvicorn. Did you add your class to the `from app.rag.blocks... import` lines
   at the top of `registry.py`?
3. Open <http://127.0.0.1:8000/api/pipeline/registry> and search for your `method_id`.
4. Reload the browser page (the registry is loaded once, when the page opens).
5. Greyed out? Then `implemented` is still `False`.
6. Selectable but the Send button is blocked? Read the red message: a combination rule may apply
   (e.g. two retrievers without fusion).
