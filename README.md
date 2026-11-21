# HYU Compass

HYU Compass is a retrieval-augmented (RAG) assistant for new international students at Hanyang University. It
answers from the official English pages of the Seoul OIA and the ERICA OIA sites and cites its sources. Its
research contribution is **AAES (Applicability-Aware Evidence Sufficiency)**: evidence counts as sufficient only when
it also applies to the student who asks (campus, degree level, visa, academic status, …). Otherwise the system answers
per case, asks one question, or refers the student to the right office. Course project for "Design of Generative AI
Application Systems". The final report is [Report/report/draft.md](Report/report/draft.md).

## Architecture

```text
question ──► Step 1 read the student (profile)            query understanding
         ──► hybrid retrieval: dense (BGE-small, Qdrant) + BM25, RRF fusion, cross-encoder reranking
         ──► Step 2 does each passage apply to this student   applicability reranker (tags in MongoDB)
         ──► Step 3 which student detail changes the answer   evidence sufficiency
         ──► Step 4 decide: answer / answer per case / ask one question / refer
         ──► writer (qwen3.5:4b via Ollama), cited [E#] sources ──► reply cleanup ──► reply + execution trace
```

- `Sources/backend/` FastAPI app. Every pipeline stage is a block with swappable methods
  (`app/rag/registry.py`); a preset is one choice per stage (`app/rag/presets.py`).
- `Sources/frontend/` React + TypeScript UI: chat, compare mode, Configuration and Execution tabs (each stage's real
  input, output and timing).
- `Sources/evaluation/` headless runner that reuses the app's pipeline code; metrics and reports.
- `Sources/crawler/`, `Sources/labeling/`, `Sources/scripts/` crawl, label and analysis tools that produced the data
  and the reported numbers.
- MongoDB stores documents, chunks with applicability tags and execution traces; Qdrant stores the vectors.

**AAES and AAES+.** Each of the four AAES steps can use rules (R), one call to the local LLM (L) or both (B), so a
version is named by four letters; RRRR is AAES. The final system, **AAES+ = RRRL** (rules in Steps 1–3, the LLM
decides in Step 4), was chosen on dev data by a rule fixed in advance. Presets: `A0_AAES` (RRRR), `AP_RRRL` (AAES+)
and all 15 `AP_*` versions; baselines `B0_BASIC_DENSE_RAG`, `R5_HYBRID_CROSS_ENCODER`, `R9S_SCOPE_PREFILTER`,
`R15_SELF_QUERY`, `R16_PROMPTED_CONDITIONAL`; references `G1_ORACLE_CONTEXT` (gold evidence) and `G0_CLOSED_BOOK`
(model only); ablations A1–A6 and the BEIR retrieval presets cited in the report. The exact prompt of every LLM
option is in [Report/slides/deck_v4/aaes_prompts.md](Report/slides/deck_v4/aaes_prompts.md).

## Setup (macOS or Linux)

