# T04 — Crawler core and site configs (offline-tested)
Owner: Codex · Reviewer: Claude Code · Phase: P2

Goal: build `Sources/crawler/`, a polite, resumable crawler for the two allowed English sources
(Seoul OIA, ERICA OIA /eng). It must:
- store raw bytes once and keep a manifest;
- extract English-only document records;
- build an immutable snapshot.

Every test runs offline against the T03 fixtures. You have no network: never fetch anything.

Read first:
- AGENTS.md (Data rules, Network and long jobs, Definition of done);
- PLAYBOOK.md Appendix B;
- `Sources/docs/agent_tasks/T03.result.md`: selectors, boilerplate, exclusions. **This is the
  extraction spec.**
- `Sources/crawler/tests/fixtures/fixtures.json`;
- `Sources/evaluation/__init__.py`: how a package puts `backend/` on `sys.path`;
- `Sources/backend/app/config.py` (`DATA_DIR`).

Allowed write paths:
- `Sources/crawler/**` (except `tests/fixtures/`, which is read-only);
- `Sources/docs/crawler.md` (new, short);
- `Sources/docs/agent_tasks/T04.result.md`;
- `STATUS.md` (one line);
- `.gitignore`: add `data/HYU/extracted/` only.

Do not touch: `Sources/backend/**`, `Sources/evaluation/**`, `Sources/frontend/**`, `data/**`
except through code paths that tests point at a tmp dir, AGENTS.md, CLAUDE.md, PLAYBOOK.md.

## Dependencies

Use only the stdlib plus what the RAG env already has: `bs4` 4.15 (use the `html.parser`
backend; lxml is NOT installed), `httpx` 0.28, `pypdf` 6.21.

NOT installed: python-docx, openpyxl, lxml, datasketch, any language-ID library.
- Read DOCX and XLSX with `zipfile` + `xml.etree.ElementTree`:
  - DOCX: `word/document.xml`, paragraphs `w:p`, tables `w:tbl`;
  - XLSX: `xl/sharedStrings.xml`, `xl/worksheets/sheet*.xml`, `xl/workbook.xml` for sheet names.
- Implement MinHash with `hashlib`.
- Do not add a dependency. If you think you need one, stop and say so in T04.result.md.

## Spec

### Files

`sites.py`
- One small dataclass per site:
  - `name` (`seoul` | `erica` | `studyerica`), `campus`, `base_url`;
  - `enabled` (studyerica: `False`, "after Gate G2");
  - seeds, allow/deny URL patterns, content selector, drop selectors, `parser_id`.
- Values come from T03.result.md §3.
- Deny on every site: `/staff`, `/bbs/write.php`, `bo_table=s4_3_eng`, `bo_table=s354_eng`,
  `/index/admin/`, `/index/adm/`, other hosts.
- ERICA board lists to discover: `s4_1_eng`, `s374_eng`, `s375_eng`, `s4_2_eng`.

`fetch.py`
- `Fetcher(client, clock, sleep, min_interval=2.5, user_agent=...)`, injectable so tests use a
  fake clock and never really sleep.
- One request at a time.
- ≥ 2.5 s between the *start* of two requests to the same host. Also keep 2.5 s globally, which
  is simpler and fine.
- User-Agent: `HYU-Compass-CourseCrawler/0.1 (+https://github.com/Jackson2706/hyu-compass; student research project)`.
  Never an e-mail address.
- robots.txt:
  - fetch once per host through the same fetcher and parse it with `urllib.robotparser`;
  - a disallowed URL is never requested and is logged as `skipped_robots`.
- Follow redirects, but only within allowed hosts. Seoul downloads redirect once to
  `/file/procFileOutput`.
- Retries:
  - 3 attempts with backoff on connection errors and 5xx;
  - on 429, honour `Retry-After`;
  - 4xx other than 429 are not retried.
- Raw store: `DATA_DIR/HYU/raw/<sha[:2]>/<sha256><ext>`. Identical bytes are written once.
- Manifest:
  - append one JSON line per request to `DATA_DIR/HYU/manifest.jsonl` (fsync or flush per line);
  - fields: `url`, `canonical_uri`, `doc_id`, `site`, `kind` (robots|sitemap|listing|page|attachment),
    `parent_uri`, `status`, `fetched_at` (UTC ISO), `sha256`, `bytes`, `content_type`, `raw_path`
    (relative to DATA_DIR), `filename` (attachments, from Content-Disposition), `error`.
