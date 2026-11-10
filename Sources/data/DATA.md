# Data: provenance and reproduction

Everything the code reads lives in `Sources/data/`. Paths are resolved by `DATA_DIR` in
`Sources/backend/app/config.py`, which can be overridden with `HYU_DATA_DIR`. Results, index
reports and audit notes live in `Report/results/` and `Report/notes/`.

```text
Sources/data/
├── DATA.md                    this file
├── HYU/
│   ├── raw/                   crawled bytes, content-addressed by sha256 (gitignored)
│   ├── extracted/             per-document extraction output used to build snapshots (gitignored)
│   ├── manifest.jsonl         one row per HTTP request of the crawl (committed)
│   ├── crawl_report.json      report of the LAST crawl invocation (the ERICA resume run)
│   ├── snapshots/hyu-20261110-97dc1269/   documents.jsonl, crawl_report.json, SNAPSHOT.sha256 (committed)
│   ├── cache/llm_tags.jsonl   LLM applicability answers, keyed by model digest + prompt version + text sha (gitignored)
│   ├── labels/                GUIDELINES.md (labeling guideline), legacy/ (older BEIR answer-annotation stubs)
│   └── synthetic_fixture/     5 invented practice documents for the app's default index (not HYU policy)
└── benchmarks/<dataset>/      downloaded datasets; only SOURCE.md is committed
```

## 1. Sources and robots.txt

robots.txt was fetched on 2026-11-10 and returned HTTP 200 for all three hosts (T03):

| Host | Scope | robots.txt | Status |
|---|---|---|---|
| `oia.hanyang.ac.kr` | Seoul OIA, English text blocks and English attachments only | `Allow: /`; sitemap listed | crawled |
| `global.hanyang.ac.kr/eng/` | ERICA OIA English site, incl. `bo_table=*_eng` boards | `Allow: /`; `/index/admin/`, `/index/adm/` disallowed (not needed, also treated as disallowed) | crawled |
| `studyerica.hanyang.ac.kr/eng/` | — | `Allow: /` | **not crawled**: waits for Gate G2 approval |

**Politeness:**
- one request at a time, at least 2.5 s apart, following robots.txt;
- User-Agent `HYU-Compass-CourseCrawler/0.1 (+https://github.com/Jackson2706/hyu-compass; student research project)`.

**Denied by configuration:**
- Seoul `/` and `/staff`;
- the ERICA staff page.

Staff directories and personal data are never crawled. E-mail addresses are masked as `[email]` in
all extracted text.

## 2. Crawl (2026-11-10)

| Run | Command (from `Sources/`) | Result |
|---|---|---|
| Trial | `python -m crawler.run --site all --max-pages 30` | 60 requests in 150 s, all 200; led to 5 extractor fixes |
| Full | `caffeinate -i python -m crawler.run --site all --resume` | 59 min (3,565 s), 1,423 requests, all 200 except 5 × 403 (attachments of Seoul `sub4_01/1810217`, forbidden by the server); robots.txt skipped nothing; led to 5 more fixes |
| ERICA resume | `python -m crawler.run --site erica --resume` | 6 requests, 16 s: the `s374_eng` gallery listing and 4 image-only posts, which produced no documents |
| Snapshot | `python -m crawler.run --build-snapshot` | offline: no requests |

- `manifest.jsonl` has 1,365 rows and 1,356 unique raw files. Its sha256 is
  `97dc126903bdfafcd77643abd12df5306afa900379f5f43aefe0437818109b53`.
- `crawl_report.json` at the HYU root describes only the last invocation, the ERICA resume. The
  full-crawl numbers above come from `Sources/docs/agent_tasks/T05.result.md`.

## 3. Extraction: the English filter, and deduplication

**English filter** (`crawler/extract.py`):
- The unit is a text block. A block is kept when fewer than 5% of its letters are non-Latin and
  more than 50% are Latin.
- A neutral block (no non-Latin letters and fewer than 3 letters) is kept only right after a kept
  block.
- Scripts, styles and `noscript` are dropped.
- A document needs at least 30 English letters, counted after e-mail masking.
- Blocks with a Latin share between 0.5 and 0.7 are counted as `borderline_lang`.

**Deduplication** (`crawler/dedup.py`):
- **Exact:** after whitespace normalization, identical texts merge into one document, and the
  others become `aliases` (10 in total). The winner is the earliest post date, then the smallest
  doc_id.
- **Near duplicates:** MinHash over 5-word shingles (128 hashes). An estimated Jaccard of at least
  0.9 links two documents.
  - Linked documents with version markers (dates, years, terms) form a **version family**. The
    newest one is current, and the others get `superseded_by`.
  - Otherwise the pair is flagged `near_duplicate`.

## 4. Snapshot `hyu-20261110-97dc1269`

- **ID:** `hyu-YYYYMMDD-` + the first 8 hex digits of sha256(`manifest.jsonl`).
- **Contents:** 362 documents (306 Seoul, 56 ERICA), 10 aliases, 2 version families, 3 superseded
  documents, 0 unmasked e-mail addresses.
- **`SNAPSHOT.sha256`:**
  - `documents.jsonl` `4a6e26675ad4c8dd21feb507d8347356f4f5544ed0832ba4361fbc02489fb041`
  - `crawl_report.json` `cd8f41cefae7aad733e35bcd767d83b2fee0085776be08d8ec8452ef17418046`
- **Warnings:** 94 `title_not_english`, 4 `.hwp` unsupported, 2 PDFs without a text layer, 2 near
  duplicates.
