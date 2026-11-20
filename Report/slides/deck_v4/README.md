# Deck v4: AAES+ and evidence

One section per task, added as each task finishes. Every number comes from a file in this folder (named next to it).
Method names for slides: standard dense retrieval = B0, prompted conditional answering = R16, self-query filter = R15,
hybrid + cross-encoder = R5, scope prefilter = R9S, model only = G0, gold evidence = G1, AAES = A0.

## Task 1 · Demo rehearsal and usability (2026-11-16)

**What ran.** `Sources/scripts/deck_v4_demo.py`: compare mode (B0, R16, A0), index r5, 3 runs per scenario through
the same API the UI uses; reply types by evaluator v2 (unchanged). Cold = run 1 after the Ollama models were unloaded;
warm = runs 2–3. Output `demo_trials_v4.csv` (one row per turn, 81 rows). Screenshots and the fallback video:
`Sources/scripts/deck_v4_screens.py` (Playwright, deviceScaleFactor 2) → `Report/figures/usability/u01…u15.png`,
`error_messages.csv`, `demo_S1_S4_fallback.webm` (6.5 MB, S1, S2 three turns, S3, S4c with AAES).

**AAES's decision was the same in all 3 runs of every scenario** (`demo_trials_v4.csv`):

| Scenario | AAES (A0) | B0 | R16 | Compare-mode seconds, cold / warm |
|---|---|---|---|---|
| S1 "Which insurance rules apply to me?" (dev T14-132) | answer per case | answer | answer per case | 44.5 / 18.7, 27.4 |
| S2 counseling booking → "I'm a Seoul campus student." → ask again (dev T14-017) | asks campus → asks student type → answer per case by degree level; profile campus = seoul (remembered) | answer ×3 | answer (1 of 3 turn-2 replies per case) | 37.1 / 21.7, 27.3 |
| S3 insurance after D-4 → D-2 (dev T14-120) | asks degree level | refers | refers | 13.2 / 5.3, 7.0 |
| S4 partner schools, one-semester English visit (dev T14-184) | refers ("contact the OIA office of your campus") | refers | refers | 12.6 / 5.8, 2.9 |
| S4b same, with "I'm a Seoul campus student." | answer per case whose text says INSUFFICIENT_CONTEXT (v2 type: refer) | refers | refers | 22.4 / 10.9, 11.3 |
| S4c "I'm a Seoul campus student. Can I bring my pet dog into the dormitory?" (new) | refers: "…Please contact the Seoul campus OIA office." | refers | refers | 15.5 / 4.7, 4.4 |
| S5 backup failure: winter school (dev T14-042) | asks campus (unneeded) | answer | answer | 12.6 / 5.2, 4.9 |

- S4 has no campus, so the referral names no campus office. Five candidates for a referral that names the office are
  logged in `s4_candidates.csv`. Only S4c gave one, so S4c is the live S4. S4b (campus stated) is a logged failure:
  AAES chose a per-case answer and the generator wrote INSUFFICIENT_CONTEXT.
- S2 turn 2 is the student's reply alone. AAES reads the campus from it, but treats the sentence as a new question
  and asks a second detail (student type). The answer by degree level arrives on turn 3, when the student asks again.
- Template replies (ask, refer) take 0.2–0.4 s even cold. LLM answers take 4–18 s per column.

**UI changes (all in the React app, tests 19 frontend / 257 backend pass).**
- New dismissible **Help** panel (`HelpPanel.tsx`): what HYU Compass is for, 3 example questions, what each reply label
  means, that every fact has a source tag, how to clear the remembered profile, and "Not official advice; confirm with
  the OIA office." Shown on first visit; reopened with the Help button.
- **Remembered about you** line above the input (from AAES step 1 of the last answer), and a **Forget my details**
  button: the conversation stays on screen but earlier turns are no longer sent (`useChat.forget`).
- **Bug fixed:** the Configuration tab's preset list left out every preset of kind `aaes` (A0, AG, A0b, A1–A6, R9S,
  R15), so AAES could only be chosen in compare mode. One line in `ConfigurationTab.tsx`, plus a test.
- Plain, actionable error messages (input → message, `error_messages.csv`, screenshots u08–u14):

