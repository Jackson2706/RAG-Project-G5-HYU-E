# 05 · How to Add a New RAG Method

This tutorial walks you through adding a **new retrieval method** from start to finish. You won't
touch the pipeline runner, the API or the React code: you write one class, register it, test it,
and the app picks it up.

> **Before you start:** the app runs ([01_GETTING_STARTED.md](01_GETTING_STARTED.md)),
> `python -m pytest` passes in `backend/`, and you have read
> [03_ABSTRACT_CLASSES.md](03_ABSTRACT_CLASSES.md) and [04_METHOD_REGISTRY.md](04_METHOD_REGISTRY.md).

**The recipe for every method:**

| # | What | Where |
|---|---|---|
| 1 | Find the block's abstract class | `backend/app/rag/blocks/…` |
| 2 | Create a subclass | same file (or a new file in `blocks/`) |
| 3 | Implement its abstract method | your class |
| 4 | Register it with `implemented=False` | `backend/app/rag/registry.py` |
| 5 | Register its hyperparameters | the `parameters={...}` of your `Method` |
| 6 | Write a test | `backend/tests/` |
| 7 | Set `implemented=True` | `registry.py` |
| 8–9 | Run it and inspect it | browser: Configuration and Execution tabs |

## The example: a keyword-overlap retriever

Our dense retriever finds chunks with a similar *meaning*. A **lexical** retriever finds chunks
that share *words* with the question. That is useful for exact terms like "TOPIK" or "add/drop".
We will build the simplest honest version: **score = the share of question words that appear in
the chunk**.

This is a **teaching example**, not BM25. It ignores word frequency and chunk length. Real
results, simple algorithm: perfect for learning the workflow.

---

### Step 1 — Find the abstract class

The UI already shows a greyed-out **Lexical Retrieval** block. Its abstract class is
`BaseLexicalRetriever` in `backend/app/rag/blocks/retrieval.py`:

```python
class BaseLexicalRetriever(PipelineBlock):
    """Find chunks that share *words* with the query. Same input/output as BaseDenseRetriever."""

    @abstractmethod
    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult: ...
```

- **Input:** `query` (the search text) and `filters` (from metadata filtering; `None` for now).
- **Output:** a `RetrievalResult` (`backend/app/rag/schemas.py`) with a list of `Candidate`s,
  best first:
  ```python
  Candidate(rank=1, chunk_id="165c3154-…", doc_id="b4852b99-…", score=0.75)
  ```
  You only return IDs and scores. The next block (Chunk Lookup) loads the text from MongoDB.

### Step 2 — Create a subclass

Add this to the end of `backend/app/rag/blocks/retrieval.py`, next to the skeleton `BM25Retriever`:

```python
class KeywordOverlapRetriever(BaseLexicalRetriever):
    """IMPLEMENTED — score = share of the question's words that appear in the chunk.

    A teaching example: simpler than BM25 (no word frequency, no length normalization).
    """

    STOPWORDS = {"a", "an", "and", "are", "can", "do", "for", "how", "i", "in", "is", "my", "of", "on",
                 "the", "to", "what", "when", "where", "which", "who", "why", "with"}

    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult:
        ...  # step 3
```

You need `import re` at the top of the file. The other names (`Candidate`, `RetrievalResult`) are
already imported there.

### Step 3 — Implement the method

Replace the `...` with:

```python
        words = set(re.findall(r"[a-z0-9]+", query.lower())) - self.STOPWORDS
        if not words:
            return RetrievalResult(candidates=[], details={"query_words": []})
        scored = []
        for chunk in self.services.db.chunks.find({}, {"_id": 0, "chunk_id": 1, "doc_id": 1, "text": 1}):
            chunk_words = set(re.findall(r"[a-z0-9]+", chunk["text"].lower()))
            overlap = len(words & chunk_words)
            if overlap:  # chunks without any shared word are not candidates
                scored.append((overlap / len(words), chunk))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))  # best first; ties in a fixed order
        top = scored[: self.params["top_k"]]
        candidates = [Candidate(rank=i + 1, chunk_id=c["chunk_id"], doc_id=c["doc_id"], score=round(score, 4))
                      for i, (score, c) in enumerate(top)]
        return RetrievalResult(candidates=candidates, details={"query_words": sorted(words)})
```

What each part does:
- `self.services.db.chunks` is the MongoDB `chunks` collection (shared tools come from `self.services`).
- `self.params["top_k"]` is the hyperparameter you register in step 5. Never hard-code it.
- `details` is extra information. It appears in the stage's Output in the Execution tab.
- Every score is computed from real data. Never return made-up candidates.

