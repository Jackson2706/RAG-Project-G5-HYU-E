# 05 · How to Add a New RAG Method

This tutorial walks you through adding a real algorithm — **diverse evidence selection** — from an
empty file to a working method that is selectable in the UI **and** measured by the benchmark. You
won't touch the pipeline runner, the API or the React code. At the end you find guides for the
methods that are still skeletons, and pointers to the implemented baselines you can learn from.

> **Before you start:** the app runs ([01_GETTING_STARTED.md](01_GETTING_STARTED.md)), `python -m pytest`
> passes in `Sources/backend/`, and you have read [03_ABSTRACT_CLASSES.md](03_ABSTRACT_CLASSES.md) and
> [04_METHOD_REGISTRY.md](04_METHOD_REGISTRY.md).

**The recipe for every method:**

| # | What | Where |
|---|---|---|
| 1 | Open the block folder and read `base.py` | `Sources/backend/app/rag/blocks/<group>/<block>/` |
| 2 | Create the algorithm's file (a subclass) | same folder, one file per algorithm |
| 3 | Implement the abstract method | your class |
| 4 | Register it (start with `implemented=False`) with its hyperparameters | `Sources/backend/app/rag/registry.py` |
| 5 | Write a test | `Sources/backend/tests/` |
| 6 | Mark it implemented | `registry.py` |
| 7–8 | Select it in the UI and inspect its real input and output | browser |
| 9 | Measure it against B0 | a preset + `python -m evaluation.runner` |

---

## Tutorial: diverse evidence selection

**The problem.** Top-K evidence selection (B0) sends the 3 best chunks to the model. Often two of
them come from the **same document** (neighbouring windows of one long section), so the model sees
less variety than it could. The benchmark measures this as `duplicate_doc_rate_in_selection`.

**The method.** Walk the ranked evidence from the top and keep a chunk only if its document has
fewer than `max_per_document` chunks selected so far; stop at `top_k` chunks.

```text
ranked:   c1 (doc A)  c2 (doc A)  c3 (doc B)  c4 (doc A)  c5 (doc C)
Top-3:    c1 c2 c3                       → 2 documents
diverse:  c1 c3 c5   (max 1 per document) → 3 documents
```

### Step 1 — Open the folder and read `base.py`

`Sources/backend/app/rag/blocks/evidence/evidence_selection/base.py`:

```python
class BaseEvidenceSelector(PipelineBlock):
    """Input: Evidence list (best first). Output: the Evidence to put in the prompt."""

    @abstractmethod
    async def select(self, evidence: list[Evidence]) -> list[Evidence]: ...
```

So your class needs exactly one method: `async def select(self, evidence)`, returning a list of
`Evidence` (from `app/rag/schemas.py`; each has `doc_id`, `chunk_id`, `text`, `rank`, `score`, …).
The two existing selectors in the same folder (`top_k_selector.py`, `token_budget_selector.py`) are
short examples.

### Steps 2 and 3 — Create the subclass and implement `select`

Create `Sources/backend/app/rag/blocks/evidence/evidence_selection/diverse_selector.py`:

```python
"""IMPLEMENTED — keep the best evidence, but at most N chunks per document."""

from __future__ import annotations

from collections import Counter

from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.schemas import Evidence


class DiverseDocumentSelector(BaseEvidenceSelector):
    """Hyperparameters: top_k (chunks in the prompt), max_per_document.

    Walks the evidence in rank order and skips a chunk when its document already has
    `max_per_document` selected chunks, so the prompt covers more different documents.
    """

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        per_document: Counter[str] = Counter()
        selected = []
        for item in evidence:
            if len(selected) == self.params["top_k"]:
                break
            if per_document[item.doc_id] < self.params["max_per_document"]:
                selected.append(item)
                per_document[item.doc_id] += 1
        return selected
```

Habits from [03_ABSTRACT_CLASSES.md](03_ABSTRACT_CLASSES.md): settings come from `self.params`, the
input order is kept (rank order), and the output is real `Evidence` objects — never invented ones.

### Step 4 — Register the class and its hyperparameters

In `Sources/backend/app/rag/registry.py`, add the import next to the other evidence-selection imports:

```python
from app.rag.blocks.evidence.evidence_selection.diverse_selector import DiverseDocumentSelector
```

and add a `Method` to the `evidence_selection` stage, **after** the existing two (start with `False`):

```python
              Method("diverse_documents", "Diverse documents", DiverseDocumentSelector, False,
                     "Best chunks, at most N per document.", parameters={
                  "top_k": Param("integer", 3, "Top K evidence", "How many chunks go into the prompt.", min=1, max=20),
                  "max_per_document": Param("integer", 1, "Max chunks per document",
                                            "A document contributes at most this many chunks.", min=1, max=5),
              }),
```

