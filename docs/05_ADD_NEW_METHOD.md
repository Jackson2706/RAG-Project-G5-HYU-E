# 05 · How to Add a New RAG Method

This tutorial walks you through implementing a real algorithm, **BM25 lexical retrieval**, from the
skeleton to a working, selectable method. You won't touch the pipeline runner, the API or the React
code. Then you get guides for the other future methods, including **Metadata Prefiltering** and
**Metadata Postfiltering**.

> **Before you start:** the app runs ([01_GETTING_STARTED.md](01_GETTING_STARTED.md)), `python -m pytest`
> passes in `backend/`, and you have read [03_ABSTRACT_CLASSES.md](03_ABSTRACT_CLASSES.md) and
> [04_METHOD_REGISTRY.md](04_METHOD_REGISTRY.md).

**The recipe for every method:**

| # | What | Where |
|---|---|---|
| 1 | Open the block folder and read `base.py` | `backend/app/rag/blocks/<group>/<block>/` |
| 2 | Create or complete the algorithm's file (a subclass) | same folder, one file per algorithm |
| 3 | Implement the abstract method | your class |
| 4 | Register it (start with `implemented=False`) | `backend/app/rag/registry.py` |
| 5 | Register its hyperparameters | `parameters={...}` of your `Method` |
| 6 | Write a test | `backend/tests/` |
| 7 | Mark it implemented | `registry.py` |
| 8–9 | Select it in the UI and inspect its real input and output | browser |

---

## Tutorial: implement BM25

**BM25** ranks chunks by shared words. Rare words count more (IDF), repeated words help with
diminishing returns (`k1`), and long chunks are penalized a little (`b`):

```text
score(q, d) = Σ over query words t:  IDF(t) · tf(t,d)·(k1+1) / (tf(t,d) + k1·(1 − b + b·|d|/avgdl))
IDF(t)      = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))
```

`tf(t,d)` = how often word t is in chunk d · `|d|` = chunk length in words · `avgdl` = average chunk
length · `N` = number of chunks · `df(t)` = chunks containing t.

### Step 1 — Open the folder and read `base.py`

```text
backend/app/rag/blocks/retrieval/lexical_retrieval/
├── __init__.py
├── base.py       BaseLexicalRetriever
└── bm25.py       BM25Retriever — currently a skeleton (raises NotImplementedError)
```

`base.py`:

```python
class BaseLexicalRetriever(PipelineBlock):
    """Find chunks that share *words* with the query. Same input and output as BaseDenseRetriever,
    including the rule that a prefilter predicate must be applied while searching."""

    @abstractmethod
    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult: ...
```

- **Inputs:** `query` (the search text) and `prefilter` (an eligibility predicate from Metadata
  Prefiltering, or `None`).
- **Output:** a `RetrievalResult` (`backend/app/rag/schemas.py`): `Candidate`s best first, plus
  the filter you applied. You return only IDs and scores. Metadata Enrichment loads the text later.

### Steps 2 and 3 — Complete the subclass and implement `retrieve`

Replace the whole content of `backend/app/rag/blocks/retrieval/lexical_retrieval/bm25.py` with:

```python
"""IMPLEMENTED — Okapi BM25 keyword ranking over all stored chunks."""

from __future__ import annotations

import math
import re
from collections import Counter

from app.rag.blocks.retrieval.lexical_retrieval.base import BaseLexicalRetriever
from app.rag.schemas import Candidate, RetrievalFilter, RetrievalResult

WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = {"a", "an", "and", "are", "at", "can", "do", "for", "how", "i", "in", "is", "my", "of", "on",
             "or", "the", "to", "what", "when", "where", "which", "who", "why", "with", "you"}


def words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


class BM25Retriever(BaseLexicalRetriever):
    """Hyperparameters: top_k, k1, b."""

    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult:
        if prefilter is not None:
            # Never ignore an eligibility predicate silently. Supporting it is a good next exercise.
            raise NotImplementedError("BM25Retriever does not support metadata prefiltering yet.")
        k1, b, top_k = self.params["k1"], self.params["b"], self.params["top_k"]
        chunks = list(self.services.db.chunks.find({}, {"_id": 0, "chunk_id": 1, "doc_id": 1, "text": 1}))
        if not chunks:
            return RetrievalResult(candidates=[])
        counts = [Counter(words(c["text"])) for c in chunks]          # tf for every chunk
        n = len(chunks)
        avgdl = sum(sum(tf.values()) for tf in counts) / n
        df = Counter(w for tf in counts for w in tf)                  # in how many chunks each word appears
        terms = set(words(query))
        scored = []
        for chunk, tf in zip(chunks, counts):
            length = sum(tf.values())
            score = 0.0
            for t in terms & tf.keys():
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / avgdl))
            if score > 0:                                             # no shared word → not a candidate
                scored.append((score, chunk))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))  # best first; ties in a fixed order
        candidates = [Candidate(rank=i + 1, chunk_id=c["chunk_id"], doc_id=c["doc_id"], score=round(s, 4))
                      for i, (s, c) in enumerate(scored[:top_k])]
        return RetrievalResult(candidates=candidates, applied_filter=prefilter,
                               details={"query_terms": sorted(terms), "chunks_scored": n})
```

