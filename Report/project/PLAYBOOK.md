# PLAYBOOK — HYU Compass: data → labels → baselines → AAES → evaluation → report

Read `AGENTS.md` first. Claude Code orchestrates; Codex implements; humans run network/long jobs
and pass the gates. Each phase below has a **start prompt** to paste into Claude Code.

## Phase map

| Phase | What | Main owner | Ends at |
|---|---|---|---|
| P0 | Install skills, add agent files, voice sample, branch | Human | — |
| P1 | Reorganize repository into `Sources/ Report/` | Codex (T01–T02), Claude reviews | **G1** |
| P2 | Crawl HYU English data (Seoul OIA + ERICA OIA) | Codex code, human runs | G2 (with P4) |
| P3 | Benchmark datasets into `Sources/data/benchmarks/<name>/` | Codex code, human runs | — |
| P4 | HYU snapshot ingest + applicability tags (AAES offline step) | Claude tests, Codex code, human runs | **G2** |
| P5 | Labeling (Codex primary, Claude second, human adjudication) | All | **G3**, **G4** |
| P6 | New baselines (brackets, self-query, prompted-conditional, memory M1/M2) | Codex, Claude reviews | — |
| P7 | AAES online steps 1–4 + ablation presets | Claude tests first, Codex code | — |
| P8 | Metrics, HYU and memory suites, headless `run_all.sh` | Claude tests first, Codex code | — |
| P8D | Demo: all presets in the UI, compare mode, demo cases, demo script | Codex code, Claude reviews, human rehearses | G7 (demo part) |
| P9 | Dev runs → tuning → config freeze → one test run | Human runs, Claude analyses | **G5**, **G6** |
| P10 | Figures, tables, report, slides (Humanizer) | Codex drafts, Claude edits, human owns | **G7** |

## Gates (Claude Code stops and asks the human)

| Gate | Condition to pass |
|---|---|
| G1 | Reorg done; all Definition-of-done checks green; same Docker volumes; app starts; `docker volume ls` unchanged |
| G2 | Crawl report reviewed (counts, English coverage, warnings); attribute vocabulary frozen (v1); 50-chunk tag audit: precision ≥ 0.8 and recall ≥ 0.7 per attribute with ≥ 5 occurrences (A5) — split by A20 into **G2a** (vocabulary v1, passed) and **G2b** (tag quality on a fresh sample, before P7/P9 dev runs) |
| G3 | Labeling guideline approved by the team |
| G4 | Labels adjudicated; every test item human-verified; dev/test split frozen with SHA |
| G5 | Dev results reviewed; AAES and baseline configs frozen and tagged (`git tag config-freeze`) |
| G6 | Exactly one test run (clean tree, `--confirm-frozen`), logged in `Report/results/TEST_RUNS.md` |
| G7 | Report and slides reviewed; every number traced to `Report/results/`. Demo rehearsed: the scripted questions run in compare mode on the presentation laptop within the time slot; a backup screen recording exists |

## Schedule (target: end of this week)

| Day | Work |
|---|---|
| Mon | P0, P1 → G1. Start P2 code |
| Tue | Run crawl; P3 downloads; P4 tags + audit → G2; write guideline → G3 |
| Wed | P5 drafting + annotation + adjudication → G4 (evening). P6 in parallel |
| Thu | P7, P8, P8D (compare mode can be built in parallel); dev runs overnight (`caffeinate`) |
| Fri | G5 → single test run (G6) → P10 assets and drafts |
| Sat | Report, slides, demo rehearsal and backup recording (G7), buffer |

Priority if time runs short:
- **Must:** P1–P5, G0/G1 brackets, R16, R15, AAES A0 + 3 ablations, HYU suite.
  Also: every preset visible in the UI, compare mode, and the demo script.
- **Should:** M1/M2 memory slice, external conditional benchmark, demo-case picker with oracle presets.
- **Could:** MTRAG-UN subset, BEIR re-run.

---

## P0 — Setup (human, ~30 min)

1. Create a work branch and tag the current state:
   ```bash
   git switch -c hyu-aaes && git tag before-reorg
   ```
2. Copy `AGENTS.md` and `CLAUDE.md` to the repo root. Keep `PLAYBOOK.md` and `STATUS.md` under `Report/project/`:
   ```markdown
   # STATUS
   | Date | Phase | Task | State | Note |
   |---|---|---|---|---|
   ```
3. Install the skills in both agents:
   ```text
   # Claude Code (inside a session), as separate prompts
   /plugin marketplace add DietrichGebert/ponytail
   /plugin install ponytail@ponytail
   /plugin marketplace add blader/humanizer
   /plugin install humanizer@humanizer
   ```
   ```bash
   # Codex (terminal)
   codex plugin marketplace add DietrichGebert/ponytail
   codex plugin add ponytail@ponytail          # then open /hooks in Codex and trust its two hooks
   npx skills add blader/humanizer --global --agent codex
   ```
4. Create `Report/voice_sample.md` with 2–3 paragraphs that **you wrote yourself** (for example
   from an earlier report). Humanizer uses it to match your voice.
5. Check your course's AI-use policy. Create `Report/ai_use_statement.md` and keep it updated.
6. Move the lesson PDFs to `Report/course/` (gitignored, never pushed).

---

## P1 — Reorganize (T01, T02) → Gate G1

**Start prompt (Claude Code):**
> Phase P1. Read Report/project/PLAYBOOK.md §P1 and Appendix A.
> 1. Record the BEFORE state into `Sources/docs/agent_tasks/T01.before.md`:
>    - the Definition-of-done checks with the current paths;
>    - frontend `npm run typecheck && npm test`;
>    - the preset count from `GET /api/pipeline/presets`;
>    - `docker volume ls | grep hyu-compass`;
>    - `git status --short | head`.
> 2. Write T01 (moves) and T02 (path config) for Codex from Appendix A, delegate T01, review it,
>    then delegate T02 and review it.
> 3. Print the human-only commands for untracked local files (Appendix A.3).
> 4. Verify the AFTER state with the same checks, plus
>    `docker compose -f Sources/docker-compose.yml config | head -3` and a start/health check.
>    The same number of presets must appear in the UI, and one chat question must work in the
>    browser.
> 5. Update Report/project/STATUS.md and stop at Gate G1 with a before/after table.

---

## P2 — Crawl HYU English data (T03–T05)

**Start prompt (Claude Code):**
> Phase P2. Read Report/project/PLAYBOOK.md §P2 and Appendix B.
> - T03 (you): fetch robots.txt for each allowed site and save 8 fixture pages to
>   `Sources/crawler/tests/fixtures/`. Use the minimum calls. Pick pages covering: Seoul OIA static
>   page, Seoul notice post (trilingual), Seoul post with PDF attachment, ERICA /eng visa page,
>   ERICA /eng board list, ERICA /eng board post, ERICA scholarships page, one page with a table.
>   Record robots.txt results in `T03.result.md`.
> - T04 (Codex): crawler core and site configs, tested offline against the fixtures.
> - Review, then give me the exact crawl commands to run (dry-run first). After I run them, review
>   `crawl_report.json` (T05) and summarize counts, English coverage, warnings, and any surprises.