| Input | Message shown |
|---|---|
| Enter on an empty box | The question is empty. Type a question first. |
| 2,420-character question | Your question is 2,420 characters; the limit is 2,000. Shorten it to send it. (it was silently cut at 2,000 before) |
| model not pulled (`qwen3.5:9b`) | Ollama model 'qwen3.5:9b' is not installed. Run: ollama pull qwen3.5:9b |
| index missing | Index 'hyu_missing_r9' does not exist. Pick an existing index in the Configuration tab (Index to search), or build it first (Sources/data/DATA.md). |
| Ollama not running | Cannot reach Ollama at http://127.0.0.1:11999. Start the Ollama app (or run: ollama serve) and send the question again. |
| backend down | Cannot reach the HYU Compass backend at http://127.0.0.1:8000. Start it with ./start.sh in the Sources folder, then send the question again. |

  When the backend goes down after the page loaded, a second line still says "Fix the configuration error in the RAG
  Pipeline panel first." (screenshot u13); on a fresh load only the backend message shows (u14).

**Screenshots** (`Report/figures/usability/`): u01 first screen with help · u02 answer with a source open · u03
answer per case · u04 clarifying question · u05 remembered profile (Execution tab step 1 and the chat line) · u06
Execution tab · u07 compare mode · u08–u14 the error messages · u15 after Forget my details.

**Slide-ready examples.**
1. S2: "How do I book the international student counseling program?" → "The answer depends on your campus. Which
   applies to you: Seoul or ERICA?" → "I'm a Seoul campus student." → (ask again) answer per degree level, with
   "Remembered about you: campus seoul (remembered)" under the chat.
2. S4c: "I'm a Seoul campus student. Can I bring my pet dog into the dormitory?" → "The official pages I found do not
   apply to you (they are for another campus or student group). Please contact the Seoul campus OIA office." (3/3 runs)
3. Backup failure S5: "Is there a winter school for international students?" → AAES asks the campus 3/3 times, while
   B0 and R16 answer directly.

Not done by me: the human still has to rehearse once live and click through the Help panel.

## Status of Tasks 2–4 (2026-11-16, in progress)

The weekly usage limit for subagents was reached at about 12:40 (it resets 2026-11-20 06:00 KST). Labelling,
adjudication and the v3 content judge all run on subagents, so they wait until the reset. Local runs (Ollama, no
Claude usage) continue.

- **Task 2 (follow-up):** `Sources/scripts/deck_v4_followup.py`, 67 personas (43 dev cases + 24 from the deck-v3
  illustrative questions, `followup/personas_illustrative.json`). Runs are still going in `followup/runs.jsonl` (not
  committed yet: raw). The score rule was fixed before judging (script docstring). Waiting for: the v3 judge.
- **Task 3 (dev-2 / test-3):** frozen. The final pool had 328 blind candidates. Independent Sol and Astra labels,
  Terra adjudication of 57 decision disputes, deterministic checks, and one Astra verifier produced dev2=60 and
  test3=140. Twelve unresolved rows were excluded and replaced from the reserve. Verification reduced the final
  dependent slice to 87/200, below the requested 140/60 balance; this is a dataset limitation. The SHA manifest is
  `Sources/data/HYU/labels/FROZEN_dev2_test3.sha256`. No system read test3 before the freeze.