- All paths are taken as parameters, defaulting from `app.config.DATA_DIR`, so tests write to
  `tmp_path`.

`extract.py`, pure functions over raw bytes (no I/O except reading the bytes passed in)
- **Canonical URI** `canonical_uri(url)`:
  - Seoul: keep scheme+host+path; drop `page`, `sort_index`, `order_type`, `mid` paging params
    and the fragment. Attachment URLs become
    `https://oia.hanyang.ac.kr/?module=file&act=procFileDownload&file_srl=<N>`; `sid`,
    `module_srl` and `file_key` are dropped. A `procFileOutput?file_srl=N` redirect target maps to
    the same URI.
  - ERICA: for `/bbs/board.php` keep only `bo_table` and `wr_id`, in that order. Other paths drop
    all query params except those needed by the page (none for `/eng/*.php`). Drop the fragment.
  - Lowercase the host and use https.
  - `doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_uri))`. This is NOT the backend's
    `make_doc_id` namespace; T08 ingest will keep the crawler's doc_id.
- **Main content**: select the site/page-type content node, remove the drop selectors (T03 §3),
  then split into blocks:
  - `p`, `li`, `h1`–`h6`, `dd`/`dt`, leftover text directly inside `div`s;
  - each table row is one block.
- **Tables**: expand `rowspan`/`colspan` into a grid. Header rows (`th`, or the first row) give
  combined column names (`Permitted Hours / Weekdays`). Each body row becomes one line:
  `Header1: v1; Header2: v2; ...`, with the header repeated on every row.
  - Test it on the last table of `erica_s3_1_visa.html`. Expect a row such as
    `University Type: Bachelor's; Year: Year 1-2; ... Permitted Hours / Weekdays: 10 hours ...`.
    Assert on the cells you can see in the fixture, not on this exact example.
  - XLSX sheets use the same row format, with the first non-empty row as header.
- **English block filter**:
  - Count letters (`str.isalpha`).
  - `hangul_cjk` = Hangul syllables/jamo + CJK unified ideographs + kana.
  - Keep a block if `hangul_cjk / letters < 0.05` **and** `latin / letters > 0.5`.
  - Neutral block: no Hangul/CJK and fewer than 3 letters, e.g. `2026.03.01` or `O`. Keep it only
    if the previous non-neutral block was kept.
  - `shortcut:` there is no language-ID library for borderline blocks. A block with Latin share
    between 0.5 and 0.7 is kept and counted in `warnings` as `borderline_lang:<n>`.
- **Titles**: Seoul: the `.content_header` title, or `<title>` minus `한양대 국제처 - `. ERICA: the
  `#bo_v header` text, or the menu page's sub title.
  - If a title mixes languages, keep the longest run without Hangul/CJK, stripped of brackets.
  - If nothing English remains, keep the original title and add the warning `title_not_english`.
- **lang_coverage** per document:
  `{"en_letters": int, "total_letters": int, "ratio": float}` over all page+attachment blocks,
  before filtering.
- **E-mail masking**: replace every address with `[email]` in `text`, `title` and attachment
  filenames, after extraction. Test it with a fixture footer address and an inline one.
  Do not store the writer/author name.
- **Dates**:
  - `post_date` (ISO date) comes from Seoul `날짜 : YYYY.MM.DD` or ERICA `Date : YYYY-MM-DD`.
    Menu pages have `null`.
  - `effective_date` comes from an explicit pattern such as `UPDATED: 2026.03.01` or
    `(effective|applied|from|as of) <date>`. Otherwise `null`.
- **Attachments**:
  - Link discovery: Seoul `a[href*="procFileDownload"]` inside the content node; ERICA
    `a[href*="download.php"]` inside `#bo_v`.
  - Filename rule from T03 §3: fetch only names that look English or have no Hangul/CJK. Skip
    `(kor)`, `(국문)`, `(Korean)`, `中文`, `(중문)`.
  - Extractors by type:
    - PDF via pypdf;
    - DOCX/XLSX via zipfile;
    - HWP, images and unknown types are listed with warning `unsupported_attachment:<ext>`.
  - A PDF with no text layer gets warning `no_text_layer`. Test it with
    `pypdf.PdfWriter().add_blank_page(...)` written to bytes.
  - Attachment text goes through the same English filter.
  - Kept attachment text is appended to the document text after the page text as
    `\n\nAttachment: <filename>\n<text>`.