### Step 4 — Register the class

Open `backend/app/rag/registry.py`.

1. Import your class. Add it to the existing `from app.rag.blocks.retrieval import (...)` lines:
   ```python
   from app.rag.blocks.retrieval import (BaseDenseRetriever, BaseHybridFusion, BaseLexicalRetriever, BaseMetadataEnricher,
                                         BM25Retriever, KeywordOverlapRetriever, MongoChunkLookup, QdrantDenseRetriever,
                                         ReciprocalRankFusion)
   ```
2. Find the `Stage("lexical_retrieval", ...)` entry and add a `Method` **before** the BM25 one.
   Start with `implemented=False`. It will show in the UI greyed out, so nobody can use it before
   it is tested:
   ```python
   Stage("lexical_retrieval", "Lexical Retrieval", "online", BaseLexicalRetriever,
         "Find chunks that share words with the question.", default_method=None, optional=True, methods=[
             Method("keyword_overlap", "Keyword overlap", KeywordOverlapRetriever, False,
                    "Share of the question's words found in each chunk (teaching example).", parameters={
                        "top_k": Param("integer", 5, "Top K", "How many chunks to retrieve.", min=1, max=20),
                    }),
             Method("bm25", "BM25", BM25Retriever, False, "Classic keyword ranking.", parameters={...unchanged...}),
         ]),
   ```

The `method_id` (`"keyword_overlap"`) must be unique in the whole registry. `default_method` stays
`None`, so the baseline pipeline does not change for anyone until they choose your method.

### Step 5 — Register hyperparameters

You already did this: `parameters={"top_k": Param(...)}`. Each `Param` becomes a control in the UI.

| Want | Write |
|---|---|
| a slider 1–20 | `Param("integer", 5, "Top K", "…", min=1, max=20)` |
| a decimal slider | `Param("float", 1.5, "k1", "…", min=0, max=3, step=0.1)` |
| a toggle | `Param("boolean", True, "Lowercase", "…", ui="toggle")` |
| a dropdown | `Param("enum", "fast", "Mode", "…", ui="select", options=("fast", "exact"))` |
| a text box | `Param("string", "", "Prefix", "…", ui="text")` |
| a setting that needs re-indexing | add `scope="ingestion"` |

Every key in `parameters` is available in your class as `self.params["key"]`, already validated.

### Step 6 — Add a test

Create `backend/tests/test_keyword_overlap.py`:

```python
import pytest

from app.rag.blocks.retrieval import KeywordOverlapRetriever

pytestmark = pytest.mark.anyio


async def test_chunks_sharing_words_come_first(services, db):
    db.chunks.insert_many([
        {"chunk_id": "c1", "doc_id": "d1", "text": "Dormitory applications open in January."},
        {"chunk_id": "c2", "doc_id": "d1", "text": "Scholarships require documents."},
        {"chunk_id": "c3", "doc_id": "d2", "text": "Dormitory rooms are assigned in February."},
    ])
    retriever = KeywordOverlapRetriever({"top_k": 5}, services)
    result = await retriever.retrieve("When do dormitory applications open?")

    assert [c.chunk_id for c in result.candidates] == ["c1", "c3"]   # c2 shares no word
    assert [c.rank for c in result.candidates] == [1, 2]
    assert result.candidates[0].score == 1.0                       # all 3 words: dormitory, applications, open
    assert result.details["query_words"] == ["applications", "dormitory", "open"]


async def test_top_k_is_respected(services, db):
    db.chunks.insert_many([{"chunk_id": f"c{i}", "doc_id": "d", "text": "dormitory"} for i in range(10)])
    result = await KeywordOverlapRetriever({"top_k": 3}, services).retrieve("dormitory")
    assert len(result.candidates) == 3
```

The `services` and `db` fixtures (in `backend/tests/conftest.py`) give you an in-memory MongoDB,
so no Docker is needed. Run only your tests, from `backend/`:

```bash
conda activate RAG
python -m pytest tests/test_keyword_overlap.py -v
```

✅ `2 passed`.

### Step 7 — Enable the method

Your tests pass, so change `False` to `True` in your `Method(...)`:

```python
Method("keyword_overlap", "Keyword overlap", KeywordOverlapRetriever, True, ...
```

Then run **all** tests: `python -m pytest`.

One existing test will now fail, on purpose:
`test_planned_stages_are_skipped_without_fake_output` in `backend/tests/test_pipeline.py`
lists `"lexical_retrieval"` as a stage that is *not implemented*. It isn't anymore: its skip reason
is now "Switched off in the configuration." Remove `"lexical_retrieval"` from that test's list,
then run `python -m pytest` again. ✅ Everything passes.