The human runs, inside `Sources/` with `conda activate RAG`:

```bash
caffeinate -i python -m crawler.run --site all --dry-run      # prints the URL plan only
caffeinate -i python -m crawler.run --site all --resume       # real crawl, polite, resumable
python -m crawler.run --build-snapshot                        # writes Sources/data/HYU/snapshots/<id>/
```

---

## P3 — Benchmark data (T06–T07)

**Start prompt (Claude Code):**
> Phase P3. Write T06 for Codex: move BEIR download/loading from `evaluation/datasets/` to
> `Sources/data/benchmarks/<name>/`, keeping the existing checksums and loaders. Add adapters for:
> - the original SciFact release (claims with labels and rationales), and
> - ONE external conditional-QA set (ConditionalQA or MDCR — check licences first and tell me which).
>
> Each dataset folder gets a committed `SOURCE.md` (URL, licence, checksum, date). Write T07 for
> Codex: a script that checks whether BEIR SciFact test query IDs map to original SciFact dev claims
> and reports SUPPORT/CONTRADICT/NEI counts. Give me the download commands; I run them.

---

## P4 — Snapshot ingest + applicability tags (T08–T10) → Gate G2

**Start prompt (Claude Code):**
> Phase P4. Read Appendix C and `Sources/docs/aaes_spec.md` (create it from Appendix C and D
> if missing).
> - T08 (you first): write `Sources/backend/app/rag/applicability.py` (vocabulary v0 + condition
>   data class) and tests from 10 real snapshot chunks with hand-written expected tags.
> - T08 (Codex): implement the `applicability_extractor` metadata-extraction subclass (rules first,
>   LLM fallback with schema validation and evidence-substring check) until your tests pass.
> - T09 (Codex): ingest the frozen HYU snapshot as a new index revision with tags in the MongoDB
>   chunk metadata and the Qdrant payload. Table rows repeat their header. E-mails masked. Give me
>   the ingest command.
> - T10 (Codex): `labeling/audit_tags.py` samples 50 chunks into `Report/notes/tag_audit.csv`
>   for human checking and computes precision per attribute.
>
> Stop at G2 with: crawl stats, tag-audit precision per attribute, and a proposed vocabulary v1.

---

## P5 — Labeling (T11–T18) → Gates G3, G4

Roles:
- **Codex** is the primary annotator on all cases.
- **Claude Code** is the independent second annotator on a ~30% subset and assists adjudication.
- **Humans** adjudicate every disagreement and verify every test item.

**Start prompt (Claude Code):**
> Phase P5. Read Appendix D.
> - T11 (you): write `Sources/data/HYU/labels/GUIDELINES.md` from Appendix D with 2 worked examples per
>   expected behaviour, national vs campus-scoped conditions, conditional vs clarify, and temporal
>   cases. Stop at G3 for team approval.
> - T12 (Codex): `Sources/labeling/` tools — `search.py` (BM25 over snapshot chunks: id, span,
>   text), `validate.py` (schema, enums, spans exist in snapshot), `agreement.py` (Cohen's κ on
>   answerability and expected_behavior, branch-attribute Jaccard, span overlap F1, adjudication
>   sheet), `freeze.py` (stratified split, seed 13, SHA file, read-only test file).
> - T13 (Codex): `topics.jsonl` (titles and headings only, no body text) and `personas.json`
>   (10 personas covering the vocabulary, each with a full gold profile).
> - T14 (Codex): draft questions from topics × personas only, without reading page bodies, using
>   the slice targets in Appendix D. Humans then delete unrealistic ones and add their own.
> - T15 (Codex): annotate all cases → `labels/annot_codex/`.
> - T16 (you): annotate the subset listed in `labels/subset_ids.txt` → `labels/annot_claude/`,
>   without opening `annot_codex/`.
> - T17: run agreement; prepare `labels/adjudication.csv`. Humans adjudicate.
> - T18: freeze. Stop at G4.

---

## P6 — New baselines (T19–T23)

**Start prompt (Claude Code):**
> Phase P6. Read Appendix E and AGENTS.md "UI and demo rules". For each new baseline write a short
> task for Codex. Each one is a subclass + registry entry + preset (with `group` and
> `description`) + test, and every existing preset stays unchanged. Each preset must show up in the
> UI picker and either run from the chat or be disabled with a clear reason:
> - T19: G0 closed-book, G1 oracle-context.
> - T20: R15 self-query (LLM → metadata filter on applicability payload; no filter when the
>   attribute is missing).
> - T21: R16 prompted-conditional.
> - T22: M1 history-aware rewrite, with session-history support in the runner and API (backward
>   compatible).
> - T23: M2 profile memory as a new `conversation_memory` block (none / buffer / profile), stored
>   in MongoDB, with staleness flags.
>
> Review each. Smoke-test on the dev split with `--smoke`. Then ask me to try each preset once in
> the browser.

---

## P7 — AAES online steps (T24–T28)

**Start prompt (Claude Code):**
> Phase P7. Read `Sources/docs/aaes_spec.md` and Appendix C.
> - T24 (you): write the tests first. Unit tests for each step use synthetic chunks, including the
>   ERICA part-time-work example. Expected outcome: branches on language status only;
>   IG(year) = 0; action CONDITIONAL. Also cover the unconditioned-fee example → ANSWER, and the
>   Seoul-student-asks-Ansan-office example → ABSTAIN. Add policy-table tests for all actions,
>   including CONFIRM for stale memory.
> - T25–T28 (Codex):
>   - `profile_understanding` (query_understanding);
>   - `applicability_reranker` (reranking, soft λ/μ);
>   - `applicability_sufficiency` (evidence_sufficiency: branches, values, information gain, policy);
>   - per-action generation templates;
>   - presets A0–A7 from Appendix E.
>
> All tests must pass. Every preset A0–A7 is in the UI under group `Ours (AAES)` or `Ablations`.
> Each step logs its typed input/output into the execution trace, so the Execution tab shows:
> - the profile with its stated/remembered/missing/stale status;
> - the applicability label of each candidate;
> - the branch table with values and information gain;
> - the chosen action.
>
> The chat message shows an action badge: ANSWER, CONDITIONAL, CLARIFY, ABSTAIN, or CONFIRM.
>
> **A23 addition (unknown condition status):** T24 also tests that evidence with
> `condition_status = "unknown"` is never treated as unconditioned. When the answer relies on it, AAES
> still answers, adds the caveat "This may depend on your situation; please confirm with the OIA
> office.", and sets the trace flag `unknown_condition_evidence = true`. P8 adds the metric
> unknown-caveat rate per slice (spec: `aaes_spec.md`, "Unknown condition status").