Restart the backend: `check_registry()` runs at startup and stops with `TypeError: Registry error: …`
if the class does not inherit from `BaseEvidenceSelector`, the `method_id` is already used, or a
default is outside its range.

### Step 5 — Add a test

Create `Sources/backend/tests/test_diverse_selector.py`:

```python
import pytest

from app.rag.blocks.evidence.evidence_selection.diverse_selector import DiverseDocumentSelector
from app.rag.schemas import Evidence

pytestmark = pytest.mark.anyio


def evidence(doc_ids: list[str]) -> list[Evidence]:
    return [Evidence(rank=i + 1, chunk_id=f"c{i + 1}", doc_id=d, score=1 - i / 10, text="t", title="T", source_uri="x")
            for i, d in enumerate(doc_ids)]


async def test_one_chunk_per_document(services):
    out = await DiverseDocumentSelector({"top_k": 3, "max_per_document": 1}, services).select(evidence(["A", "A", "B", "A", "C"]))
    assert [e.chunk_id for e in out] == ["c1", "c3", "c5"]


async def test_two_per_document_and_top_k(services):
    out = await DiverseDocumentSelector({"top_k": 3, "max_per_document": 2}, services).select(evidence(["A", "A", "A", "B"]))
    assert [e.chunk_id for e in out] == ["c1", "c2", "c4"]


async def test_fewer_documents_than_top_k_and_empty_input(services):
    selector = DiverseDocumentSelector({"top_k": 3, "max_per_document": 1}, services)
    assert [e.chunk_id for e in await selector.select(evidence(["A", "A"]))] == ["c1"]
    assert await selector.select([]) == []
```

The `services` fixture (`Sources/backend/tests/conftest.py`) uses an in-memory MongoDB and a fake embedding
model, so no Docker is needed. Run, from `Sources/backend/`:

```bash
conda activate RAG
python -m pytest tests/test_diverse_selector.py -v
```

✅ `3 passed`.

### Step 6 — Mark it implemented

In `registry.py`, change `False` to `True` in your `Method("diverse_documents", …)`. Run **all**
tests: `python -m pytest`. ✅ Everything passes (the registry tests check that every implemented
method inherits correctly and has valid defaults).

### Step 7 — Select it in the existing UI

Let `--reload` restart the backend, then **reload the browser page**. In
**Configuration → Evidence → Evidence Selection**, the method menu now lists **Diverse documents**
with two sliders (Top K evidence, Max chunks per document). Choose it. Nothing else in the UI changed:
it is drawn from `GET /api/pipeline/registry`.

### Step 8 — Inspect the real execution

Ask *What do international students need for the scholarship?* and open **Execution → Evidence
Selection**: the *Input* tab shows the ranked evidence it received, *Output* the chunks it kept,
*Parameters* `{"top_k": 3, "max_per_document": 1}`. Check that no two kept chunks share a `doc_id`.
Then switch back to *Top-K (baseline)* and ask again: the answer's sources show the difference.

### Step 9 — Measure it

Give it a preset in `Sources/backend/app/rag/presets.py` (in the online section):

```python
    {"id": "R15_DIVERSE_SELECTION", "kind": "online", "name": "R15 — Diverse evidence selection",
     "description": "Top 3 evidence, at most one chunk per document.",
     "stages": {"evidence_selection": {"method": "diverse_documents", "params": {"top_k": 3, "max_per_document": 1}}}},
```

and one line in `Sources/evaluation/configs/online.yaml` under `experiments:`:

```yaml
  - {id: R15_DIVERSE_SELECTION, preset: R15_DIVERSE_SELECTION, protocols: [B]}
```

Run it from `Sources/` (the SciFact O0 index is reused if it exists, otherwise built first):

```bash
python -m evaluation.runner --suite retrieval --dataset scifact --experiment B0_BASIC_DENSE_RAG,R15_DIVERSE_SELECTION --run-id tutorial
```