What each part does:
- `self.services.db.chunks` is the MongoDB `chunks` collection (shared tools come from `self.services`).
- `self.params["k1"]` etc. are the hyperparameters registered in step 5. Never hard-code them.
- `details` is extra information that appears in the stage's Output in the Execution tab.
- Every score is computed from real data. Never return made-up candidates.
- Refusing a prefilter you can't apply is correct behaviour. Silently ignoring it would break the
  student's eligibility conditions.

### Steps 4 and 5 — Register the class and its hyperparameters

`registry.py` already imports `BM25Retriever` and has its entry, because the skeleton was
registered as planned:

```python
from app.rag.blocks.retrieval.lexical_retrieval.bm25 import BM25Retriever
...
Stage("lexical_retrieval", "Lexical Retrieval", "online", BaseLexicalRetriever,
      "Find chunks that share words with the question.", default_method=None, optional=True,
      methods=[
          Method("bm25", "BM25", BM25Retriever, False, "Classic keyword ranking.", parameters={
              "top_k": Param("integer", 5, "Top K", "How many chunks to retrieve.", min=1, max=20),
              "k1": Param("float", 1.5, "k1", "How fast repeated words stop adding score.", min=0, max=3, step=0.1),
              "b": Param("float", 0.75, "b", "How much long chunks are penalized.", min=0, max=1, step=0.05),
          }),
      ]),
```

For a **brand-new** algorithm you would add both parts yourself: an import line at the top, and a
`Method("my_id", "My name", MyClass, False, "…", parameters={...})` inside the right `Stage`. The
`method_id` must be unique in the whole registry.

Each `Param` becomes a UI control, and its value arrives in `self.params[...]`, already validated:

| Want | Write |
|---|---|
| a whole-number slider | `Param("integer", 5, "Top K", "…", min=1, max=20)` |
| a decimal slider | `Param("float", 1.5, "k1", "…", min=0, max=3, step=0.1)` |
| a toggle | `Param("boolean", True, "Include university-wide", "…", ui="toggle")` |
| a dropdown | `Param("enum", "SEOUL", "Campus", "…", ui="select", options=("SEOUL", "ERICA"))` |
| a text box | `Param("string", "", "Prefix", "…", ui="text")` |
| a setting that needs re-indexing | add `scope="ingestion"` |

### Step 6 — Add a test

Create `backend/tests/test_bm25.py`:

```python
import pytest

from app.rag.blocks.retrieval.lexical_retrieval.bm25 import BM25Retriever
from app.rag.schemas import RetrievalFilter

pytestmark = pytest.mark.anyio
PARAMS = {"top_k": 5, "k1": 1.5, "b": 0.75}


@pytest.fixture
def chunks(db):
    db.chunks.insert_many([
        {"chunk_id": "c1", "doc_id": "d1", "text": "International students need a TOPIK score report."},
        {"chunk_id": "c2", "doc_id": "d1", "text": "Submit the scholarship report before the deadline."},
        {"chunk_id": "c3", "doc_id": "d2", "text": "Dormitory rooms are assigned in February."},
    ])


async def test_rare_words_count_more(services, chunks):
    result = await BM25Retriever(PARAMS, services).retrieve("TOPIK score report")
    assert [c.chunk_id for c in result.candidates] == ["c1", "c2"]  # c1 has all three words; c2 only "report"; c3 none
    assert [c.rank for c in result.candidates] == [1, 2]
    assert result.candidates[0].score > result.candidates[1].score > 0
    assert result.details["query_terms"] == ["report", "score", "topik"]


async def test_top_k_is_respected(services, db):
    db.chunks.insert_many([{"chunk_id": f"c{i}", "doc_id": "d", "text": "dormitory"} for i in range(10)])
    result = await BM25Retriever({**PARAMS, "top_k": 3}, services).retrieve("dormitory")
    assert len(result.candidates) == 3


async def test_a_prefilter_is_never_silently_ignored(services, chunks):
    with pytest.raises(NotImplementedError, match="prefiltering"):
        await BM25Retriever(PARAMS, services).retrieve("TOPIK", RetrievalFilter(conditions={"campus": ["ERICA"]}))
```

