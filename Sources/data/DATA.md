# Data: provenance and reproduction

Everything the code reads lives in `Sources/data/`, except the 5 invented sample documents of the
app's default index, which are in `Sources/backend/sample_data/` (ingest folder name `sample_data`). Paths are resolved by `DATA_DIR` in
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
│   ├── labels/                GUIDELINES.md (labeling guideline), legacy/sample_questions.jsonl (14 questions on the sample documents)
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
| r3 | vocabulary v1 (A17) and the postcheck fixes (A13) | vocabulary v1, prompt v3 (re-called), postcheck p1 | 1058 / 392 / 27 / 378 / 12 / 0 | published, kept for rollback |
| r4 | audit causes on r3 (A20/A21): stated status, year union, target visa, rule 5b; LLM fallback off | rules only (`--no-llm`), **0 LLM calls**; new bucket `rule_cue_unknown` (cue, no rule → condition unknown) | 1189 / 291 / 0 / 0 / 0 / 0, plus rule_cue_unknown 387 | published, kept for rollback |
| r5 | last tagger round (A24): guide degree level from the guide's own title (804 chunks), prior qualifications, institution names, student_type phrases, visa noise | rules only (`--no-llm`), **0 LLM calls** | 1189 / 291 / 0 / 0 / 0 / 0, plus rule_cue_unknown 387 | **HYU default** (`Settings.hyu_index_id`, env `HYU_INDEX_ID`) |

All five revisions use 1,867 chunks from 362 documents: max 344 embedded tokens, 0 truncated, and
`llm_errors` = 0.

**Versions:**
- **vocabulary:** `v0` for r1/r2; `v1` for r3 (`app/rag/applicability.py`, PLAYBOOK A17):
  - adds `korean_standard`, `academic_status=applicant` and alternative condition sets (`any_of`);
  - drops `student_type=short_term`;
- **LLM prompt:** `v2` for r1/r2, `v3` for r3. Both answer sets stay in the cache file, so r2 remains
  reproducible;
- **postcheck:** unversioned for r1/r2, `p1` for r3 (mappings, normalized quote match, labeled
  rejections, preference rule);
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
- **The TOPIK-or-English exception is missed when it sits in another chunk.** Alternative condition
  sets (`any_of`) are only built when one chunk joins the groups with "or". The ERICA Visa page puts
  the English-track exception to its Korean requirement in a different chunk from the TOPIK
  work-hours table, so that table's rows stay TOPIK-only. Answers must recover the exception at
  answer time (Step 3); the tags do not.
- **Three files disappeared from disk on 2026-11-10 at about 21:03–21:06, outside the project's
  tools:**
  - the raw PDF `raw/a8/a800a6ab…61ace.pdf` (the 70 MB Seoul Major Guidebook);
  - the sample-document folder (restored from git);
  - `libtorch_cpu.dylib` in the RAG env (torch reinstalled).

  The cause is being investigated: the Trash, cleaner apps, iCloud Desktop sync.
  - The snapshot text extracted from the PDF was intact throughout.
  - `crawler.run --dry-run` reports any missing raw file as a warning (A16).
  - **The PDF is restored.** On 2026-11-11, one human-run re-fetch of the same URL (crawler
    User-Agent) returned the identical sha256 `a800a6ab…61ace` (70,192,404 bytes). It was moved
    back into `raw/a8/`, and the crawler dry run now shows no missing raw files.

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