### Step 8 — Run the application

The backend reloads automatically if you started it with `--reload`. Otherwise restart it. Then
**reload the browser page**.

In **Configuration**:
- **Lexical Retrieval** is no longer grey. It is a normal card. Open it and choose
  **Keyword overlap**: a **Top K** slider appears, drawn from your `Param`.
- Turning on two retrievers at once shows a red message: *"Two retrievers are on: choose a Hybrid
  Fusion method to merge them"*. Hybrid fusion is not implemented yet, so to try your method set
  **Dense Retrieval → Off — skip this stage**.

```text
BEFORE                                       AFTER
░ Lexical Retrieval   NOT IMPLEMENTED        ✓ Lexical Retrieval
  [BM25 — BM25Retriever (planned)]             Method: [Keyword overlap ▾]   (BM25 — not implemented)
                                               Top K:  ──●──────── 5
```

### Step 9 — Inspect the output

Ask: *How do I apply for a dormitory at the ERICA campus?* and open **Execution**:

```text
░ Dense Retrieval        skipped — Switched off in the configuration.
✓ Lexical Retrieval · Keyword overlap        3 ms
    Input:      {"query": "How do I apply for a dormitory at the ERICA campus?", "filters": null}
    Output:     5 candidates (cards with similarity scores) + {"details": {"query_words": [...]}}
    Parameters: {"top_k": 5}
✓ Chunk Lookup · MongoDB lookup              loads the text of YOUR candidates
✓ … Context Builder, LLM Generation, Citation Verification …
```

Check that:
- the candidates' scores are the overlap shares you expect (1.0 = every question word appears);
- **Chunk Lookup** received exactly your chunk IDs;
- the answer cites chunks your method found.

Then compare with **Dense Retrieval** on a few questions. Which finds the right chunk more often?
That comparison is your research result.

### Step 10 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: Can't instantiate abstract class KeywordOverlapRetriever without an implementation for abstract method 'retrieve'` | method missing or misspelled | name it exactly `retrieve`, with `async def` |
| `TypeError: Registry error: KeywordOverlapRetriever must inherit from BaseLexicalRetriever` | wrong parent class, or registered in the wrong `Stage` | `class KeywordOverlapRetriever(BaseLexicalRetriever)` inside `lexical_retrieval` |
| `TypeError: Registry error: duplicate method id 'keyword_overlap'` | the ID already exists | pick a unique `method_id` |
| `ImportError: cannot import name 'KeywordOverlapRetriever'` | class not in that file, or name mismatch | check spelling in `retrieval.py` and in the `import` in `registry.py` |
| `TypeError: … got an unexpected keyword argument` / `missing … argument` | signature differs from the abstract method | copy `retrieve(self, query, filters=None)` exactly |
| `KeyError: 'top_k'` | parameter not registered | add `"top_k": Param(...)` to the `Method` |
| `AttributeError: 'list' object has no attribute 'candidates'` | wrong output type | return `RetrievalResult(candidates=[...])`, not a list |
| `KeyError`/`TypeError` in Chunk Lookup, or "missing in MongoDB" | invalid result schema: wrong IDs or plain dicts | build `Candidate(rank, chunk_id, doc_id, score)` with real `chunk_id`s |
| method is greyed out in the UI | `implemented=False` | step 7 |
| method missing in the UI | not registered, backend not restarted, or page not reloaded | see [04_METHOD_REGISTRY.md › Debugging](04_METHOD_REGISTRY.md#debugging-my-method-does-not-show-up-in-the-ui) |
| Send is blocked with a red message | a combination rule | read it, e.g. switch Dense Retrieval off |
| `RuntimeWarning: coroutine … was never awaited` | `def` instead of `async def` | online methods are `async def` |

---

## Guides for the other future methods

Every one of these already has an abstract class, a skeleton with TODO steps and a registry entry
with `implemented=False`. Follow the same steps 1–9: replace the `raise NotImplementedError(...)`
with real code, test it, set `implemented=True`, and update the "planned stages" test list.

### Query Rewriting — `LLMQueryRewriter(BaseQueryRewriter)` in `query_processing.py`
- **Where it runs:** first, before retrieval. Its output is the `query` both retrievers search
  with. The original question is still used in the prompt.
- **Method:** `async def rewrite(self, question: str) -> str`.
- **Reuse:** `self.services.ollama.pick_model(...)` and `chat_stream(...)` in `app/ollama.py`.
  Collect the pieces into one string.
- **Test:** with the `ollama` + `fake_ollama` fixtures, set `fake_ollama.answer` and check the
  returned string. Also test that an empty answer falls back to the question.

### Metadata Filtering — `ExactMetadataFilter(BaseMetadataFilter)` in `query_processing.py`
- **Where it runs:** before retrieval. Its output (`{"campus": ["ERICA", "ALL"]}`) is passed as
  `filters` to the retrievers. `QdrantDenseRetriever` already turns it into a Qdrant filter.
- **You also need:** the field in the Qdrant payload. Today the payload has only
  `chunk_id`/`doc_id`, so add the document's metadata (e.g. `metadata.extra["campus"]` from front
  matter) in `Database.replace_index()`, then **re-index**.