Open `Report/results/tutorial/retrieval_comparison.csv` and compare the two rows: the ranking
metrics (nDCG@10, Recall@100) are **identical** — evidence selection does not change the ranking —
while `duplicate_doc_rate_in_selection` and `selected_doc_recall` show what your method changes.
That separation (ranking vs selection) is exactly why the report keeps them in different columns.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: Can't instantiate abstract class DiverseDocumentSelector without an implementation for abstract method 'select'` | method missing or misspelled | name it exactly `select`, with `async def` |
| `TypeError: Registry error: … must inherit from BaseEvidenceSelector` | wrong parent class, or registered in the wrong `Stage` | inherit from the class in the same folder's `base.py` |
| `TypeError: Registry error: duplicate method id …` | ID already used | choose a unique `method_id` |
| `ImportError: cannot import name …` | file/class name mismatch | check the file name and the import line in `registry.py` |
| `KeyError: 'max_per_document'` | hyperparameter not registered (or misspelled) | add it to `parameters={...}` |
| `ValidationError: … Field required` | a schema field is missing | give every field `schemas.py` lists |
| method greyed out | `implemented=False` | step 6 |
| method missing in the UI | not registered, backend not restarted, page not reloaded | [04_METHOD_REGISTRY.md › Debugging](04_METHOD_REGISTRY.md#debugging-my-method-does-not-show-up-in-the-ui) |
| `KeyError: 'R15_DIVERSE_SELECTION'` from the runner | preset not added to `presets.py` | step 9 |
| `RuntimeWarning: coroutine … was never awaited` | `def` instead of `async def` | online methods are `async def` |

---

## Learn from the implemented baselines

Every method below is a complete, tested example of the recipe (tests: `Sources/backend/tests/test_methods.py`).

| You want to… | Read |
|---|---|
| build a retriever with an index of your own | `retrieval/lexical_retrieval/bm25.py` (inverted index, cache per index revision, prefilter inside ranking) |
| merge rankings | `retrieval/hybrid_fusion/rrf.py` (`reciprocal_rank_fusion()` is reused by multi-query) |
| call a local LLM and **check** its output | `query_processing/query_rewriting/llm_rewriter.py` + `validate_rewrite()` in its `base.py`; `evidence/reranking/rankgpt.py` (permutation validation, retry, repair/fallback) |
| use a second model | `evidence/reranking/cross_encoder.py` (pinned revision, cached load, device) |
| change only the search vector | `query_processing/query_rewriting/hyde.py` + `embedding_text` in dense retrieval |
| filter by metadata | `metadata_filtering/…/qdrant_prefilter.py` and `candidate_postfilter.py` (one predicate: `FilterCriteria.to_filter()`) |
| decide to abstain | `evidence/evidence_sufficiency/sufficiency_checker.py` |
| chunk with source spans | `ingestion/chunking/fixed_chunker.py`, `recursive_chunker.py` |

## Guides for the methods that are still skeletons

Each has a folder, an abstract class, a skeleton with TODO steps and a registry entry with
`implemented=False`. Use steps 1–9.

### Semantic chunking (`ingestion/chunking/semantic_chunker.py`)

| Item | Guide |
|---|---|
| Idea | split each section into sentences; embed them (`self.services.embedder.embed_documents`); start a new chunk where neighbouring sentences are not similar |
| Parameters | `similarity_threshold` (e.g. 0.6), `max_tokens` (`scope="ingestion"`) |
| Must keep | real token counts and source spans (`start`, `end`) like the other chunkers — the manifest reports invalid spans |
| Measure | add an O-preset (copy O5) and a line in `Sources/evaluation/configs/offline.yaml` |

### LLM query understanding (`query_processing/query_understanding/llm_understanding.py`)

| Item | Guide |
|---|---|
| Idea | ask the LLM for the criteria the question **states** (campus, audience, year, type) as JSON |
| Must keep | never invent attributes the user did not state; validate the JSON into `FilterCriteria`; on invalid output return empty criteria (and say so in `self.trace_details`) |
| Measure | the HYU metadata fixture: compare with *Stated criteria* (R9/R10) |

### Metadata-aware reranking (`evidence/reranking/metadata_reranker.py`)

| Item | Guide |
|---|---|
| Idea | among equally relevant chunks, prefer documents matching the stated criteria (soft preference, unlike filtering) |
| Must keep | use `self.reordered(head, tail, …)` from `BaseReranker` so ranks and the untouched tail stay correct |

### LLM metadata extraction, Ollama embeddings, website loader

`metadata_extraction/llm_extractor.py`, `embedding/ollama_embedder.py`, `document_loading/web_loader.py`:
offline methods — they need re-indexing (`scope="ingestion"` or `"index"` parameters), and an Ollama
embedding index is a new index revision (its `contract()` must name the model and dimension).

---

## Beginner checklist

- [ ] I opened the block folder, read `base.py`, and copied the method name and signature exactly.
- [ ] My class lives in its own file in that folder, inherits from the base class, reads settings
      from `self.params` and tools from `self.services`.
- [ ] It returns the promised type, built from real data with keywords.
- [ ] It never silently ignores eligibility conditions, and an LLM output is checked before it is used.
- [ ] It is registered with a unique `method_id` and its `Param`s, starting at `implemented=False`.
- [ ] My test passes: `python -m pytest tests/test_<mine>.py`.
- [ ] I set `implemented=True` and the whole suite passes.
- [ ] I restarted the backend, reloaded the page, selected my method, and inspected its real input and output.
- [ ] I measured it against B0 with the benchmark runner and wrote down what changed (and what it costs).