- **Document record**, written to `documents.jsonl`. The fields are exactly:
  `doc_id`, `source_uri`, `site`, `campus` (seoul|erica), `board`, `post_id`, `title`, `post_date`,
  `effective_date`, `text`, `spans`, `attachments[]`, `lang_coverage`, `warnings[]`, `parser_id`,
  `source_sha256`, `version_family_id`, `superseded_by`.
  - **plus `aliases[]`** (see dedup).
  - `spans`: `[{"char_start","char_end","kind": "heading|paragraph|list_item|table_row|attachment","source": "page"|"attachment:<file_srl or name>"}]`
    covering `text`.
  - `attachments[]`: `{canonical_uri, filename, content_type, sha256, lang_coverage, warnings}`.
  - `board`: e.g. `notice`, `sub4_01`, `Forms`, `s4_1_eng`, or `null` for menu pages.
  - `post_id`: the Seoul path id or the ERICA `wr_id`.
  - A document with 0 kept English letters is **not** emitted. It is counted in the report as
    `skipped_no_english`.

`dedup.py` (a small separate file is fine)
- **Exact**: identical normalized `text` (whitespace collapsed) → one record. The others go into
  `aliases: [{doc_id, source_uri, site, campus}]` of the record with the earliest `post_date`
  (tie: smallest doc_id). Both campus tags are kept that way.
- **Near-duplicates**:
  - MinHash over word 5-shingles, 128 hashes from `hashlib.blake2b` with per-index salt.
    Estimated Jaccard ≥ 0.9.
  - If the two texts differ in a year (`20\d\d`), a semester (`20\d\d-[12]`, `Spring|Fall|Summer|Winter`)
    or an amount (numbers with `won|KRW|%|,000`), they form a **version family**:
    - `version_family_id = uuid5(NAMESPACE_URL, "family:" + smallest member doc_id)`;
    - each older member (by `post_date`, else `effective_date`) gets `superseded_by` = the newest
      member's doc_id.
  - They are **never merged**: all members stay as separate records.
  - Near-duplicates without such a difference stay separate, each with warning
    `near_duplicate:<other doc_id>`.
- Pairwise comparison is fine:
  `shortcut: O(n²) pairwise MinHash, fine below ~3000 docs; add LSH banding if the corpus grows`.

`run.py`, CLI: `python -m crawler.run` from `Sources/`

- `--site seoul|erica|studyerica|all`
  - `all` = every *enabled* site;
  - `studyerica` exits with code 2 and the message `studyerica is disabled until Gate G2`.
- `--dry-run`:
  - prints the URL plan and makes no request: seeds, the known patterns per site, and the deny
    list applied;
  - offline it can only show seeds and rules. With `--from-fixtures` (tests only) or an existing
    manifest it expands the sitemap/menu from stored raw bytes.
  - Prints one line per planned URL plus a per-site count.
- `--max-pages N`: at most N **requests** per site, robots/sitemap included.
- `--resume`: skip every canonical_uri already in the manifest with status 200. Without
  `--resume`, an existing non-empty manifest makes the run refuse. That prevents accidental
  re-crawls.
- Discovery:
  - Seoul: the sitemap `<loc>` list, filtered by deny rules, then attachments found on fetched
    pages.
  - ERICA: the menu links in the stored `/eng/` page, then for each board fetch `&page=1..N`
    listings until a page brings no new `wr_id`, then posts, then post attachments.
  - Pinned rows repeat posts. The canonical URI dedups them.
- During a crawl:
  - each fetched page/attachment is extracted at once into `DATA_DIR/HYU/extracted/<doc_id>.json`.
    This is a gitignored preview, so the human and Claude can inspect a trial crawl.
  - At the end, write `DATA_DIR/HYU/crawl_report.json`:
    - per site: requests, by status, by kind, `skipped_robots`, `skipped_deny`,
      `skipped_no_english`, documents, attachments by type;
    - lang_coverage ratio histogram (deciles);
    - warnings counted by type;
    - wall time;
    - user_agent;
    - min_interval.