---

## P8 — Metrics, suites, headless script (T29–T32)

**Start prompt (Claude Code):**
> Phase P8. Read Appendix F and G.
> - T29 (you first): unit tests with hand-computed examples for every new metric.
> - T29 (Codex): implement the metrics.
> - T30 (Codex): `--suite hyu` and `--suite memory` in the runner (dev/test, per-query outputs,
>   slices, paired bootstrap + Holm on the pre-registered comparisons), plus tables in `summary.md`.
> - T31 (Codex): `Sources/scripts/run_all.sh` (Appendix G). The test-run guard refuses a dirty tree
>   or a missing `--confirm-frozen`, and appends to `Report/results/TEST_RUNS.md`.
> - T32 (Codex, Should): external conditional benchmark adapter in oracle-context mode.
>
> Finish with a full `--dry-run` and a dev `--smoke`.

---

## P8D — Demo in the UI (T36–T38)

**Start prompt (Claude Code):**
> Phase P8D. Read AGENTS.md "UI and demo rules" and Appendix H.
> - T36 (Codex): compare mode in the frontend. Pick 2–4 presets, run one question through each
>   **sequentially** via the existing `/api/chat/stream`, and show columns with answer, action
>   badge, citations, latency, and LLM calls. Clicking a column opens its Execution trace. The
>   existing single-chat view stays the default. Add vitest tests.
> - T37 (Codex): `GET /api/demo/cases` serves `Sources/data/HYU/labels/demo_cases.jsonl`
>   (8–10 dev cases, never test). A demo-case picker in the chat fills the question and session
>   history. Oracle presets (G1, A2) are enabled only when a demo case is selected; otherwise
>   `check_runnable` returns the reason. Presets needing applicability tags are disabled on
>   untagged indexes with a reason.
> - T38 (you): write `Report/slides/demo_script.md` using Appendix H. Pick the cases from dev
>   results where the presets differ most, and include a warm-up checklist and a timing for each
>   step.
>
> I will rehearse on the presentation laptop and record a backup video.

---

## P9 — Runs (human) and analysis (Claude) → Gates G5, G6

```bash
cd Sources && conda activate RAG
caffeinate -i ./scripts/run_all.sh --split dev --run-id dev-01            # overnight
# Claude analyses Report/results/dev-01, proposes tuning (dev only), we iterate dev-02, dev-03 ...
git tag config-freeze                                                      # Gate G5
caffeinate -i ./scripts/run_all.sh --split test --run-id test-final --confirm-frozen   # Gate G6
```

**Analysis prompt (Claude Code):**
> Analyse `Report/results/dev-XX/`.
> - Primary metrics with 95% CIs.
> - Slice table.
> - Wins/losses vs the strongest baseline.
> - The earliest failing AAES step using the oracle-input tests.
> - 20 failure examples with categories.
>
> Propose at most 3 dev-only changes and explain each. Do not open test labels.

---

## P10 — Report and slides (T33–T35) → Gate G7

**Start prompt (Claude Code):**
> Phase P10.
> - T33 (Codex): `Sources/scripts/make_report_assets.py` exports figures (PNG + SVG) and tables
>   (CSV + Markdown) from `Report/results/test-final` and `Report/results/dev-*` into `Report/figures` and
>   `Report/tables`, each with a source path.
> - T34 (Codex): draft `Report/report/draft.md` sections: data, setup, methods, baselines.
> - You: draft the results, discussion, limitations, and course-lesson mapping.
> - Then run `/humanizer:humanizer` on the draft with `Report/voice_sample.md` as the voice sample.
> - Then re-check every number against `Report/results/`.
> - T35 (Codex): slide outline in `Report/slides/outline.md`.
>
> Stop at G7.

---

# Appendix A — Reorganization map (P1)

### A.1 Tracked files (`git mv`, Codex T01)

| From | To |
|---|---|
| `backend/` | `Sources/backend/` |
| `frontend/` | `Sources/frontend/` |
| `evaluation/` (code, configs, tests, fixtures) | `Sources/evaluation/` |
| `evaluation/results/main/` | `Report/results/2026-11-01_main/` (legacy, keep files as-is) |
| `evaluation/annotations/` | `Sources/data/HYU/labels/legacy/` |
| `scripts/` | `Sources/scripts/` |
| `docs/` | `Sources/docs/` |
| `data/samples/` | `Sources/data/HYU/synthetic_fixture/` |
| `data/eval/`, `data/raw/README.md` | `Sources/data/HYU/labels/legacy/`, `Sources/data/HYU/README.md` |
| `docker-compose.yml`, `setup.sh`, `start.sh`, `stop.sh`, `uninstall.sh`, `.env.example` | `Sources/` |
| `.claude/` | stays at root (Claude Code loads project skills from the repo root) |
| `README.md` | stays at root; update its layout and run instructions |

### A.2 Path updates (Codex T02)

- `Sources/backend/app/config.py` adds `REPO_ROOT`, `DATA_DIR`, `RESULTS_DIR`, `REPORT_DIR`, with env
  overrides. Keep `BACKEND_DIR` and `PROJECT_ROOT` (now `Sources/`) for backward compatibility.
- `evaluation/beir.py` uses `DATA_DIR / "benchmarks"`. `evaluation/runner.py` uses `RESULTS_DIR`.
  `--run-id` help text is updated.
- Shell scripts still `cd` to their own folder. Update the `README` and docs commands
  (`cd Sources && python -m evaluation.runner ...`).
- `.gitignore` paths:
  - `Sources/backend/.env`, `Sources/.env`
  - `Sources/frontend/node_modules/`, `Sources/frontend/dist/`
  - `Sources/data/HYU/raw/`, `Sources/data/benchmarks/*/` with `!Sources/data/benchmarks/*/SOURCE.md`
  - `Report/results/*/raw/`, `Report/results/smoke*/`
  - `Report/course/`, `.run/`
- Create empty folders with `.gitkeep`: `Sources/data/HYU/{snapshots,labels}`, `Report/{report,slides,figures,tables,notes}`.

### A.3 Untracked local state (human runs; agents print these)

```bash
mv .env Sources/.env
mv backend/.env Sources/backend/.env
mv frontend/node_modules Sources/frontend/node_modules
[ -d evaluation/datasets ] && mkdir -p Sources/data/benchmarks && mv evaluation/datasets/* Sources/data/benchmarks/
[ -d .run ] && mv .run Sources/.run
```

### A.4 Safety checks

- `docker compose -f Sources/docker-compose.yml config` shows `name: hyu-compass`.
- `docker volume ls` lists the same two volumes before and after.
- Backend `/api/health` answers; the frontend loads; one chat question works.

# Appendix B — Crawl scope and identity rules (P2)