Needs Docker Desktop (running), Conda, Node.js 20+ and [Ollama](https://ollama.com) with `qwen3.5:4b`.

```bash
cd Sources
./setup.sh   # once: creates .env and backend/.env with a random MongoDB password (if missing), the Conda env
             # `RAG` (if missing) with the pinned Python packages, npm packages, MongoDB + Qdrant, pulls the
             # Ollama model, and builds the small sample index. Safe to run again.
```

`.env.example` and `backend/.env.example` list every setting with placeholder values and no secrets.

Dependencies are pinned in `Sources/backend/requirements.txt`, `Sources/evaluation/requirements.txt` and
`Sources/frontend/package-lock.json`. `docker compose` (`Sources/docker-compose.yml`) runs MongoDB and Qdrant on
127.0.0.1 with named volumes; `docker compose down -v` would delete all local data.

## Build the HYU index

The cleaned pages from the crawl are committed as a frozen snapshot:
`Sources/data/HYU/snapshots/hyu-20261110-97dc1269/documents.jsonl` (362 documents, with `SNAPSHOT.sha256`). Raw crawled
bytes are not part of the repository.

**Rebuild the index from the cleaned pages** (deterministic: section chunks 256/32, BGE-small embeddings, rule-based
applicability tags, no LLM):

```bash
cd Sources && conda activate RAG
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r5 --no-llm
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r5 --publish
```

The build verifies itself before publishing; its report for the published index is
`Report/results/index_reports/hyu_20261110_97dc1269_r5.{json,md}`.

**The processed chunks as data:** `Sources/data/HYU/processed/r5_chunks.jsonl.gz` is a read-only export of the
published r5 index (1,867 chunks with text, section, source spans and applicability tags; no vectors), with
`r5_chunks.manifest.json` (count, SHA-256, the index build manifest). Use it to inspect or analyse the chunks
without a database, or to check a rebuild: the rebuilt index must report the same chunk count and
`chunk_id_sha256` as the manifest.

```python
import gzip, json
chunks = [json.loads(line) for line in gzip.open("Sources/data/HYU/processed/r5_chunks.jsonl.gz", "rt")]
```

## Run the app

```bash
cd Sources
./start.sh               # MongoDB + Qdrant, backend http://127.0.0.1:8000, frontend http://127.0.0.1:5173
./demo_preflight.sh      # health check: services, Ollama model, r5 index, UI; warms B0, R16 and AAES+ (exit 1 on failure)
./stop.sh                # stop (data kept; --keep-db leaves the databases running)
```

In the UI choose the preset "AAES+ (RRRL)" and the index `hyu_20261110_97dc1269_r5`, or press Compare to see standard
dense retrieval, prompted conditional answering and AAES+ side by side. Try "Which insurance rules apply to me?",
"How do I book the international student counseling program?" (then reply "I'm a Seoul campus student."), and
"I'm a Seoul campus student. Can I bring my pet dog into the dormitory?".

## Configuration

Settings live in `Sources/backend/.env` (names match `Sources/backend/app/config.py`):

| Setting | Default | Meaning |
|---|---|---|
| `FOLLOWUP_RESOLUTION` | `true` | After an AAES clarifying question, a reply that only gives the asked detail ("I'm a Seoul campus student.") answers the earlier question; the Execution tab shows "Answering your earlier question". |
| `CLEAN_REPLY` | `true` | Removes internal markers (e.g. "[No evidence provided]") from replies and merges per-case lines that only say "ask the office" into one closing line when at least two cases with facts remain. |
| `TRACE_TTL_DAYS` | `30` | Stored execution traces expire after this many days (0 = never). |
| `HYU_INDEX_ID` | `hyu_20261110_97dc1269_r5` | The HYU index revision. |
| `OLLAMA_CHAT_MODEL` | first installed | The generator model (`qwen3.5:4b` for every reported result). |

`FOLLOWUP_RESOLUTION` and `CLEAN_REPLY` are on in the app and off in the evaluation runner unless a run passes
`--followup-resolution` or `--clean-reply`, so the reported results are unchanged by them.

## Reproduce the evaluation

```bash
cd Sources && conda activate RAG && export HYU_LLM_CACHE=../.run/llm_cache
python -m evaluation.runner --suite hyu --split dev --experiment A0_AAES,AP_RRRL --run-id my-dev   # dev questions
python -m evaluation.rescore --run-id my-dev                                                      # reply types (evaluator v2)
```

The held-out hypotheses (`Report/slides/deck_v4/heldout/hypotheses.json`) were computed by
`python scripts/deck_v5.py heldout --run heldout-test3,heldout-test2 --splits test3,test2 --ours AP_RRRL --aaes A0_AAES
--conditional R16_PROMPTED_CONDITIONAL`; it reads the per-query records under `Report/results/<run_id>/raw/`, which are
too large to commit, so in this repository the saved summaries are the record.

The frozen question sets and labels are in `Sources/data/HYU/labels/` (hashes in `FROZEN*.sha256`). The held-out
sets (test, test2, test3) were each run once and are closed: re-running a system on them would no longer be a
held-out test. Saved results and their summaries are in `Report/results/<run_id>/` (per-query raw records are not
committed); the deck v5–v7 analyses the report cites are in `Report/slides/deck_v4/` (`aaes_plus/dev_ablation.csv`,
`heldout/hypotheses.json`, `heldout/content_summary.md`, …). Evaluation details:
[Sources/docs/06_BENCHMARK_AND_EVALUATION.md](Sources/docs/06_BENCHMARK_AND_EVALUATION.md).

## Privacy

No accounts and no profile store. Each request's execution trace (question, earlier turns, reply) is stored in the
local MongoDB for the Execution tab and expires after `TRACE_TTL_DAYS`. Help → "Delete stored history" shows how many
traces are stored and deletes them after an in-page confirmation; the count and delete endpoints answer only on
localhost. The crawler followed robots.txt, skipped staff directories and masked e-mail addresses at crawl time; a
few public staff names and office phone numbers on official notices remain in the index
([privacy check](Report/slides/deck_v4/privacy_check.md)). For a shared deployment, add authentication first.

## Limitations

- Questions and labels were written, annotated, adjudicated and verified by LLMs; no person checked them, so results
  are relative comparisons between methods.
- On the held-out sets AAES+ beats AAES (+0.084 acceptable reply type) and prompted conditional answering on
  student-dependent questions, but over all questions it is below every baseline (0.395 against 0.54–0.67): it asks
  or splits on 41% of questions that need one answer.
- One 4B model writes every answer; with the right evidence it still covers only about 0.61 of the required facts.
- English pages of two offices only; the index is a frozen November 2026 snapshot.

## Documentation

[Getting started](Sources/docs/01_GETTING_STARTED.md) · [RAG architecture](Sources/docs/02_RAG_ARCHITECTURE.md) ·
[Abstract classes](Sources/docs/03_ABSTRACT_CLASSES.md) · [Method registry](Sources/docs/04_METHOD_REGISTRY.md) ·
[Add a method](Sources/docs/05_ADD_NEW_METHOD.md) · [Benchmarks and evaluation](Sources/docs/06_BENCHMARK_AND_EVALUATION.md) ·
[AAES spec](Sources/docs/aaes_spec.md) · [Crawler](Sources/docs/crawler.md) · [Data provenance](Sources/data/DATA.md) ·
[AI use statement](Report/ai_use_statement.md)