- **Frozen:** never re-crawled or regenerated. `Sources/crawler/tests/test_committed_snapshot.py`
  checks the hashes and the ID.

## 5. Index revisions (MongoDB `hyu_bench_<id>` / Qdrant `bench_<id>`)

All revisions are built with `Sources/scripts/ingest_snapshot.py`:
- section-aware chunks of 320/48 bge tokens (`BAAI/bge-small-en-v1.5`);
- English-only headers;
- full applicability tags in MongoDB and `app_*` filter fields in the Qdrant payload;
- three steps, BUILD → VERIFY (15 checks) → PUBLISH.

Verification reports are in `Report/results/index_reports/`. The app's default index (the
synthetic fixture: 5 documents, 23 chunks) is separate and never touched.

| Revision | Why it exists | Tagging | Partition (rule_tagged / rule_uncond. / llm_tagged / llm_uncond. / llm_rejected / llm_errors) | Status |
|---|---|---|---|---|
| r1 | first build | vocabulary v0, prompt v2, qwen3.5:4b `7f3251fa6878…`, 772 LLM calls | 695 / 400 / 165 / 581 / 26 / 0 | published, kept for rollback |
| r2 | TOPIK thresholds were stored as a single level ("3 or above" → `3`) on about 40 LLM chunks (A9) | same + ordinal TOPIK rule and LLM post-check; **0 new LLM calls** (all cache hits) | 900 / 400 / 26 / 522 / 19 / 0 | published, kept for rollback |
| r3 | planned: postcheck fixes and vocabulary v1 (A13) | vocabulary v1, `postcheck_version` | — | not built; becomes the HYU default |

All three revisions use 1,867 chunks from 362 documents: max 344 embedded tokens, 0 truncated, and
`llm_errors` = 0.

**Versions:**
- vocabulary `v0` (`app/rag/applicability.py`; v1 is pending at G2);
- LLM prompt `TAG_PROMPT_VERSION = "v2"`;
- the postcheck is unversioned before r3;
- the LLM settings are temperature 0, seed 42, `num_ctx` 4096, thinking off.

## 6. Known gaps

- **Missing extraction:**
  - 4 `.hwp` attachments (Korean word processor) have no parser and are not extracted.
  - 2 PDFs have no text layer (scanned) and are not extracted.
  - Questions answerable only from these are labeled `unanswerable_unreadable` (A4).
- **Missing or partial raw data:**
  - The 5 Seoul attachments that returned 403 are not in the data.
  - 36 Seoul documents keep a few Hangul words inside mostly English blocks.
  - The Seoul `/counseling` tabs leave their `Kor Eng Chn` labels as noise.
- **The 2025 and 2026 NHI premium notices are not linked as versions.** Their titles differ by
  "(UPDATED: date)", and their texts differ too much for the near-duplicate rule.
- **One raw file was deleted from disk (2026-11-10, about 21:05, outside the project's tools):**
  the 70 MB Seoul Major Guidebook PDF, `raw/a8/a800a6ab…61ace.pdf`.
  - The snapshot text extracted from it is intact.
  - `crawler.run --dry-run` currently fails on the missing file.
  - It can be restored only by re-fetching that one URL. That needs human approval, because the
    snapshot is frozen.

## 7. Benchmarks (`benchmarks/<dataset>/`, downloaded, only `SOURCE.md` committed)

| Dataset | Source | Licence | Checksum | Downloaded |
|---|---|---|---|---|
| scifact (BEIR) | `public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip` | CC BY-NC 2.0 | md5 `5f7d1de6…` (published) | 2026-11-01 |
| nfcorpus (BEIR) | same host, `nfcorpus.zip` | CC BY-SA 4.0 | md5 `a89dba18…` (published) | 2026-11-01 |
| arguana (BEIR) | same host, `arguana.zip` | CC BY-SA 4.0 | md5 `8ad3e3c2…` (published) | 2026-11-01 |
| scifact_original | `scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz` | claims CC BY 4.0, abstracts ODC-By 1.0 | md5 `cb7da4d8…` (S3 ETag) | 2026-11-10 |
| conditionalqa | `raw.githubusercontent.com/haitian-sun/ConditionalQA/77bd2959…/v1_0/` | BSD 2-Clause; "ONLY for NLP research" | sha256 per file, recorded on first download | 2026-11-10 |

The BEIR SciFact test queries are the original SciFact dev claims: 300/300 IDs and texts match
(SUPPORT 124, CONTRADICT 64, NEI 112). See `Report/results/scifact_mapping/`.

## 8. Reproduction (from `Sources/`, `conda activate RAG`)

```bash
# 1. data (network; humans only)
python -m crawler.run --site all --dry-run                     # plan, no requests
caffeinate -i python -m crawler.run --site all --resume        # polite crawl → raw/, manifest.jsonl
python -m crawler.run --build-snapshot                         # offline → snapshots/<id>/
python -m evaluation.runner --download scifact,nfcorpus,arguana,scifact_original,conditionalqa

# 2. index (needs MongoDB, Qdrant and Ollama with qwen3.5:4b)
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id <id> --dry-run
caffeinate -i python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id <id>
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id <id> --publish   # only after VERIFY passes

# 3. checks
python -m evaluation.scifact_mapping
pytest -q crawler/tests labeling/tests evaluation/tests && (cd backend && pytest -q)
```

A new crawl produces a new manifest, and so a new snapshot ID. To reproduce *our* results, use the
committed snapshot and do not crawl again. With an intact `cache/llm_tags.jsonl`, rebuilding an index
makes 0 new LLM calls.