The `services` and `db` fixtures (`backend/tests/conftest.py`) give you an in-memory MongoDB, so no
Docker is needed. Run, from `backend/`:

```bash
conda activate RAG
python -m pytest tests/test_bm25.py -v
```

✅ `3 passed`.

### Step 7 — Mark it implemented

In `registry.py`, change `False` to `True` in the BM25 `Method(...)`:

```python
Method("bm25", "BM25", BM25Retriever, True, "Classic keyword ranking.", parameters={
```

Run **all** tests: `python -m pytest`. One existing test will fail, on purpose:
`test_planned_stages_are_skipped_without_fake_output` in `backend/tests/test_pipeline.py` lists
`"lexical_retrieval"` as *not implemented*. It isn't anymore: its skip reason is now "Switched off in
the configuration." Remove `"lexical_retrieval"` from that test's list and run `python -m pytest`
again. ✅ Everything passes.

### Step 8 — Select it in the existing UI

Restart the backend (or let `--reload` do it), then **reload the browser page**. In
**Configuration → Candidate Retrieval**:

```text
BEFORE                                        AFTER
░ Lexical Retrieval   NOT IMPLEMENTED         ✓ Lexical Retrieval
  [BM25 — retrieval/lexical_retrieval/bm25.py]            Method: [BM25 ▾]
                                                Top K ──●── 5   k1 ──●── 1.5   b ──●── 0.75
```

Choose **BM25**. You'll see a red message: *"Two retrievers are on: choose a Hybrid Fusion method to
merge them"*. Fusion is not implemented yet, so set **Dense Retrieval → Off — skip this stage** to
try BM25 alone.

### Step 9 — Inspect the real execution

Ask *What do international students need for the scholarship?* and open **Execution**:

```text
CANDIDATE RETRIEVAL
░ Dense Retrieval        skipped — Switched off in the configuration.
✓ Lexical Retrieval · BM25                         4 ms
    Input:      {"query": "What do international students need for the scholarship?", "prefilter": null}
    Output:     candidate cards with BM25 scores + {"details": {"query_terms": [...], "chunks_scored": 23}}
    Parameters: {"top_k": 5, "k1": 1.5, "b": 0.75}
✓ Metadata Enrichment · MongoDB lookup             loads the text of YOUR candidates
✓ … Evidence Selection, Context Construction, Generation …
```