**Package:** `Sources/crawler/`
- `sites.py`: seed lists and per-site selectors.
- `fetch.py`: robots check, rate limit, retries, raw store, manifest append.
- `extract.py`: main-content selection, English block filter, tables → row text, attachments.
- `run.py`: CLI with `--site`, `--dry-run`, `--resume`, `--max-pages`, `--build-snapshot`.
- `tests/`: offline only, using the fixtures from T03.

**Seeds:**
- Seoul OIA: `https://oia.hanyang.ac.kr/sitemap.xml`. Boards `/notice`, `/sub4_01`, `/Forms`.
- ERICA OIA English: `https://global.hanyang.ac.kr/eng/` menu pages (`/eng/s1/*`, `/eng/s2/*`,
  `/eng/s3/*`) and boards `bo_table=s4_1_eng`, `s374_eng`, `s375_eng`, `s4_2_eng`.
- `studyerica.hanyang.ac.kr/eng/` only after G2 approval.

**Canonical identity:**
- Seoul posts: path `/notice/<id>`, etc.; drop `page`, `sort_index`, `order_type`, `#fragments`.
  Seoul attachments: key on `file_srl`.
- ERICA posts: keep only `bo_table` and `wr_id`.
- `doc_id = UUIDv5(NAMESPACE_URL, canonical_uri)`; `source_sha256 = SHA256(raw bytes)`.

**English filter:** block-level. Keep a block if Hangul + CJK characters are under 5% and Latin
letters are over 50%; borderline blocks are checked with a language-ID library.
Record `lang_coverage` per document.

**Document record** (`snapshots/<id>/documents.jsonl`) fields:
`doc_id`, `source_uri`, `site`, `campus` (seoul|erica), `board`, `post_id`, `title`, `post_date`,
`effective_date`, `text`, `spans`, `attachments[]`, `lang_coverage`, `warnings[]`, `parser_id`,
`source_sha256`, `version_family_id`, `superseded_by`.

**Deduplication:**
- Exact text duplicates become aliases with both URLs and both campus tags.
- Near-duplicates (MinHash ≥ 0.9) that differ in year, semester, or amounts form a `version_family`.
  They are never merged.

**Outputs:**
- `Sources/data/HYU/raw/`
- `Sources/data/HYU/manifest.jsonl`
- `Sources/data/HYU/snapshots/<id>/{documents.jsonl, crawl_report.json, SNAPSHOT.sha256}`

`<id>` = `hyu-YYYYMMDD` + the first 8 characters of the manifest SHA.

# Appendix C — Applicability vocabulary v0 (freeze as v1 at G2)

| Attribute | Values |
|---|---|
| `campus` | `seoul`, `erica` (scope `national` = applies to both) |
| `degree_level` | `undergraduate`, `master`, `doctoral`, `language_program`, `non_degree` |
| `year` | `1`, `2`, `3`, `4` (undergraduate only) |
| `student_type` | `degree_seeking`, `exchange`, `visiting`, `language_program`, `short_term` |
| `visa` | `D-2`, `D-2-5`, `D-2-8`, `D-4`, `D-10`, `other` |
| `topik_level` | `none`, `1`–`6` |
| `english_track` | `yes`, `no` |
| `academic_status` | `enrolled`, `leave_of_absence`, `completed_coursework`, `graduating`, `admitted_not_enrolled` |
| `term` | `YYYY-1`, `YYYY-2` (default: current term) |

Chunk condition format (MongoDB metadata + Qdrant payload):

```json
{"constraints": {"degree_level": ["undergraduate"], "year": ["1", "2"]},
 "scope": "national | campus", "campus": ["erica"],
 "requirements": ["GPA >= 2.0 in the previous semester"],
 "effective_term": "2026-2", "superseded_by": null, "extraction_method": "rule | llm"}
```

Requirements on attributes **outside** the vocabulary (GPA, attendance) are stated as caveats in
answers, never asked about. Online steps 1–4 and the policy are defined in
`Sources/docs/aaes_spec.md`, which Claude Code writes from our design discussion:
- Step 1: profile with stated/remembered/missing/stale status.
- Step 2: labels compatible/conflicting/open/unconditioned, with soft λ/μ penalty.
- Step 3: branches, per-branch values, D, information gain.
- Step 4: policy ABSTAIN / CONFIRM / ANSWER / CONDITIONAL / CLARIFY.

# Appendix D — Label schema and targets (P5)

```json
{
  "case_id": "hyu-0042", "case_version": "1.0", "snapshot_id": "hyu-20261110-ab12cd34",
  "split": "dev | test", "slice": "unconditional | conditional | temporal | negative | multi_session",
  "origin": "human | agent_draft_human_edited | agent_draft",
  "annotator": "codex:<model>", "adjudicated_by": "human:JK",
  "session_history": [{"role": "user", "text": "I'm a degree-seeking undergrad at ERICA."}],
  "question": "How many hours can I work part-time during the semester?",
  "stated_profile": {"degree_level": "undergraduate", "campus": "erica"},
  "gold_profile": {"degree_level": "undergraduate", "campus": "erica", "year": "2", "topik_level": "3", "visa": "D-2"},
  "branch_attributes": ["topik_level"],
  "answerability": "answerable | partial | unanswerable | external_only | korean_only",
  "expected_behavior": "answer | conditional_answer | clarify | abstain",
  "acceptable_behaviors": ["conditional_answer", "clarify"],
  "required_facts": ["cap depends on meeting the Korean requirement", "D-2 and GPA >= 2.0 required"],
  "gold_evidence": [{"doc_id": "...", "char_start": 0, "char_end": 0, "applies_to_gold_profile": true}],
  "inapplicable_evidence": [{"doc_id": "...", "char_start": 0, "char_end": 0, "why": "master's row"}],
  "outdated_evidence": [],
  "condition_scope": "national | campus",
  "reference_answer": "...",
  "notes": ""
}
```

**Targets:** about 180 cases, split dev about 50 and test about 130. Stratify by slice and campus.

| Slice | Share | Notes |
|---|---|---|
| unconditional | ~35% | single-fact and table questions |
| conditional | ~25% | answer depends on ≥ 1 profile attribute; mix of stated, unstated, and partly stated |
| temporal | ~10% | latest vs superseded versions |
| negative | ~20% | unanswerable, external-only, Korean-only |
| multi_session | ~10% | session 1 states attributes; session 2 asks. Includes attribute updates (stale memory) |

**Process rules:**
- At least 30% of questions are written or edited by humans. Report the share.
- Codex annotates everything. Claude annotates a stratified ~30% subset for agreement.
- Disagreements are human-adjudicated; every test item is human-verified.
- Report Cohen's κ (answerability, expected_behavior) before adjudication.

# Appendix E — Methods to run