- **Input:** constraints from Query Understanding / Constraint Validation (implement
  `RuleBasedQueryUnderstanding` first, or read a fixed value from `self.params` for a start).
- **Test:** index two documents with different campuses; with the filter, only one campus comes back.

### BM25 — `BM25Retriever(BaseLexicalRetriever)` in `retrieval.py`
- **Where it runs:** Lexical Retrieval, like the tutorial. Start from your `KeywordOverlapRetriever`.
- **Formula:** `score = Σ IDF(t) · tf·(k1+1) / (tf + k1·(1 − b + b·len/avg_len))`, with
  `IDF(t) = ln(1 + (N − df + 0.5)/(df + 0.5))`. The parameters `k1`, `b` and `top_k` are already
  registered.
- **Test:** a chunk containing a rare word ranks above one containing only common words.

### Hybrid Fusion — `ReciprocalRankFusion(BaseHybridFusion)` in `retrieval.py`
- **Where it runs:** after both retrievers. The runner calls `fuse(dense.candidates, lexical.candidates)`,
  and only when dense, lexical *and* fusion are all on (the validator enforces this).
- **Method:** for every `chunk_id`, `score = Σ 1/(rrf_k + rank)` over the lists it appears in;
  sort, keep `top_k`, renumber `rank` from 1, and return a `RetrievalResult`.
- **Test:** a chunk ranked 2nd in both lists beats a chunk ranked 1st in only one list.

### Cross-Encoder Reranking — `CrossEncoderReranker(BaseReranker)` in `reranking.py`
- **Where it runs:** after Chunk Lookup, before Evidence Selection. It receives `Evidence` with
  text.
- **Method:** `async def rerank(self, query, evidence) -> list[Evidence]`. Score
  `(query, e.text)` pairs with `sentence_transformers.CrossEncoder`, sort, keep `top_n`, and
  renumber `rank` (`dataclasses.replace(e, rank=i)`). The model downloads ~90 MB once. Load it in
  a cached function, like `load_sentence_transformer` in `embedding.py`.
- **Test:** monkeypatch the model loader with a fake whose `predict()` returns fixed scores; check
  the new order.

### Evidence Sufficiency — `ScoreThresholdGate(BaseSufficiencyGate)` in `evidence.py`
- **Where it runs:** after Evidence Selection. If it returns `sufficient=False`, the runner skips
  the Context Builder, Generation and Citation Verification, and the Response Guard gives the honest
  "not enough information" answer. That logic already exists in `run_rag()`.
- **Method:** `async def check(self, question, evidence) -> SufficiencyDecision`.
- **Choose `min_score` by measuring**, not guessing: `data/eval/sample_questions.jsonl` has 14
  labelled questions (12 answerable, 2 not). Print the best score for each and pick a value that
  separates them. Say in your report that it was tuned on that small set.
- **Test:** evidence with scores `[0.2, 0.1]` and `min_score=0.5` gives `sufficient=False`; in a
  pipeline test the LLM is then not called (`fake_ollama.requests == []`).

---

## Beginner checklist

- [ ] I found the right abstract class and copied its method name and signature exactly.
- [ ] My class inherits from it and reads settings from `self.params`, tools from `self.services`.
- [ ] It returns the promised type (`RetrievalResult`, `list[Evidence]`, …) built from real data.
- [ ] I registered a `Method(...)` with a unique ID, a description and its `Param`s, starting at `implemented=False`.
- [ ] I wrote a test, and `python -m pytest tests/test_<mine>.py` passes.
- [ ] I set `implemented=True`, updated the planned-stages test, and the whole suite passes.
- [ ] I restarted the backend, reloaded the page, selected my method, and checked the Execution tab.
- [ ] I compared it with the existing method on a few real questions and wrote down what changed.
