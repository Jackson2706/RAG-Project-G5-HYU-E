# PLAYBOOK — HYU Compass: data → labels → baselines → AAES → evaluation → report

Read `AGENTS.md` first. Claude Code orchestrates; Codex implements; humans run network/long jobs
and pass the gates. Each phase below has a **start prompt** to paste into Claude Code.

## Phase map

| Phase | What | Main owner | Ends at |
|---|---|---|---|
| P0 | Install skills, add agent files, voice sample, branch | Human | — |
| P1 | Reorganize repository into `Sources/ data/ results/ Report/` | Codex (T01–T02), Claude reviews | **G1** |
| P2 | Crawl HYU English data (Seoul OIA + ERICA OIA) | Codex code, human runs | G2 (with P4) |
| P3 | Benchmark datasets into `data/benchmarks/<name>/` | Codex code, human runs | — |
| P4 | HYU snapshot ingest + applicability tags (AAES offline step) | Claude tests, Codex code, human runs | **G2** |
| P5 | Labeling (Codex primary, Claude second, human adjudication) | All | **G3**, **G4** |
| P6 | New baselines (brackets, self-query, prompted-conditional, memory M1/M2) | Codex, Claude reviews | — |
| P7 | AAES online steps 1–4 + ablation presets | Claude tests first, Codex code | — |
| P8 | Metrics, HYU and memory suites, headless `run_all.sh` | Claude tests first, Codex code | — |
| P9 | Dev runs → tuning → config freeze → one test run | Human runs, Claude analyses | **G5**, **G6** |
| P10 | Figures, tables, report, slides (Humanizer) | Codex drafts, Claude edits, human owns | **G7** |

## Gates (Claude Code stops and asks the human)

| Gate | Condition to pass |
|---|---|
| G1 | Reorg done; all Definition-of-done checks green; same Docker volumes; app starts; `docker volume ls` unchanged |
| G2 | Crawl report reviewed (counts, English coverage, warnings); attribute vocabulary frozen (v1); 50-chunk tag audit precision ≥ 0.8 per attribute |
| G3 | Labeling guideline approved by the team |
| G4 | Labels adjudicated; every test item human-verified; dev/test split frozen with SHA |
| G5 | Dev results reviewed; AAES and baseline configs frozen and tagged (`git tag config-freeze`) |
| G6 | Exactly one test run (clean tree, `--confirm-frozen`), logged in `results/TEST_RUNS.md` |
| G7 | Report and slides reviewed by the team; every number traced to `results/` |

## Schedule (target: end of this week)

| Day | Work |
|---|---|
| Mon | P0, P1 → G1. Start P2 code |
| Tue | Run crawl; P3 downloads; P4 tags + audit → G2; write guideline → G3 |
| Wed | P5 drafting + annotation + adjudication → G4 (evening). P6 in parallel |
| Thu | P7, P8; dev runs overnight (`caffeinate`) |
| Fri | G5 → single test run (G6) → P10 assets and drafts |
| Sat | Report and slides (G7), buffer |

Priority if time runs short:
- **Must:** P1–P5, G0/G1 brackets, R16, R15, AAES A0 + 3 ablations, HYU suite.
- **Should:** M1/M2 memory slice, external conditional benchmark.
- **Could:** MTRAG-UN subset, BEIR re-run.

---

## P0 — Setup (human, ~30 min)

1. Create a work branch and tag the current state:
   ```bash
   git switch -c hyu-aaes && git tag before-reorg
   ```
2. Copy `AGENTS.md`, `CLAUDE.md`, and `PLAYBOOK.md` to the repo root. Create `STATUS.md`:
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
> Phase P1. Read PLAYBOOK.md §P1 and Appendix A.
> 1. Record the BEFORE state into `Sources/docs/agent_tasks/T01.before.md`: run the
>    Definition-of-done checks with the current paths, `docker volume ls | grep hyu-compass`, and
>    `git status --short | head`.
> 2. Write T01 (moves) and T02 (path config) for Codex from Appendix A, delegate T01, review it,
>    then delegate T02 and review it.
> 3. Print the human-only commands for untracked local files (Appendix A.3).
> 4. Verify the AFTER state with the same checks, plus
>    `docker compose -f Sources/docker-compose.yml config | head -3` and a start/health check.
> 5. Update STATUS.md and stop at Gate G1 with a before/after table.

---

## P2 — Crawl HYU English data (T03–T05)