| ID | Method | Data | UI group | In live demo |
|---|---|---|---|---|
| B0 | Basic dense RAG | HYU dev/test (+ BEIR) | Naive | yes |
| R1–R8, R11–R14 | Existing advanced baselines | HYU dev/test (+ BEIR) | Advanced | yes |
| R9, R10 | Prefilter / postfilter on stated attributes | HYU | Advanced | yes (needs tagged index) |
| G0 | Closed-book (no retrieval) | HYU | Brackets | yes |
| G1 | Oracle context (gold evidence only) | HYU | Brackets | only with a demo case |
| R15 | Self-query retriever (LLM → metadata filter) | HYU | Advanced | yes (tagged index) |
| R16 | Prompted conditional answering ("if it depends on the student, state conditions or ask") | HYU | Advanced | yes |
| M1 | History-aware rewrite (short-term memory) | HYU multi_session | Memory | yes |
| M2 | Profile memory (long-term, with staleness flags) | HYU multi_session | Memory | yes (shows profile + reset) |
| A0 | AAES full | HYU (+ multi_session with M2) | Ours (AAES) | yes |
| A1 | AAES with hard filter instead of soft penalty | HYU | Ablations | yes |
| A2 | AAES with oracle profile | HYU | Ablations | only with a demo case |
| A3 | Always clarify when any attribute is missing | HYU | Ablations | yes |
| A4 | Question-only ambiguity detector (no evidence branching) | HYU | Ablations | yes |
| A5 | AAES with LLM sufficiency judge instead of lexical | HYU | Ablations | yes |
| A6 | AAES without temporal rule | HYU temporal | Ablations | yes |
| A7 | AAES + M2 memory | HYU multi_session | Ours (AAES) | yes |

Offline presets O0–O8 stay in the picker under their existing `offline` kind.

- Generation backbone: `qwen3.5:4b` for all methods. `llama2:7b` only for B0, R5, R16, A0.
- Retrieval stays fixed (hybrid + cross-encoder, the best dev configuration) for all AAES variants.

**Pre-registered primary comparisons (Holm-corrected):**
1. A0 vs best of {B0, R5, R15, R16} on the applicability error rate (conditional + temporal).
2. A0 vs the same baseline on correctness, unconditional slice (non-inferiority margin 3 points).
3. A0 vs A4 on action macro-F1.

# Appendix F — Metrics (definitions in `Sources/docs/aaes_spec.md`)