- `--build-snapshot`:
  - offline;
  - re-extracts every manifest page from the raw store, so parser fixes need no re-crawl;
  - dedups;
  - writes `DATA_DIR/HYU/snapshots/<id>/documents.jsonl`, `crawl_report.json` (the run report plus
    snapshot counts: documents, aliases, families, superseded) and `SNAPSHOT.sha256`
    (`sha256sum`-format lines for the two files);
  - `<id>` = `hyu-YYYYMMDD-` + the first 8 hex of SHA256(manifest.jsonl bytes);
  - if the directory already exists, refuse with exit code 1: snapshots are frozen;
  - documents are sorted by doc_id, so the output is deterministic.

### Tests (`Sources/crawler/tests/`, all offline)

Each bullet is at least one test:
- canonical URIs:
  - Seoul `?page=3&sort_index=x#c` dropped;
  - attachment `sid`/`module_srl` dropped, file_srl kept;
  - the `procFileOutput` redirect maps to the same URI;
  - ERICA keeps only bo_table+wr_id (`&page=2&sca=Visa` dropped);
  - doc_id is stable.
- Rate limit: with a fake clock and a fake transport (`httpx.MockTransport`), 3 requests → the
  recorded sleeps make the starts ≥ 2.5 s apart, and no real sleep happens. Also check that the
  User-Agent header is sent and contains no `@`.
- robots: a disallowed path is never requested. Use a mock robots.txt with the Yeti group from T03
  and a `*` group disallow.
- Retries: 503,503,200 → 3 calls; 404 → 1 call; 429 with Retry-After → the sleep is honoured
  (fake clock).
- Raw store: the same bytes fetched from two URLs → one file and two manifest lines. `--resume`
  skips URIs already in the manifest.
- Extraction on fixtures:
  - `seoul_summer` keeps English and contains no `bh_widget_content` popup text;
  - `seoul_notice_1814881_trilingual` contains `Monthly Insurance premium`, no Hangul and no CJK
    characters in `text`, and `lang_coverage.ratio` is between 0.2 and 0.8;
  - `seoul_sub4_01_1814504` lists its attachment links with file_srl;
  - `seoul_notice_1813514`: the page body gives ~0 English. With the PDF fixture as attachment,
    the document text contains attachment English text (`Part-time Work Confirmation`).
  - ERICA visa: the merged-cell table rows repeat the header and contain no privacy pop-up text
    (`Consent to the Privacy Policy`) and no menu text.
  - ERICA post wr86: title, `post_date == "2026-11-03"`, body text, no writer name.
  - ERICA list page: extracts the `wr_id` links, and pinned rows dedup.
  - Sitemap: `/staff` is excluded and `/notice/<id>` is included.
- Attachments: DOCX fixture text contains `GLOBAL KOREA SCHOLARSHIP`; XLSX rows are in header
  format; the blank PDF gets `no_text_layer`.
- E-mail masking: there is no `@`-address in any extracted fixture text.
- Record schema: the key set equals the Appendix B list plus `aliases`.
- Dedup:
  - two identical texts from seoul+erica → one record with 1 alias and both campuses;
  - two texts identical except `2025`→`2026` and `76,390 won`→`79,320 won` → 2 records in the
    same family, the older `superseded_by` the newer;
  - two unrelated texts → no family.
- CLI:
  - `--dry-run` makes zero requests (a transport that raises if called);
  - `--site studyerica` → exit 2;
  - `--max-pages 3` stops after 3 requests (mock transport);
  - `--build-snapshot` on a tmp DATA_DIR (built from fixtures) writes the 3 files, the id
    format is right, the sha256 lines verify, and a second run refuses.

Verify with:
- `cd Sources && pytest -q crawler/tests`
- `cd Sources/backend && pytest -q`
- `cd Sources && pytest -q evaluation/tests`
- `cd Sources && python -m evaluation.runner --suite all --dry-run`
- `cd Sources && python -m crawler.run --site all --dry-run`. This must make no network call; if
  the sandbox blocks the network, it must still finish.

Human runs (you must NOT run these): any crawl without `--dry-run`.

Done when:
- the AGENTS.md Definition of done is met;
- every test above exists and passes;
- `Sources/docs/crawler.md` documents the CLI in ≤ 40 lines;
- `T04.result.md` lists what was skipped and the human commands.