**Start prompt (Claude Code):**
> Phase P2. Read PLAYBOOK.md §P2 and Appendix B.
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
python -m crawler.run --build-snapshot                        # writes data/HYU/snapshots/<id>/
```

---

## P3 — Benchmark data (T06–T07)

**Start prompt (Claude Code):**
> Phase P3. Write T06 for Codex: move BEIR download/loading from `evaluation/datasets/` to
> `data/benchmarks/<name>/`, keeping the existing checksums and loaders. Add adapters for:
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
> - T11 (you): write `data/HYU/labels/GUIDELINES.md` from Appendix D with 2 worked examples per
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
> Phase P6. Read Appendix E. For each new baseline write a short task for Codex. Each one is a
> subclass + registry entry + preset + test, and every existing preset stays unchanged:
> - T19: G0 closed-book, G1 oracle-context.
> - T20: R15 self-query (LLM → metadata filter on applicability payload; no filter when the
>   attribute is missing).
> - T21: R16 prompted-conditional.
> - T22: M1 history-aware rewrite, with session-history support in the runner and API (backward
>   compatible).
> - T23: M2 profile memory as a new `conversation_memory` block (none / buffer / profile), stored
>   in MongoDB, with staleness flags.
>
> Review each; smoke-test on the dev split with `--smoke`.

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
> All tests must pass. Each step logs its typed input/output into the execution trace, so the
> Execution tab shows it.

---

## P8 — Metrics, suites, headless script (T29–T32)

**Start prompt (Claude Code):**
> Phase P8. Read Appendix F and G.
> - T29 (you first): unit tests with hand-computed examples for every new metric.
> - T29 (Codex): implement the metrics.
> - T30 (Codex): `--suite hyu` and `--suite memory` in the runner (dev/test, per-query outputs,
>   slices, paired bootstrap + Holm on the pre-registered comparisons), plus tables in `summary.md`.
> - T31 (Codex): `Sources/scripts/run_all.sh` (Appendix G). The test-run guard refuses a dirty tree
>   or a missing `--confirm-frozen`, and appends to `results/TEST_RUNS.md`.
> - T32 (Codex, Should): external conditional benchmark adapter in oracle-context mode.
>
> Finish with a full `--dry-run` and a dev `--smoke`.

---

## P9 — Runs (human) and analysis (Claude) → Gates G5, G6

```bash
cd Sources && conda activate RAG
caffeinate -i ./scripts/run_all.sh --split dev --run-id dev-01            # overnight
# Claude analyses results/dev-01, proposes tuning (dev only), we iterate dev-02, dev-03 ...
git tag config-freeze                                                      # Gate G5
caffeinate -i ./scripts/run_all.sh --split test --run-id test-final --confirm-frozen   # Gate G6
```

**Analysis prompt (Claude Code):**
> Analyse `results/dev-XX/`.
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
>   (CSV + Markdown) from `results/test-final` and `results/dev-*` into `Report/figures` and
>   `Report/tables`, each with a source path.
> - T34 (Codex): draft `Report/report/draft.md` sections: data, setup, methods, baselines.
> - You: draft the results, discussion, limitations, and course-lesson mapping.
> - Then run `/humanizer:humanizer` on the draft with `Report/voice_sample.md` as the voice sample.
> - Then re-check every number against `results/`.
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
| `evaluation/results/main/` | `results/2026-11-01_main/` (legacy, keep files as-is) |
| `evaluation/annotations/` | `data/HYU/labels/legacy/` |
| `scripts/` | `Sources/scripts/` |
| `docs/` | `Sources/docs/` |
| `data/samples/` | `data/HYU/synthetic_fixture/` |
| `data/eval/`, `data/raw/README.md` | `data/HYU/labels/legacy/`, `data/HYU/README.md` |
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
  - `data/HYU/raw/`, `data/benchmarks/*/` with `!data/benchmarks/*/SOURCE.md`
  - `results/*/raw/`, `results/smoke*/`
  - `Report/course/`, `.run/`
- Create empty folders with `.gitkeep`: `data/HYU/{snapshots,labels}`, `Report/{report,slides,figures,tables,notes}`.

### A.3 Untracked local state (human runs; agents print these)

```bash
mv .env Sources/.env
mv backend/.env Sources/backend/.env
mv frontend/node_modules Sources/frontend/node_modules
[ -d evaluation/datasets ] && mkdir -p data/benchmarks && mv evaluation/datasets/* data/benchmarks/
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
- `data/HYU/raw/`
- `data/HYU/manifest.jsonl`
- `data/HYU/snapshots/<id>/{documents.jsonl, crawl_report.json, SNAPSHOT.sha256}`

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

| ID | Method | Data |
|---|---|---|
| B0, R1–R14 | Existing baselines (R9/R10 use stated attributes) | HYU dev/test (+ BEIR re-run optional) |
| G0 | Closed-book (no retrieval) | HYU |
| G1 | Oracle context (gold evidence only) | HYU |
| R15 | Self-query retriever (LLM → metadata filter) | HYU |
| R16 | Prompted conditional answering ("if it depends on the student, state conditions or ask") | HYU |
| M1 | History-aware rewrite (short-term memory) | HYU multi_session |
| M2 | Profile memory (long-term, with staleness flags) | HYU multi_session |
| A0 | AAES full | HYU (+ multi_session with M2) |
| A1 | AAES with hard filter instead of soft penalty | HYU |
| A2 | AAES with oracle profile | HYU |
| A3 | Always clarify when any attribute is missing | HYU |
| A4 | Question-only ambiguity detector (no evidence branching) | HYU |
| A5 | AAES with LLM sufficiency judge instead of lexical | HYU |
| A6 | AAES without temporal rule | HYU temporal |
| A7 | AAES + M2 memory | HYU multi_session |

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
4. Write reports and append to `results/TEST_RUNS.md` for test runs.

```
results/<run_id>/
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