- **Task 4 (AAES+):** code done and tested (`aaes_llm.py`, the three AAES blocks take `mode` / `step3_mode` /
  `step4_mode`; 14 presets `AP_<code>`; RRRR = A0 unchanged, backend tests 263). A0b diagnosis:
  `aaes_plus/a0b_diagnosis.md` (the campus rule removed 4 of A0's 5 splits; NONE extractions the fifth). Stage B
  has started on dev (47 cases × 15 versions, `Report/results/deck4-dev`, LLM cache in `.run/llm_cache`). Dev-2,
  the stage-A component labels, the content judge, and stage C wait for the reset.

Continuation audit: `aaes_plus/audit_2026-11-16.md`. Both 187-row candidate label drafts now exist, but they have
no annotator metadata and are not treated as independent labels. Stage B has completed RRRR and LLLL on 47 dev
cases; BBBB has 11 resumable rows. T39 fixed Step 2 fallbacks and numeric Step 3 comparisons. Its dev-only probe
kept two measured failures: hypothetical identity extraction and the unnecessary winter-school campus split.

Task 3 methodology and agreement numbers are in `questions/METHODOLOGY.md`. The labels are LLM-annotated,
LLM-adjudicated and LLM-verified, not human-verified. A partial local Qwen pilot was retained only as an uncommitted
audit artifact and did not contribute to the freeze.

## Task 5 · Privacy and data check (done)

`privacy_check.md`, `privacy_scan.json` (`Sources/scripts/deck_v4_privacy.py`).
- Chat and remembered profile live only in the browser. **Forget my details** clears the profile (Task 1).
- Every request's trace (question, earlier turns, answer) is kept in MongoDB `hyu_compass.traces` with no expiry and no
  delete button (44 traces, the oldest from 2026-10-28). This is the main gap.
- Nothing from the chat leaves the Mac. The page loads Google Fonts, and the models come from Hugging Face on the
  first start.
- Index r5: 0 unmasked e-mails (1,424 masked). 292 office phone numbers. 23 title-plus-name candidates (public staff
  on notices).

## Deck v5 (brief v5, 2026-11-20/21)

Label limitation, stated plainly: the dev-2 and test-3 labels are LLM-annotated, LLM-adjudicated and verified by one
model (GPT-6 Astra); no person checked them. All comparisons on them are relative.

### Decisions taken without the user

1. **No `codex-plugin-cc` in this Claude Code install** (only `ponytail` and `humanizer` are installed, so `/codex:*`
   does not exist). Delegation used the same Codex through its CLI: `codex exec -s workspace-write -m gpt-6.1-sol` (the
   brief's Sol id; it answered a test call) and reviews with `codex review --uncommitted -c model="gpt-6.1-sol"`. The
   workspace-write sandbox makes `.git` read-only, so Codex cannot commit or push; every task said so and named its files.
2. **Task 2 blind judging:** the 516 items were copied into `.run/task2_judge/` with only the frozen prompt, split into
   6 disjoint batches of 86, one GPT-6 Sol run each, told to open no other file. The logs show each judge reading its
   batch 8–10 items at a time and writing judgments by hand (no script). `merge_judgments` combined the batches in three
   parts; its metadata label was changed from the stale `codex:gpt-6-astra` to `codex:gpt-6.1-sol`. No GPT-6 Astra
   judgments of Task 2 existed locally, so none had to be excluded.
3. **"I finished my coursework but I'm still living in Korea. How do I get insured?"** is not one of the 67 judged
   Task 2 personas; it was run once, one turn, with A0 (abstain, "no evidence", 2.5 s; `followup/runs.jsonl`). No
   two-turn transcript of it exists, so it is reported as that single turn.
4. **Held-out runs need a question-major runner:** `--case-major` and `--stop-at` were added to the runner (T43)
   instead of a separate script, so the held-out run uses the same pipeline and records as every other run.
5. **The machine was restarted mid-Phase 1** (lag). T44's Codex session ended before its note; Claude Code read the code,
   re-ran its tests (116 pass) and wrote `T44.result.md`. Docker volumes were intact after the restart.
6. **Controlled "before" for T42:** the brief's before numbers (BBBB kept 4) came from an older commit; the fixes were
   judged against a re-run at `1441216` in a clean git worktree (`.run/wt_pre_t42`, results via `HYU_RESULTS_DIR`).
7. **Runner order:** `--experiment` does not set the order (the config's list does), so on dev-2 every version runs in
   its own invocation in the brief's order, with LLLL last under its own `--stop-at`.
8. **Swap stall during timing:** with Docker's VM at 8.3 GB and Ollama holding ≈ 11.8 GB for Qwen 3.5, the Mac
   swapped (13.6 GB) and the first timing attempt reached 5 of 11 questions in 2 h 15 min. It was stopped, its partial
   results committed, and resumed from a clean tree (8 min). The recorded seconds are the pipeline's own `total_ms`.
9. **Test-2 method list:** test-2 had never been run; its A35 list (`PREREG_test2.md`) is replaced by the brief's seven
   held-out methods (`hyu.yaml test2_presets`), set before the freeze.
10. **u16 screenshot** shows the in-page confirmation and then clicks Cancel, so no stored trace was deleted for the picture.

### Phase 1 · Fixes and cleanup

Commits `6e0d712` (cleanup), `b698b3b` (code), `faf4179` (the commit the dev measurement ran from). Tests: backend 327,
evaluation 158, frontend 24, typecheck.

- **Cleanup:** 23 intermediate files (≈10.4 MB) untracked with `git rm --cached`, patterns in `.gitignore`, SHA-256 of
  each in `CLEANUP.md`. Git history was not rewritten, so they remain in `72a05f6`.
- **Trace expiry and delete (T41, T41b):** TTL index on `expires_from` (default 30 days, `TRACE_TTL_DAYS`, backfilled
  from `created_at`); localhost-only `GET/DELETE /api/traces` over **every** trace store (the default database and each
  index revision; the Codex review found that HYU-index chats store traces in their own database); "Delete stored
  history" in the Help panel with an in-page confirmation (`Report/figures/usability/u16_delete_history.png`, taken
  with Cancel: 47 traces counted, none deleted). `privacy_check.md` updated.
- **AAES+ both-mode fixes (T42).** Measured on dev (47) under evaluator v2. The fair "before" is a controlled re-run at
  the pre-T42 commit `1441216` with the same index and LLM cache (`Report/results/deck5-dev-preT42`); the "after" is
  `Report/results/deck5-dev`.

  | Version | Needed questions/splits kept (of 7), before → after | T14-042 winter school, before → after | Acceptable reply type |
  |---|---|---|---|
  | RRBR (Step 3 both) | 4 → 4 | clarify (campus) → **answer** | 0.447 → 0.468 |
  | BRBB | 4 → 4 | clarify (campus) → **answer** | 0.447 → 0.468 |
  | BRRR (Step 1 both) | 5 → 5 | clarify → clarify | 0.362 → 0.340 |
  | BBRB | 3 → 3 | answer → answer | 0.596 → 0.574 |
  | BBBB, BBBR, RBBB | 2 → 2 | answer → answer | unchanged |

  **Both fixes accepted** under the rule: T14-042 is answered without a campus question in the "both" versions and no
  version keeps fewer needed questions or splits. **The brief's "BBBB kept 4" is not the right baseline:** it came from
  the 16 Nov run (`deck4-dev`, commit `bacb730`), before T39 changed Step 2. At `1441216`, BBBB already kept only 2;
  every version with `both` at Step 2 lost splits there (e.g. RBRR 5 → 3), versions with rules at Step 2 did not.
- **Step 1 component set (150 messages; now development data):** both mode, before → after: hypothetical 2/6 → 5/6,
  campus-not-self 1/6 → 4/6, but plain 27/33 → 23/33, dev questions 28/47 → 20/47, campus recall 0.921 → 0.684,
  micro F1 0.793 → 0.769, invented values 26 → 19. Rules and LLM modes are unchanged (F1 0.768 and 0.767). The fix
  removes hypothetical values at the cost of dropping campuses a student names without "I'm …". Probe "If I were a
  master's student at ERICA, could I take the TOPIK class?": campus and degree level are dropped unless the LLM
  confirms them (unit test with a fake LLM, `test_aaes_plus_v5.py`).

### Phase 2 · Stage B on dev + dev-2, re-scored with evaluator v2

Runs: `Report/results/deck5-dev` (dev 47, commit `faf4179`), `Report/results/deck5-dev2` (dev-2 60, commit `55f9ce5`;
same system code). All 15 versions completed on all 107 cases (LLLL included, 20 min on dev-2). Reply types: frozen
evaluator v2 (prompt hash `5151f273055b`), never the runner's decision. Table: `aaes_plus/dev_ablation.csv`.

| Version | Acceptable reply type | Needed kept (of 36) | Unneeded questions/splits | Wrong referrals | LLM calls / question | Fresh s (median) |
|---|---|---|---|---|---|---|
| RBRR | 0.570 | 19 | 19 | 13 | 1.78 | |
| BBRB | 0.561 | 19 | 19 | 15 | 3.00 | |
| RLRR | 0.561 | 14 | 13 | 16 | 1.77 | |
| BBBB | 0.542 | 11 | 12 | 16 | 3.78 | 35.6 |
| LLLL | 0.533 | 14 | 16 | 15 | 4.76 | |
| **RRRL (AAES+)** | **0.393** | **23** | 45 | 13 | 1.42 | 7.6 |
| RRRB | 0.383 | 25 | 49 | 13 | 1.00 | |
| A0 = RRRR (AAES) | 0.374 | 25 | 50 | 13 | 0.34 | 0.3 |
| BRRR | 0.374 | 26 | 51 | 11 | 1.31 | |
| LRRR | 0.374 | 26 | 52 | 10 | 1.33 | |

(Full 15 rows in the CSV.) **Selection, rule fixed earlier:** RRRR keeps 25, so a version needs ≥ 20; eligible RRRL
(23), RRLR (22), RRRB (25), BRRR (26), LRRR (26); the highest acceptable rate among them is **RRRL = AAES+** (Step 4 decided
by the LLM, steps 1–3 by the rules). The versions with the best acceptable rate (RBRR 0.570, BBRB 0.561) keep only 19 of 36
needed questions or splits and are not eligible: on dev + dev-2 the gain in acceptable replies comes from asking less.

**Fresh timing** (`aaes_plus/timing_v5.csv`, dev-2 questions 2–11, LLM cache off, question 1 warmed every method):
median seconds / LLM calls per question: A0 0.3 / 0, AAES+ 7.5 / 1, B0 6.2 / 1, R15 9.5 / 2, G1 12.6 / 1 (9 questions:
one reply failed), R16 13.2 / 1, BBBB 35.5 / 4.

**Components** (`aaes_plus/components_v5.csv`, from the Stage B traces, no new labels; the Step 2 component set was skipped
for time): Step 3 chosen detail among the labelled branch details, A0 14/29 (0.48), BBBB 6/10 (0.60), LLLL 13/24 (0.54);
"needs a split" A0 precision 0.333 / recall 0.750, BBBB 0.417 / 0.278, RBRR 0.487 / 0.528; Step 4 exact reply type vs the
label, A0 0.187, AAES+ 0.215, LLLL 0.430.

Freeze: `aaes_plus_freeze.md` (committed and pushed before the held-out run).

### Phase 3 · Held-out test, once

Frozen commit `4e6d007`; test-3 (140) then test-2 (75), both complete (≥ 2.5 h were left: test-2 started 00:03 with
11.9 h to STOP_AT); test-1 never run. Details, tables and traces: `heldout/summary.md`, `heldout/reply_types.csv`,
`heldout/hypotheses.json`. Labels: LLM-annotated, adjudicated and verified by one model; no person checked them.

- **H1 supported:** AAES+ acceptable reply type 0.395 vs AAES 0.312, +0.084 [+0.042, +0.126], Holm p = 0.0001 (215).
- **H2 supported (non-inferior):** needed questions/splits kept on student-dependent questions 0.697 vs 0.727, −0.030
  [−0.076, 0.000] (66), lower bound above −0.10.
- **H3 supported:** on student-dependent questions AAES+ 0.671 vs prompted conditional 0.200, +0.471 [+0.329, +0.614] (70).
- **But over all questions AAES+ is still below every baseline** (acceptable 0.395 vs B0 0.544, R15 0.577, R16 0.609,
  BBBB 0.563, G1 0.674): 41% of its replies ask or split when the label says answer (AAES 52%, baselines 0–10%). Its
  advantage is only on the student-dependent 70 (0.671 vs 0.086–0.314). AAES+ costs a median 8.8 s per question vs 0.4 s
  for AAES.
- Infra: one AAES+ test-3 reply (N038) failed on an Ollama Metal GPU error and was retried once as a recorded resume.
- Slide examples (full text in `heldout/summary.md`): winter school (T2-011) now answered instead of an unneeded campus
  question; OIA location (T2-017) answered for Seoul only (broke an acceptable AAES question); counseling sign-up (T2-009)
  answered per campus while prompted conditional gave "please email us at the address below" with no address.
- Blind judge items for Phase 5: 475 answered replies of AAES+, AAES, B0, R16 (`heldout/judge/items.jsonl`, gitignored)
  and 171 of G1 (`items_gold.jsonl`); `key.jsonl` committed.

### Phase 5 · Held-out content, judged by Claude Opus 5.5 (v3 prompt)

475 answered replies (AAES+, AAES, B0, R16) in 12 disjoint blind batches, one Claude Opus 5.5 subagent each; key read only
after the merge. Table and judge-consistency notes: `heldout/content_summary.md`; numbers `heldout/judge/content_scores.csv`.

- Facts covered over each method's answered replies: AAES+ 0.383 [0.316, 0.454] (97), AAES 0.358 (67), B0 0.407 (145),
  R16 0.453 (166); CIs overlap.
- Wrong-group replies on student-dependent questions: AAES+ 0.333 (24) vs B0 0.489, R16 0.481 (CIs overlap).
- Replies with a wrong fact: AAES+ 0.227, AAES 0.179, B0 0.324, R16 0.295. Citation support 0.51–0.57 for all.
- Not paired: AAES+ answers fewer questions, so its rates come from a different, smaller set.
- Limitation: judges split on partly stated facts (some batches *missing*, others *correct*); not re-judged.

### Phase 6 · Demo rehearsal (AAES vs AAES+, 3 runs each)

`demo_trials_v5.csv` (script `scripts/deck_v5_demo.py`, same procedure as v4: run 1 cold, runs 2–3 warm).

- Winter school ("Is there a winter school for international students?", dev T14-042): **AAES+ still asks the campus,
  3/3 runs**, as AAES does (0.9–5.0 s vs 0.2 s). The T42 fix is in "both" mode; the chosen AAES+ (RRRL) uses rules in
  Step 1, so this demo failure stays. The held-out wording (T2-011) was answered. Do not use S5 as a success demo.
- Scenario 2 (counseling, then "I'm a Seoul campus student.", then the question again): identical behaviour for both,
  3/3 runs: asks campus → asks student type → answers per degree level with the campus remembered. AAES+ seconds per
  turn 0.9–6.6 (cold 3.1 / 2.1 / 6.6), AAES 0.2–9.0.

### Phase 4 · Task 2 follow-up, judged by GPT-6 Sol (v3 prompt)

All numbers in this section are **judged by GPT-6 Sol (v3 prompt)** (`followup/judge/judgments.meta.json`: 516 items,
prompt sha256 `3541b5db…`, judgments sha256 `3ebc12ca…`). Script: `Sources/scripts/deck_v5_task2.py` →
`followup/content_v5.{csv,json}`. Facts covered = correct / required facts over a system's answered replies; paired
differences use facts covered per persona (an unanswered reply counts 0), bootstrap 95% CI.

| System | Replies | Answered | Facts covered | Wrong fact | Wrong group | Turns |
|---|---|---|---|---|---|---|
| A0 two-turn, reply only | 39 | 25 | 0.000 | 0.000 | 0.080 | 2.79 |
| A0 two-turn, reply + re-ask | 39 | 24 | 0.200 | 0.175 | 0.458 | 3.67 |
| A0 details up front | 34 | 8 | 0.267 | 0.000 | 0.000 | 1.00 |
| B0 one turn | 39 | 28 | 0.455 | 0.205 | 0.536 | 1.00 |
| B0 details up front | 34 | 19 | 0.367 | 0.200 | 0.368 | 1.00 |
| R5 one turn | 39 | 30 | 0.354 | 0.188 | 0.400 | 1.00 |
| R15 one turn | 39 | 22 | 0.353 | 0.265 | 0.500 | 1.00 |
| R16 one turn | 39 | 29 | 0.348 | 0.239 | 0.552 | 1.00 |
| R9S one turn | 39 | 28 | 0.306 | 0.184 | 0.429 | 1.00 |

AAES two-turn final answer (reply + re-ask) minus each baseline, facts covered per persona: vs B0 one turn −0.222
[−0.350, −0.103]; vs R16 one turn −0.158 [−0.278, −0.056]; vs R5 one turn −0.201 [−0.333, −0.085]; vs the "details up
front" baselines between −0.164 (B0) and +0.020 (R15, R9S), every CI containing 0 except B0. Reply only is worse
than every baseline (−0.06 to −0.35, all CIs below 0). **AAES's two-turn flow does not recover the content of a
one-turn answer**, although its wrong-group rate on reply only (0.08) is the lowest of all answering systems.

Why reply only scores 0: the student's second turn is only "I'm a ERICA campus student.", and AAES treats it as a new
question. Transcripts (`followup/transcripts.md`):
1. **Failure (T14-033, reply only):** "Where do international students apply to return to the Seoul campus?" → asks
   academic status → "I'm on leave of absence." → asks degree level → "I'm an undergraduate student." → an answer about
   **TOPIK scholarships** (the last reply was read as the question).
2. **Success (I06, reply + re-ask, item F230):** "How do I take the mental health check for international students?" →
   asks campus → "I'm a Seoul campus student." → … → re-asked → "log into HY-in, navigate to Foreign student …" with
   all required facts correct and no wrong group.
3. **The insurance question** exists only as one A0 turn: "I finished my coursework but I'm still living in Korea. How
   do I get insured?" → "I could not find this in the official English HYU pages. Please contact the OIA office of your
   campus." (Decision 3.)