| Category | Metrics |
|---|---|
| Retrieval | Applicable-Recall@k, Inapplicable-Intrusion@k, nDCG@10, MRR@10 |
| Selection | Selected applicable-gold recall vs mean context tokens |
| Decision | 4×4 action confusion matrix; macro-F1; clarification P/R; unnecessary-clarification rate; collapsed 2×2 gate matrix (proceed = answer/conditional, withhold = clarify/abstain) with FPR/FNR |
| Answer | Required-fact coverage; applicability error rate (AER, computed from cited [E#] chunks vs gold profile); conditional completeness; outdated-answer rate |
| Attribution | Grounding support, citation precision, citation coverage, applicable citation precision |
| Memory | Profile attribute P/R; stale-profile error rate; turns-to-answer |
| Cost | p50/p95 latency, LLM calls, prompt/output tokens |
| Statistics | Paired bootstrap (10,000) 95% CI; paired permutation; Holm; slice tables |

Any LLM judge (correctness, citation support) is validated against human labels on 60 dev
cases before use. Report its accuracy and κ.

# Appendix G — Headless runs and outputs

`Sources/scripts/run_all.sh --split dev|test --run-id <id> [--confirm-frozen] [--resume] [--smoke]`

Steps:
1. Preflight: Docker and Ollama health; models present; index revision exists; label SHA check.
2. For `test`: refuse if `git status --porcelain` is not empty or `--confirm-frozen` is missing.
3. Run suites in order: `hyu` → `memory` → `generation` (backbone comparison) → `external` (if present).
4. Write reports and append to `Report/results/TEST_RUNS.md` for test runs.

```
Report/results/<run_id>/
  run_manifest.json   status.json   summary.md
  per_query.csv       answers.jsonl          actions_confusion.csv   gate_matrix.csv
  retrieval_comparison.csv   comparisons_paired.csv   slices.csv   failure_analysis.csv
  raw/ (gitignored)
```

Report folder:

```
Report/
  report/ (draft.md, final.md)   slides/ (outline.md, deck)   figures/   tables/
  notes/ (decisions.md, tag_audit.csv, meeting notes)   course/ (gitignored)
  voice_sample.md   ai_use_statement.md
```

# Appendix H — Demo spec (P8D)

**Setup:** the presentation laptop runs everything locally: Docker (MongoDB + Qdrant), Ollama,
backend, frontend. No internet is needed. Use the frozen HYU index revision.

**Warm-up checklist (10 minutes before):**
1. Run `./start.sh`.
2. Load each Ollama model with one throwaway question.
3. Confirm the preset list shows every group, with no unexpected disabled presets.
4. Reset M2 memory.
5. Close other heavy apps.

**Compare-mode limits:** at most 3 columns live (≈ 3 × 5–15 s per question on a 16 GB Mac),
run sequentially. Precomputed dev results back up every scripted question.

**Script (about 8 minutes).** Pick the final questions from dev results where presets differ most;
these are the intended stories:

| # | Story | Question type | Columns |
|---|---|---|---|
| 1 | Unconditional question: no friction | fee or office-hours question | B0 · R16 · A0 → all ANSWER, same facts |
| 2 | Conditional question: wrong branch vs conditional answer | part-time work hours (ERICA visa page) | B0 · R15 · A0 → B0 picks one row; A0 CONDITIONAL |
| 3 | Clarify only when the evidence branches | question with many branches | A4 · A0 → A4 asks an irrelevant question; A0 asks the splitting attribute |
| 4 | Campus applicability: abstain and refer | Seoul student asks about an ERICA-only procedure | B0 · A0 → B0 gives the ERICA office; A0 refers to Seoul OIA |
| 5 | Memory: no repeated questions, but stale-profile check | two-turn script with an attribute update | M2 · A7 → A7 asks CONFIRM after the update |
| 6 | Look inside: Execution tab | any of the above | profile → labels → branches → decision |

**Rules:**
- Demo questions come from dev or are newly written. Never show test cases.
- Every claim on the slides about which method is better uses `Report/results/test-final`, not the live
  demo.


# Amendments

## 2026-11-10 (decisions from the planning chat, after P3 downloads)

**A1 Real-schema fixtures.**
- Before writing any loader for external data, inspect the real file: top-level type, keys, field
  types, and optional fields per split. Write that schema into the task file.
- Fixtures use synthetic content in the real structure.
- Every loader gets a real-data smoke test that loads the actual downloaded file and is skipped
  when the file is absent.
- Missing labels stay `None`. Never default them to False or "answerable".

**A2 SciFact roles** (choose the branch from the T07 result).
- If the BEIR SciFact test IDs equal the original dev claim IDs:
  - Keep BEIR SciFact for retrieval metrics.
  - Add a public sufficiency benchmark on the same 300 claims:
    - gold "sufficient" = the selected context contains ≥ 1 gold evidence abstract;
    - NEI claims are always "insufficient";
    - predicted positive = the system proceeds.
  - Report the course 2×2 gate matrix and 3-way verdict accuracy (NEI ↔ abstain).
  - Tune on original train (809 claims). Report the 300 once, after G5.
- Never use BEIR qrels as sufficiency labels: cited docs are not evidence docs. Use only the
  original evidence annotations.
- If the IDs do not map, build the sufficiency benchmark on original SciFact dev with its own
  corpus and index revision. Keep BEIR SciFact for retrieval only.
- Report caveat: NEI means "no evidence in the cited abstracts", not in the whole corpus.
- SciFact tests the single-branch case of AAES (ordinary sufficiency) and ablation A5.

**A3 ConditionalQA roles.**
- The official test set is unlabeled, so dev (285) is our held-out set: run it once, after G5.
- Tune only on a fixed, seeded 150-question sample of train (2,338).
- Mode: oracle document. The gold document is given, and sections inside it are retrieved to fit
  `num_ctx`.
- It tests vocabulary-free conditional answering: AAES steps 3–4, with conditions extracted from
  the text by the LLM. It does not test the HYU vocabulary.
- Metrics:
  - the dataset's official answer and condition metrics. Wrap the official evaluation script at
    the pinned commit if it exists; otherwise implement them with tests;
  - action accuracy (answer / conditional / not answerable).
- Priority: Should. Cite Sun, Cohen & Salakhutdinov, ACL 2022.
- Research use only. Never commit its data.

**A4 HYU lessons from P2.**
- Every chunk header that is embedded or indexed must be English-only. Fall back to the first
  English heading.
- Labels are stratified by campus, not proportionally: ERICA is only 56/362 docs but holds most
  conditional pages.
- The 4 `.hwp` files and 2 scanned PDFs are listed as known gaps. Questions answerable only from
  them are labeled `unanswerable_unreadable`.

**A5 Gate G2 criterion, updated.** For every attribute with ≥ 5 occurrences in the audit:
precision ≥ 0.8 AND recall ≥ 0.7. A missed condition makes conditional evidence look
unconditioned, which is the error AAES must avoid.

**P4 additions.**
- **T08 test set:** 12 real chunks with hand-written expected tags:
  - 4 ERICA (visa-table rows, scholarship);
  - 4 Seoul notices (insurance by academic status, acceptance guide by Korean-test result);
  - 2 unconditioned;
  - 2 superseded/temporal.
- **Site defaults:** ERICA chunks default to `campus=[erica]`, Seoul chunks to `campus=[seoul]`.
  `scope=national` only when the chunk states a national rule (visa or immigration law, NHI
  enrollment) without a campus-specific procedure.
- **Tagging:** `extraction_method` is recorded per field. Table rows are tagged from header and
  row together.
- **LLM fallback:**
  - qwen3.5:4b via Ollama, in the auxiliary role, recorded in the index manifest;
  - its output must validate against the vocabulary and quote a supporting substring of the chunk.
- **T09 index:**
  - a new index revision for hyu-20261110-97dc1269, built in three steps: BUILD → VERIFY →
    PUBLISH;
  - section-aware chunking 320/48, measured with the bge tokenizer;
  - English-only headers; a test that no chunk exceeds 512 tokens;
  - full tags in the MongoDB chunk metadata, and a compact copy of the filterable fields in the
    Qdrant payload;
  - the synthetic index stays untouched.
- **T10 audit:**
  - a stratified sample of 50 chunks: 25 Seoul, 25 ERICA, ≥ 20 with conditions, ≥ 5 table rows;
  - written to `Report/notes/tag_audit.csv`, with correct / wrong / missed columns per attribute;
  - precision and recall per attribute;
  - an attribute-frequency table over all chunks, to propose vocabulary v1.
- **G2 package:**
  - crawl stats;
  - the index verification report (counts, dimensions, unique IDs, max tokens, truncated = 0);
  - tag precision and recall per attribute;
  - the frequency table and the proposed vocabulary v1;
  - the T07 result and which A2 branch applies.

## 2026-11-10 (tag accounting, before the T09 ingest)

**A6 Tag partition.** Every chunk is in exactly one bucket:
`rule_tagged | rule_unconditioned | llm_tagged | llm_unconditioned | llm_rejected | llm_errors`.
- `rule_unconditioned` means no rule tag and no LLM cue, so the chunk was never sent to the LLM.
- VERIFY checks that the buckets sum to the chunk count, and that `llm_errors` = 0.

**A7 Unknown is not unconditioned.**
- A refused LLM answer (vocabulary or substring check failed) gives `condition_status = "unknown"`,
  with empty tags.
- In Step 2, an `unknown` chunk ranks like `unconditioned`, but it is flagged in the trace and
  counted in the audit.

**A8 T10 sampling.** The 50 audit chunks are stratified by bucket as well:
- ≥ 8 from `rule_unconditioned`;
- ≥ 5 from `llm_unconditioned`;

so recall is measured where the tagger said "no conditions".

## 2026-11-10 (before the tag audit)

**A9 topik_level is ordinal.** A threshold ("TOPIK 3 or above", "level 4 or higher", "Lv4~6",
"5+") is stored as every level from N to 6.
- The rules recognise these forms.
- An LLM answer whose evidence quote is a threshold is expanded the same way.
- An LLM answer that allows every value of an attribute is no constraint, and is refused.
- r1 stored "3 or above" as "3" (or as all levels) on about 40 LLM chunks. The audit therefore runs
  on r2, rebuilt from the LLM cache.

**A10 Audit scoring.**
- Recall is reported twice: raw on the sample, and weighted by bucket sizes over all chunks.
- The G2 table gives Wilson 95% intervals.
- The sample includes ≥ 6 chunks whose topik_level came from the LLM.
- The sheet has two free-text columns, `out_of_vocabulary_condition` and `audience`
  (applicant / admitted / enrolled). They are not scored; they feed vocabulary v1.

**A11 Before G2.**
- T11 (labeling guideline, drafted by Claude Code with vocabulary v0) and T12 (labeling tools,
  Codex, after T10) may start before G2.
- No labels are produced until vocabulary v1 is approved. T11 is updated after G2.

## 2026-11-10 (data layout, vocabulary v1 before the audit, automated audit)

**A12 Data lives in `Sources/data/`.**
- `Report/data/` moves to `Sources/data/`:
  - `benchmarks/<dataset>/` (with `SOURCE.json` and `SOURCE.md`);
  - `HYU/`: `raw/` (gitignored, kept), `manifest.jsonl`, `crawl_report.json`, `snapshots/`,
    `labels/`;
  - `DATA.md`.
- Results, index reports and audit notes stay in `Report/`.
- `DATA_DIR` defaults to `REPO_ROOT/Sources/data` (the env override is unchanged).
- The manifest and snapshot are moved, never rewritten; their sha256 is identical before and after.
- Deletions happen only after human OK. Never delete `raw/`, `manifest.jsonl`, the snapshot,
  `SOURCE.*` or `labels/GUIDELINES.md`.

**A13 Vocabulary v1 comes before the audit.**
- v1 is proposed from the r2 frequency table, and the human approves it.
- r3 = the postcheck fixes plus vocabulary v1:
  - postcheck fixes: drop a field that allows every value, normalized substring match, labeled
    rejection units, and a `postcheck_version`;
  - r3 becomes the HYU default index; r1 and r2 are kept for rollback.

**A14 Automated tag audit (team decision; replaces the human-filled sheet for G2).**
- 150 chunks are sampled from r3, stratified by bucket and campus, with ≥ 15 TOPIK chunks and
  ≥ 20 `rule_unconditioned`.
- Codex annotates them blind: chunk text, heading path, vocabulary v1 and the audit rules, but no
  predicted tags.
- A script scores predicted vs Codex tags: precision and recall per attribute, split by method,
  bucket and campus, with Wilson 95% intervals and bucket-weighted recall.
- A second Codex pass reviews only the disagreements: it sees both versions, decides, and gives a
  one-line reason.
- The rules are in `Report/notes/tag_audit_rules.md`.
- Limitation, stated in the report: "automated audit; reference annotator Codex, which also wrote
  the tagging rules; not human-validated".
- P4 is done when the human approves G2.

## 2026-11-10 (vocabulary v1 approved; cleanup)

**A15 Cleanup.**
- Approved deletions:
  - `HYU/README.md` and `labels/.gitkeep`;
  - `.DS_Store` files, finished Codex logs, caches;
  - `labels/legacy/qa_annotations.jsonl`, with `annotations: null` in `generation.yaml`.
- `synthetic_fixture/` moves to `Sources/backend/sample_data/`. The default index stays 5/23/23.

**A16 Missing raw files.**
- The crawler dry run reports a missing raw file as a warning; it does not crash.
- The guidebook PDF is re-fetched with one human-run request:
  - same sha256 (`a800a6ab…`): restore it into `raw/`;
  - different: do not keep it, and record "raw missing, upstream changed" in DATA.md.
- Three files disappeared at about 21:05 (the raw PDF, the fixture, `libtorch_cpu.dylib`). The
  cause is being investigated.

**A17 Vocabulary v1 (approved).**
- **`academic_status`** gains `applicant`, tagged only on admission guides.
  - **Scope default:** unless the user states they are an applicant, the profile excludes
    `applicant`.
  - The trace shows this with status `scope_default`, and P7 must use it.
- **`korean_standard ∈ {pass, exempt, fail}`** is a new attribute.
- **`student_type`** drops `short_term`.
- **Alternative condition sets (`any_of`)**, only where the text joins the groups with "or":
  - e.g. `[{topik_level: 3–6}, {english_track: yes}]`;
  - A_e(u) holds when any set fits;
  - an English-track student with no TOPIK is compatible.
  - The cross-chunk exception (stated in another chunk) is a known limitation.
- **Fixed postcheck mappings, shown in the trace:**
  - `visa=F*` or any `D-*` not in the list → `other`;
  - `student_type=international|volunteer` → dropped;
  - attribute `semester` → dropped.
- **Requirements, not attributes:** GPA and nationality.
- **Preference wording** ("preferred", "additional points", "optional") never becomes a constraint.
- **Prompt v3 re-call approved.** The v2 cache is kept for r2 reproducibility.
- **GUIDELINES.md moves to vocabulary v1.**
- **r3 = postcheck fixes + v1.** Part C (the automated audit) starts after r3 is published.

## 2026-11-11 (Gate G2 approved; P5 decisions)

**A18 Gate G2 approved by the human.**
- **Decisions:**
  - vocabulary v1 as approved in A17;
  - the rule fixes committed in the T08c review (`51f2873`): `exempt` only next to the Korean
    standard, no `applicant` on visa guides, the `any_of` method key.
- **What the approval was based on:**
  - the crawl stats;
  - the r1/r2/r3 verification reports (15/15 each);
  - the r3 frequency table;
  - T07 (300/300; A2 branch 1).
- **What was not yet available:** the automated tag audit (A14) had not finished, so no precision
  or recall numbers existed. The audit is completed anyway, and its scores are appended to the G2
  record.

**A19 P5 labeling, on top of the P5 start prompt and Appendix D.**
- **Vocabulary v1 everywhere.**
  - The label schema includes `korean_standard`, `academic_status=applicant` and
    `condition_sets`.
  - `gold_profile` contains `applicant` only when the persona is an applicant (the scope default).
- **Personas: 10–12.**
  - Together they cover campus, degree level, year, visa, TOPIK / English track, academic status
    and `korean_standard`.
  - At least 2 English-track students, and at least 2 ERICA students with visa questions.
- **Stratification:** by campus, on purpose rather than proportionally. Slices are as in
  Appendix D, and `answerability: unanswerable_unreadable` is used for answers that exist only in
  the `.hwp` files or the scanned PDFs.
- **multi_session** includes attribute updates (a stale profile), e.g. D-4 → D-2, or coursework
  completed.
- **Roles are unchanged:**
  - Codex annotates everything;
  - Claude Code annotates a blind ~30% subset;
  - `labeling.agreement` reports κ;
  - humans adjudicate the disagreements and verify every test item.
- **Demo cases** (8–10) are chosen from dev only, after the split is frozen.
- **After every labeling session:** commit and push the label files.
- **Stops:** at G3 (guideline approval) and at G4 (freeze), each with the numbers the human needs.

**A18 addendum (2026-11-11): automated audit results, appended to the G2 record.**
- **Where:** r3, 150 chunks, scored in `Report/results/tag_audit/hyu_20261110_97dc1269_r3/auto/scores_final.md`.
- **Limitation:** automated audit; reference annotator Codex, which also wrote the tagging rules;
  not human-validated. The disagreement reviewer was Codex too: it sided with the reference in 147
  of 177 rows and with the system in 18, with 5 both-wrong and 7 ambiguous. Same-model bias is
  likely.
- **Gate (precision ≥ 0.8 and weighted recall ≥ 0.7, attributes with ≥ 5 occurrences):**
  - pass: degree_level, topik_level, campus, scope, effective_term;
  - fail: year, student_type, visa, english_track, academic_status.
- **Rule 5b was added to the audit rules after the reference pass:** an alternative whose other
  options are outside the vocabulary gives no constraint. 4 reference rows were normalized; the
  original file is kept.

## 2026-11-11 (gate record corrected: G2 split into G2a and G2b)

**A20 G2 is split in two.** G2 was marked approved before the audit was scored, and the tag-quality
criterion is not met on the raw r3 scores.
- **G2a: vocabulary v1 approved.** Passed (A17, A18). P5 labeling may go on, because labels do not
  depend on the tags.
- **G2b: tag quality.** For each attribute with ≥ 5 occurrences: precision ≥ 0.8 and weighted recall
  ≥ 0.7, measured on a FRESH stratified sample (~100 chunks, none of the first 150) with a new blind
  Codex reference under the same audit rules, including 5b. Must pass before the P7/P9 dev runs.
  The r3 sample (150 chunks) is now the development sample for tagger fixes. Its scores are reported
  next to the fresh-sample scores, but G2b is decided on the fresh sample only.
- Order: cause breakdown of the failing attributes
  (`Report/results/tag_audit/hyu_20261110_97dc1269_r3/auto/causes_failing.json`) → proposed fixes →
  human OK → r4 build, VERIFY, publish, HYU default → fresh-sample audit → G2b.

**A21 Tagger fixes for r4 approved (human OK, 2026-11-11).**
- The fix list from the cause breakdown (A20) is approved as a whole: admission-guide applicant /
  admitted rules, stated-status rules for `enrolled` / `leave_of_absence`, ineligibility lists, year
  ranges, the target visa of a change, rule 5b in the tagger, audience-only visa and english_track.
- **Decision (c): `enrolled` only from stated wording,** never inferred from the audience. Audit rule 8b
  is added to `Report/notes/tag_audit_rules.md`. The applicant scope default (A17) already rules out
  applicants.
- **LLM fallback off for every attribute** (LLM precision < 0.8 or recall < 0.5 on all of them). r4 is
  built with `--no-llm`: 0 LLM calls. A chunk with an LLM cue and no rule goes to the new bucket
  `rule_cue_unknown` (condition_status `unknown`, A6). The LLM code and cache stay.
- Tasks: T08d (tagger, tests first by Claude Code), T10d (fresh sample, re-used sample, carried decisions).
- **Old sample on r4:** the r3 reference was written before rule 8b. Before the old-sample comparison, its
  `academic_status` rows are re-checked under 8b in a separate blind Codex pass (like the 5b
  normalization); the original file is kept.

## 2026-11-11 (Gate G3 approved)

**A22 G3 approved by the human** ("approve. i trust u"; confirmed by the human on 2026-11-11, A25). GUIDELINES.md becomes v1.0 and section 8 records
the three decisions: the clarify threshold is kept (> 3 branches or different procedures); the applicant
scope default is kept, and a question about applying for admission states `applicant`; a missing campus is
an ordinary branch attribute. T13 (topics, personas) starts. G2b is still open and runs alongside.

## 2026-11-11 (after r4; decisions from the planning chat)

**A23 r4 follow-up.**
1. **Parallel Codex jobs:** T10d writes only audit-tool code (`Sources/labeling/`, the Tag audit section of
   `aaes_spec.md`); T10e writes only reference data (`reference_r8b*` in the r3 audit folder). The paths do
   not overlap. Claude Code's own `aaes_spec.md` edit (item 2) waits until T10d has finished.
2. **Unknown condition status in AAES** (387 r4 chunks, 21%): spec section "Unknown condition status" in
   `aaes_spec.md`; tests in T24 (see the P7 start prompt); metric unknown-caveat rate per slice in P8.
   Unknown is never treated as silently unconditioned.
3. **G2b scoring on the fresh sample** (~100 chunks, none of the first 150), task T10f after T10d:
   - oversample `rule_cue_unknown` (~30 chunks);
   - per attribute: coverage (share of reference occurrences in resolved chunks), precision and
     recall on resolved chunks, and strict recall (an unknown chunk's reference values count as misses),
     all with Wilson intervals; bucket-weighted with the r4 partition;
   - an estimate, with interval, of the share of the 387 unknown chunks that truly carry a condition;
   - old sample (r4, reference after rule 8b) and fresh sample side by side.
   - The gate test (precision ≥ 0.8, weighted recall ≥ 0.7) uses the resolved-chunk numbers; strict
     recall and coverage are reported next to it (Claude Code's reading, to confirm at G2b).
4. **Time box:** at most one more tagger fix round after the fresh-sample scores. If G2b still fails, the
   scores are recorded as a documented limitation in `DATA.md` and the report, and the project moves on.
5. **P5 continues in parallel.** The planning chat says G3 still waits for the human's guideline
   approval. A22 recorded G3 as approved from the message "approve. i trust u"; that reading is now
   **pending the human's confirmation**. T14 (question drafting) does not start until G3 is confirmed.

**A24 G2b: last tagger round (human decision, option (a)).**
- r5 = fixes 1–4 from the dev-100 causes (T08e, tests first by Claude Code): degree level inherited only from an
  admission guide's own title or heading path, only inside that guide, with the count logged; prior
  qualifications and institution names give no degree level; student_type phrases; visa contact lines and
  misuse warnings. 0 LLM calls. Built, verified, published and made the HYU default; r4 kept for rollback.
- Samples are renamed: **dev-150** (r3 sample, rule 8b reference), **dev-100** (r4 fresh), **test-100** (new).
  test-100 excludes all 250, oversamples by text cues so that degree_level, student_type and visa each have ≥ 15
  expected occurrences, and is scored with design weights (T10g). G2b is decided on test-100 only. The report
  also counts degree_level errors in applicant-tagged chunks (AAES demotes those for in-scope students).
- **After this round, tagger work stops whatever the result.** The final scores and limitations go into
  `Sources/data/DATA.md`.
- Runs in parallel with P5 and must not delay labeling. (T14 still waits for the G3 confirmation, A23.5.)

**A25 G3 confirmed by the human (2026-11-11):** "approved with the three section-8 decisions as written".
GUIDELINES.md v1.0 stands. T14 (question drafts from topics × personas, no page bodies) starts.

**A26 Drafting and annotation inputs (decisions from the planning chat, 2026-11-11).**
1. **Hints never reach an annotator.** The drafter's hints (`intended_attributes`, `intended_answerability`,
   `why`, `topic_doc_ids`, and the slice) are moved to `labels/drafts/hints.jsonl`, used only for quotas and the
   human review. T15 (Codex) and T16 (Claude Code, blind subset) see only the question, the session history
   and the persona's `gold_profile` (the guideline needs it for `gold_evidence`; `stated_profile` is what they
   derive from the question).
2. **T10g builds the tool only.** The blind Codex reference for test-100 runs after T15 is finished, and only
   if Codex quota remains. T10g writes `labeling/auto_audit.py` and its own new test file; T14 writes
   `labeling/drafts.py`, its own new test file and `labels/drafts/`. No path overlaps.
3. **Human review sheet.** `labels/drafts/review.csv` (id, slice, campus, persona, session_history, question,
   decision keep/edit/delete, edited_question, notes) and an apply script: applies the decisions, sets
   `origin` (agent_draft / agent_draft_human_edited / human), appends the human's new questions, runs
   `labeling.drafts check`, and reports the slice quotas and the human share (target ≥ 30%).
4. **Data safety.** The 2026-11-10 21:05 file deletion is still unexplained. Label files are committed and
   pushed after every labeling session.