Check that `query_terms` are the words you expect, that Metadata Enrichment received exactly your
chunk IDs, and that the answer's sources are chunks BM25 found. Then compare with Dense Retrieval
on a few questions from `data/eval/sample_questions.jsonl`. That comparison is retrieval evaluation.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: Can't instantiate abstract class BM25Retriever without an implementation for abstract method 'retrieve'` | method missing or misspelled | name it exactly `retrieve`, with `async def` |
| `TypeError: Registry error: … must inherit from BaseLexicalRetriever` | wrong parent class, or registered in the wrong `Stage` | inherit from the class in the same folder's `base.py` |
| `TypeError: Registry error: duplicate method id …` | ID already used | choose a unique `method_id` |
| `ImportError: cannot import name …` | file/class name mismatch | check the file name and the import line in `registry.py` |
| `TypeError: … unexpected keyword argument` / `missing … argument` | signature differs from `base.py` | copy the signature exactly |
| `KeyError: 'k1'` | hyperparameter not registered | add it to `parameters={...}` |
| `TypeError: BaseModel.__init__() takes 1 positional argument …` | `Candidate(...)` without keywords | `Candidate(rank=..., chunk_id=..., doc_id=..., score=...)` |
| `ValidationError: … Field required` | a schema field is missing | give every field `schemas.py` lists |
| Metadata Enrichment fails: "missing in MongoDB" | invalid result: fake or wrong chunk IDs | return real `chunk_id`s from the database |
| method greyed out | `implemented=False` | step 7 |
| method missing in the UI | not registered, backend not restarted, page not reloaded | [04_METHOD_REGISTRY.md › Debugging](04_METHOD_REGISTRY.md#debugging-my-method-does-not-show-up-in-the-ui) |
| Send blocked with a red message | a combination rule | read it (e.g. switch Dense Retrieval off) |
| `RuntimeWarning: coroutine … was never awaited` | `def` instead of `async def` | online methods are `async def` |

---

## Guides for the other future methods

Each of these already has a folder, an abstract class, a skeleton file with TODO steps, and a
registry entry with `implemented=False`. Use the same steps 1–9: replace the
`raise NotImplementedError(...)` with real code, write tests, set `implemented=True`, remove the
block from the "planned stages" test list, select it, and inspect it.

### Query Rewriting

| | |
|---|---|
| Folder | `blocks/query_processing/query_rewriting/` → `llm_rewriter.py` (or `multi_query.py`) |
| Inherit | `BaseQueryRewriter` |
| Implement | `async def rewrite(self, question: str) -> RewrittenQuery` |
| Input → output | the question → `RewrittenQuery(query=..., alternatives=[...])` |
| Where it runs | before prefiltering and retrieval. Retrieval uses `query`; the prompt still uses the original question |
| Reuse | `self.services.ollama.pick_model(...)` and `chat_stream(...)` (`app/ollama.py`); collect the pieces into one string |
| Registry | `Method("llm_rewrite", …)`; its `temperature` parameter is already registered |
| Test | use the `ollama` + `fake_ollama` fixtures: set `fake_ollama.answer`, check `query`; an empty answer falls back to the question |
| Inspect | Query Rewriting's output, then Dense Retrieval's `input.query` must be the rewritten text |

### Metadata Prefiltering

| | |
|---|---|
| Folder | `blocks/metadata_filtering/metadata_prefiltering/` → `qdrant_prefilter.py` |
| Inherit | `BaseMetadataPrefilter` |
| Implement | `async def build_filter(self, criteria: FilterCriteria) -> RetrievalFilter \| None` |
| Input → output | validated `FilterCriteria` (campus, audience, academic year, document type, effective date) → a **predicate** `RetrievalFilter(conditions={field: allowed values}, include_unknown=...)`, or `None` when there are no conditions |
| Where it runs | before candidate retrieval. The runner passes your predicate **into** `retrieve(query, prefilter)`, and `QdrantDenseRetriever` already turns it into a Qdrant `query_filter` (`to_qdrant_filter` in `retrieval/dense_retrieval/qdrant_cosine.py`) |

How to build the predicate, step by step:
1. **Make the field searchable.** The Qdrant payload today is `{chunk_id, doc_id}`. In
   `ingestion/vector_indexing/qdrant_indexer.py` / `Database.replace_index()`, add the document's metadata to
   each point (e.g. `campus` from front matter, `documents.metadata.campus`). Then **re-index**.
2. **Get criteria.** They come from Query Understanding (`analysis.criteria`). Implement that block
   first, or for an experiment, read a fixed value from a `Param` of your prefilter. Never invent
   user attributes.
3. **Allow university-wide documents:**
   `RetrievalFilter(conditions={"campus": [criteria.campus, "ALL"]}, include_unknown=True)`.
   `include_unknown=True` keeps chunks whose campus is missing (unknown ≠ ineligible).
4. **Do not** call the retriever yourself, and do not filter a result list. That would be
   postfiltering.

Test ideas: with a predicate on one document, Dense Retrieval still returns `top_k` candidates, all
eligible (see `test_prefiltering_is_a_predicate_applied_inside_retrieval` in
`backend/tests/test_pipeline.py`). Also test empty criteria → `None`, and unknown metadata.
Inspect: Prefiltering's output (the predicate), then Dense Retrieval's `input.prefilter` and
`output.applied_filter` must show the same predicate.

### Metadata Postfiltering

| | |
|---|---|
| Folder | `blocks/metadata_filtering/metadata_postfiltering/` → `candidate_postfilter.py` |
| Inherit | `BaseMetadataPostfilter` |
| Implement | `async def filter_candidates(self, candidates: list[Candidate], criteria: FilterCriteria) -> PostfilterResult` |
| Input → output | the **already retrieved** candidates + criteria → `PostfilterResult(kept=[...], removed=[RemovedCandidate(chunk_id=..., reason=...)])` |
| Where it runs | after candidate retrieval, before metadata enrichment and reranking. It never searches the collection |
| Reuse | `self.services.db.get_documents([c.doc_id for c in candidates])` → each document's `metadata` |

Rules:
- Keep the original order and ranks of the survivors.
- Give a human-readable `reason` for every removed candidate (it is shown in the trace).
- If nothing survives, return an empty `kept` list, and the pipeline abstains. **Never relax the
  conditions** to fill the list.

**Candidate starvation (synthetic example):** an ERICA student asks *"Can I borrow a laptop?"*. With
Top K = 5, all five candidates are Seoul library rules, and the ERICA rule is ranked 7th.
Postfiltering removes all five, so the student gets no answer although the right document exists.
Write this as a test: index 6 "Seoul" chunks and 1 less similar "ERICA" chunk, retrieve with
`top_k=5`, postfilter for ERICA, and assert `kept == []`. Then compare with your prefilter, which
finds the ERICA chunk. Report this difference. It is exactly the Prefiltering vs Postfiltering
lesson.

Inspect: Postfiltering's input candidate IDs, `removed` (IDs and reasons) and `kept`. Metadata
Enrichment must then receive only the `kept` IDs.

### Hybrid Retrieval (Fusion)

| | |
|---|---|
| Folder | `blocks/retrieval/hybrid_fusion/` → `rrf.py` |
| Inherit | `BaseHybridFusion` |
| Implement | `async def fuse(self, dense: RetrievalResult, lexical: RetrievalResult) -> RetrievalResult` |
| Algorithm | for every `chunk_id`: `score = Σ 1/(rrf_k + rank)` over the lists it appears in; sort; keep `top_k`; renumber `rank` from 1 |
| Where it runs | after both retrievers, only when dense, lexical *and* fusion are on (the validator enforces this) |
| Prefilter | both inputs were searched with the same predicate. Keep `applied_filter=dense.applied_filter`, and make sure your lexical retriever supports prefiltering before combining them with a prefilter |
| Test | a chunk ranked 2nd in both lists beats a chunk ranked 1st in only one list |

### Cross-Encoder Reranking

| | |
|---|---|
| Folder | `blocks/evidence/reranking/` → `cross_encoder.py` |
| Inherit | `BaseReranker` |
| Implement | `async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]` |
| Input → output | the query + `Evidence` (with text) → the same evidence, reordered, `rank` renumbered (`e.model_copy(update={"rank": i})`), at most `top_n` |
| Algorithm | `sentence_transformers.CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2").predict([(query, e.text) for e in evidence])`. The model downloads ~90 MB once; load it in a cached function, like `load_sentence_transformer` in `ingestion/embedding/bge_embedder.py` |
| Where it runs | after metadata enrichment, before evidence selection |
| Test | monkeypatch your model loader with a fake whose `predict()` returns fixed scores; check the new order |

### Evidence Sufficiency

| | |
|---|---|
| Folder | `blocks/evidence/evidence_sufficiency/` → `sufficiency_checker.py` |
| Inherit | `BaseSufficiencyChecker` |
| Implement | `async def check(self, question: str, evidence: list[Evidence]) -> SufficiencyDecision` |
| Input → output | the question + selected evidence → `SufficiencyDecision(sufficient=..., reason=...)` |
| Where it runs | after evidence selection. If `sufficient=False`, the runner skips Context Construction and Generation and **abstains**. That logic already exists in `run_rag()` |
| Choosing `min_score` | measure, don't guess: `data/eval/sample_questions.jsonl` has 14 labelled questions (12 answerable, 2 not). Print the best score for each and pick a value that separates them. Report that it was tuned on that small set |
| Test | evidence with scores `[0.2, 0.1]` and `min_score=0.5` → `sufficient=False`; in a pipeline test the LLM is not called (`fake_ollama.requests == []`) |

---

## Beginner checklist

- [ ] I opened the block folder, read `base.py`, and copied the method name and signature exactly.
- [ ] My class lives in its own file in that folder, inherits from the base class, reads settings
      from `self.params` and tools from `self.services`.
- [ ] It returns the promised type (`RetrievalResult`, `PostfilterResult`, …), built from real data with keywords.
- [ ] It never silently ignores eligibility conditions (prefilter predicates, postfilter criteria).
- [ ] It is registered with a unique `method_id` and its `Param`s, starting at `implemented=False`.
- [ ] My test passes: `python -m pytest tests/test_<mine>.py`.
- [ ] I set `implemented=True`, updated the planned-stages test, and the whole suite passes.
- [ ] I restarted the backend, reloaded the page, selected my method, and inspected its real input and output.
- [ ] I compared it with the existing method on real questions and wrote down what changed.
