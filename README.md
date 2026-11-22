# HYU Compass

HYU Compass is a modular RAG (retrieval-augmented generation) assistant for new Hanyang University
students. It answers questions from official English HYU pages and cites its sources: Seoul OIA,
and the ERICA OIA English site. Every pipeline block (retrieval, filtering, evidence selection,
generation) is a swappable method, and the React UI shows each block's input and output. The
research contribution is **AAES (Applicability-Aware Evidence Sufficiency)**. Evidence counts as
sufficient only when it also applies to the asking student: campus, degree level, visa, term, and
so on. Otherwise the system gives a conditional answer, asks one question, or refers the student to
the right office. It is a course project for "Design of Generative AI Application Systems".

## Layout

```text
hyu-compass/
├── Sources/                all code
│   ├── backend/            FastAPI app and the RAG blocks (app/rag/registry.py lists every method)
│   ├── frontend/           React + TypeScript UI (chat, Configuration, Execution)
│   ├── evaluation/         headless benchmark runner, metrics, reports
│   ├── crawler/            polite crawler for the approved HYU sites
│   ├── labeling/           label search, validation, agreement, freeze; tag audit
│   ├── scripts/ docs/      ingest scripts; tutorials and task notes (docs/agent_tasks/)
│   ├── data/HYU/           crawl manifest, frozen snapshots, labels, synthetic sample documents (see data/DATA.md)
│   ├── data/benchmarks/    benchmark datasets (downloaded, not committed; SOURCE.md is)
│   └── setup.sh start.sh stop.sh uninstall.sh docker-compose.yml
├── Report/                 everything the experiments produce, and the report itself
│   ├── results/<run_id>/   one folder per evaluation run; index_reports/, tag_audit/
│   ├── project/            PLAYBOOK.md (plan and gates) and STATUS.md (progress log)
│   └── report/ slides/ figures/ tables/ notes/
├── AGENTS.md  CLAUDE.md    rules for the coding agents
└── README.md
```

All paths come from `Sources/backend/app/config.py`. You can override them with `HYU_REPORT_DIR`,
`HYU_DATA_DIR` and `HYU_RESULTS_DIR`.

## Quickstart

Needs Conda (environment `RAG`), Docker Desktop (running), Node.js 20+ and Ollama.

```bash
cd Sources
./setup.sh             # once: .env files, packages, MongoDB + Qdrant, an Ollama model, sample index
./start.sh             # databases, backend :8000, frontend → http://127.0.0.1:5173 (logs in Sources/.run/)
./stop.sh              # stop everything, data kept (--keep-db leaves the databases running)
./uninstall.sh         # remove containers, node_modules, caches; data kept (--delete-data asks first)
```

The step-by-step version is in [Sources/docs/01_GETTING_STARTED.md](Sources/docs/01_GETTING_STARTED.md).
The five documents in `Sources/backend/sample_data/` are invented practice documents, not
HYU policy.

## Evaluation

Experiments run headless through the same pipeline code as the UI:

```bash
cd Sources && conda activate RAG
python -m evaluation.runner --suite all --dry-run   # list the tasks, run nothing
python -m evaluation.runner --suite all --smoke     # a few queries per task
python -m evaluation.runner --suite all             # full run → Report/results/main/
python -m evaluation.reports --run-id main          # rebuild the reports from saved results
```

Tests: `cd Sources/backend && pytest -q`, and `cd Sources && pytest -q evaluation/tests crawler/tests`.
Details: [Sources/docs/06_BENCHMARK_AND_EVALUATION.md](Sources/docs/06_BENCHMARK_AND_EVALUATION.md).

## Where things live

| What | Where |
|---|---|
| Crawl manifest and frozen HYU snapshots | `Sources/data/HYU/manifest.jsonl`, `Sources/data/HYU/snapshots/<id>/` |
| Raw crawled bytes (not committed) | `Sources/data/HYU/raw/` |
| Labels | `Sources/data/HYU/labels/` |
| Benchmark datasets (not committed) | `Sources/data/benchmarks/<dataset>/` |
| Evaluation results | `Report/results/<run_id>/` (per-query `raw/` not committed) |
| Plan, gates, progress | `Report/project/PLAYBOOK.md`, `Report/project/STATUS.md` |
| Report, slides, figures, tables | `Report/report/`, `Report/slides/`, `Report/figures/`, `Report/tables/` |

## Documentation

1. [Getting started](Sources/docs/01_GETTING_STARTED.md)
2. [RAG architecture](Sources/docs/02_RAG_ARCHITECTURE.md)
3. [Abstract classes](Sources/docs/03_ABSTRACT_CLASSES.md)
4. [Method registry](Sources/docs/04_METHOD_REGISTRY.md)
5. [Add a new method](Sources/docs/05_ADD_NEW_METHOD.md)
6. [Benchmarks and evaluation](Sources/docs/06_BENCHMARK_AND_EVALUATION.md)
7. [Crawler](Sources/docs/crawler.md)
