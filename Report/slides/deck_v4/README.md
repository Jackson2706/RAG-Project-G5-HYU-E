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
- **Task 3 (dev-2 / test-3):** 204 drafted, 187 kept after the overlap check (`questions/overlap_check.json`:
  17 near-duplicates dropped, max cosine to any dev/test-1/test-2 question 0.895, no evidence passage shared with
  them). Writers' first seed type (similar passage pairs) was mostly noise (22 questions from 136 seeds). Topic
  bundles gave the rest. 113 are student-dependent by the writers, 74 controls: **fewer than the 140 / 60 asked**.
  Labeller A finished 47 of 187; labeller B none. Nothing is frozen and no system has seen these questions.
- **Task 4 (AAES+):** code done and tested (`aaes_llm.py`, the three AAES blocks take `mode` / `step3_mode` /
  `step4_mode`; 14 presets `AP_<code>`; RRRR = A0 unchanged, backend tests 263). A0b diagnosis:
  `aaes_plus/a0b_diagnosis.md` (the campus rule removed 4 of A0's 5 splits; NONE extractions the fifth). Stage B
  has started on dev (47 cases × 15 versions, `Report/results/deck4-dev`, LLM cache in `.run/llm_cache`). Dev-2,
  the stage-A component labels, the content judge, and stage C wait for the reset.

Continuation audit: `aaes_plus/audit_2026-11-16.md`. Both 187-row candidate label drafts now exist, but they have
no annotator metadata and are not treated as independent labels. Stage B has completed RRRR and LLLL on 47 dev
cases; BBBB has 11 resumable rows. T39 fixed Step 2 fallbacks and numeric Step 3 comparisons. Its dev-only probe
kept two measured failures: hypothetical identity extraction and the unnecessary winter-school campus split.

## Task 5 · Privacy and data check (done)

`privacy_check.md`, `privacy_scan.json` (`Sources/scripts/deck_v4_privacy.py`).
- Chat and remembered profile live only in the browser. **Forget my details** clears the profile (Task 1).
- Every request's trace (question, earlier turns, answer) is kept in MongoDB `hyu_compass.traces` with no expiry and no
  delete button (44 traces, the oldest from 2026-10-28). This is the main gap.
- Nothing from the chat leaves the Mac. The page loads Google Fonts, and the models come from Hugging Face on the
  first start.
- Index r5: 0 unmasked e-mails (1,424 masked). 292 office phone numbers. 23 title-plus-name candidates (public staff
  on notices).
