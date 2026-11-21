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

## Deck v7 (demo fixes, 2026-11-21)

**Summary.** The reply cleanup is on in the app: internal markers are gone, and in an answer per case the cases that
only say "ask the office" are merged into one closing line when at least two cases with facts remain. Regression
(47 dev questions × AAES RRRL, cleanup off vs on): 46 of 47 reply types identical; the one change (T14-044) is the
frozen 4B evaluator relabelling a reply whose only edit is a removed " [no evidence]". The per-case candidate T14-130
gave a single answer in 3/3 AAES runs, so **the per-case demo stays D1 with the cleanup**. Exact prompt texts of every
AAES LLM option: `aaes_prompts.md` (generated from the code; all hashes match `aaes_plus_freeze.md`).

### Reply cleanup

- Code: `Sources/backend/app/rag/reply_cleanup.py`; flag `clean_reply` (settings, default on in the app; `run_rag`
  default off; runner `--clean-reply`). The trace keeps the writer's own text as `raw_answer` when the cleanup changed
  it. Tests: `tests/test_reply_cleanup.py` (12: markers removed, `[E#]`, links and ordinary brackets kept, merging,
  one-paragraph cases, no merge with fewer than two factual cases, only per-case answers merged).
- Regression, first version (`Report/results/deck7-clean-off`, `-on`): 4 of 47 reply types changed (T14-044, T14-132,
  T14-139, T14-158). In all four the merge left one case with facts plus "For other cases …", which evaluator v2
  (it needs at least two "If you" lines) then labels a single answer. Fixed: merge only while two or more cases with
  facts remain.
- Regression, final (`Report/results/deck7-clean2-off`, `-on`, commit `912ca0d`): **46/47 identical reply types**; 4 texts
  differ (markers removed). T14-044 changed from per case to answer under the frozen evaluator's 4B model; its text
  differs only by the removed " [no evidence]". Recorded as a measured deviation; not hidden by keeping the marker.

### Per-case scenario T14-130 and D1–D3 (cleanup on; `demo_trials_v7.csv`, `scripts/deck_v7_demo.py`)

| Scenario | Standard dense (B0) | Prompted conditional (R16) | AAES+ (RRRL) |
|---|---|---|---|
| T14-130 "Can I work part time here?" (3 runs) | answer 3/3 (12.2–27.1 s) | answer 3/3 (13.6–13.8 s) | answer 3/3 (2.4–6.6 s) |
| D1 insurance rules | answer 1/1 (13.1–13.1 s) | conditional_answer 1/1 (12.7–12.7 s) | conditional_answer 1/1 (20.0–20.0 s) |
| D2 counseling | answer 1/1 (5.1–5.1 s) | clarify 1/1 (8.8–8.8 s) | clarify 1/1 (4.2–4.2 s) |
| D2 → "I'm a Seoul campus student." | answer 1/1 (12.1–12.1 s) | conditional_answer 1/1 (13.2–13.2 s) | conditional_answer 1/1 (15.1–15.1 s) |
| D3 pet dog, Seoul | abstain 1/1 (10.5–10.5 s) | abstain 1/1 (10.4–10.4 s) | abstain 1/1 (8.8–8.8 s) |

- T14-130 (dev; label expects a question): AAES+ answered once for everyone, 3/3. It states **no hour limits**: its
  only cited page is "Part-time work permit Document guide" (oia.hanyang.ac.kr/notice/1813514), and both facts it
  gives match that page ("Is the employment start date at least 10 days from today?"; "Jobs requiring professional
  skills are NOT permitted under a student visa. (e.g., Marketing, Translation/Interpretation)"). B0 and R16 state
  hour limits from the "Visa" page and the permit guide, and not consistently (B0 run 1: TOPIK 3 → 20 h, TOPIK 4 →
  25 h; run 2: TOPIK 4 → 20 h). Not checked further: those are baselines. test-1 T14-088 was not run.
- **Choice (rule fixed in the brief): D1 with the cleanup**, because T14-130 gave neither a per-case answer nor a
  campus question in all 3 AAES runs.
- D1–D3 unchanged in behaviour: D1 per case, D2 asks the campus then answers the counseling question per degree
  level, D3 refers to the Seoul campus OIA office. The D1 reply has one case with facts, so its seven "ask the
  office" cases stay and only the eight "[No evidence provided]" markers are removed.
- Video: the per-case demo did not change, so `demo_D1_D3_fallback_v6.webm` stays (recorded before the cleanup, so its
  D1 column still shows the markers).

**D1, AAES+ (cleanup on):**

> If you are at Seoul campus with an admitted but not enrolled status, you should ask the OIA office.
> If you are at Seoul campus with an enrolled status, you should ask the OIA office.
> If you are at Seoul campus with a leave of absence status, you should ask the OIA office.
> If you are at Seoul campus with a completed coursework or graduating status, you should ask the OIA office.
> If you are at ERICA campus with an admitted but not enrolled status, you should ask the OIA office.
> If you are at ERICA campus with an enrolled status, you should ask the OIA office.
> If you are at ERICA campus with a leave of absence status, international students must register for group insurance due to strict laws of the Korean Ministry of Health and Welfare, submit the insurance registration certificate when applying for registration, pay a 25,000 Won fee, and access www.isamaster.co.kr/hanyang to click "Insurance applications" (Virtual account on Website); inquiry can be made via KAKAO ID ISACHINA or HYU OIA manager at 031-400-0791~0795. [E1]
> If you are at ERICA campus with a completed coursework or graduating status, you should ask the OIA office.

**D2, AAES+ after "I'm a Seoul campus student." (answering "How do I book the international student counseling program?"):**

> If your degree level is undergraduate, language program, or non-degree, you can visit the Office of International Cooperation (OIA) at Hanyang University for help with psychological and affective problems as well as needs in daily life and study. [E2]
> If your degree level is master or doctoral, you can participate in the International Students Counseling Month program which enriches hearts with 10 international students every session on four topics; please look at the topic and time you want to participate. [E1][E2]
>
> This may depend on your situation; please confirm with the OIA office.

**D3, AAES+:**

> The official pages I found do not apply to you (they are for another campus or student group). Please contact the Seoul campus OIA office.

**T14-130, AAES+ run 1:**

> Yes, you can work part time at Hanyang University under specific conditions. Students must have a valid Alien Registration Card and ensure their employment start date is at least 10 days from today [E1]. Additionally, jobs requiring professional skills such as Marketing or Translation/Interpretation are NOT permitted under a student visa [E1].
>
> This may depend on your situation; please confirm with the OIA office.

### Task 2 · Submission branch (brief v7b)

- Branch `submission` (tip `21b9306`, from `a1f982b`; `hyu-aaes` untouched). Zip: `~/HYU_Compass_submission.zip`
  (`git archive`, 29.9 MB). Removal list: `/tmp/REMOVED_FOR_SUBMISSION.md` (outside the repository).
- 541 files removed, 2 added (the r5 chunk export and its manifest): 1,425 → 886 tracked files; code lines
  (py, ts, tsx, sh, js, css) 45,668 → 22,991. Removed: agent rules and skills, agent task notes, working slide
  folders and demo trials, slide/demo scripts, all test code (98 files) and test-only dependencies; 6 unused imports,
  1 unused variable, 1 unused function. Every preset and code path the report cites is kept.
- Export: `Sources/data/HYU/processed/r5_chunks.jsonl.gz` (1,867 chunks of the r5 index with tags, 0.71 MB,
  0 unmasked e-mails; read-only query) + `r5_chunks.manifest.json`. No kept file is over 50 MB (largest: the 17 MB video).
- Fresh clone of `submission`, installed (npm ci; pip requirements already satisfied), started against the existing
  Docker services and r5 index: preflight 9/9 PASS at `a4bab28`; D1 per case, D2 asks the campus then answers the
  earlier question, D3 refers to the Seoul campus OIA office. The clone folder was then deleted.

### Decisions taken without the user (v7)

1. Merge "ask the office" cases only while at least two cases with facts remain; with one, the reply would read as a
   single answer for one group (and the evaluator agrees), which hides that the answer depends on the student.
2. Markers are removed by two patterns only (upper-case words with an underscore, or a bracketed note about
   evidence/context/information/source/citation), so ordinary brackets such as "[Seoul]" stay.
3. The T14-044 relabel is reported, not worked around.
4. `aaes_prompts.md` is generated from the code (`scripts/deck_v7_prompts.py`) so it cannot drift from the system.
5. Submission built in a separate git worktree instead of `git switch` in the main folder, so the running app and the
   `hyu-aaes` working tree were never changed.
6. Deletions and the dead-code pass were done with scripted `git rm`, ruff, tsc and vulture rather than Codex: Codex hit
   its usage limit at the start of job 3 and made no change; the README was written directly for the same reason.
7. `Report/project/gates.md`, `Report/notes/quality_gpt_check.csv` and `tag_audit_rules.md` are kept because the
   report or the AI-use statement cites them; every script that produces a file the report cites is kept.
8. Docker Desktop was not running at 16:01 (cause unknown; the Mac had not restarted); it was started and the app restarted
   with `start.sh` (no data change).

## Deck v6 (final prep, 2026-11-21)

**Summary.** The follow-up fix is **accepted**: after AAES asks a detail, a reply that only gives the detail now
answers the student's earlier question. Single-turn behaviour is unchanged (94 of 94 dev replies identical with the flag
off and on), and on the Task 2 personas reply-only facts covered rose from 0.000 to 0.205 (AAES) and 0.255 (AAES+) —
post-hoc, dev only. Preflight: all 9 checks pass. Demo: D1–D3 work 3/3 with AAES+; D4 (winter school, dev wording)
still asks the campus 3/3, the known failure. Report §9, §11–§13 and the AI-use statement are updated; the number
check passes (377 checks, 0 mismatches).

### Task 1 · Follow-up fix

- Code: `Sources/backend/app/rag/followup.py` (detection, marker), hooks in `pipeline.run_rag` (effective question;
  the reply's detail merged as a *stated* attribute inside the traced Step 1), `api.py` (validated `followup` marker),
  `config.py` (`followup_resolution`, default on in the app), runner `--followup-resolution` (off unless set);
  frontend sends back the last reply's marker (per preset in compare mode, dropped by "Forget my details") and the
  Execution tab shows "Answering your earlier question: …". Tests: `tests/test_followup.py` (17: the brief's positive
  and negative cases, carried details, end to end with the flag on and off), `src/test/followup.test.ts`.
- Codex review (`codex review`, GPT-6 Sol) found six P2 issues, all fixed before any run: carry earlier resolved
  details forward; imperative openers ("Tell me about … at Seoul") are a new question; "Forget my details" drops the
  marker; compare mode matches markers by preset id; the detail applies when Step 1 is off; the traced profile is the
  one used.
- **Regression** (`Report/results/deck6-regress-off`, `deck6-regress-on`, commit `269eb54`): 47 dev questions × A0 and
  AP_RRRL, LLM cache on: reply types and reply texts identical, 94/94.
- **Dev check** (post-hoc, dev only; `followup_v6/summary.md`, `content.json`, `transcripts.md`; judged blind by
  GPT-6 Sol, v3 prompt, 3 batches of 26):

| Reply only | Facts covered | Wrong fact | Wrong group | Turns per persona | Answer after one reply |
|---|---|---|---|---|---|
| AAES, Phase 4 (before) | 0.000 | 0.000 | 0.080 | 2.79 | 10 of 39 |
| AAES with the fix | 0.205 | 0.136 | 0.269 | 2.64 | 13 of 39 |
| AAES+ with the fix | 0.255 | 0.128 | 0.296 | 2.36 | 14 of 36 |

  Wrong facts and wrong-group answers rise too: before the fix the reply answered another question, so it could not
  be wrong about this one. T14-033: before, "I'm an undergraduate student." got a TOPIK scholarship answer; now AAES+
  answers the asked question (where to apply to return) and says it found no page (retrieval misses it).
- Measured failure, fixed after the check: 3 of 107 detail replies ("I'm a non-degree student.") were not resolved
  because the option matcher missed the hyphen; fixed with a test (`fffb4b2`), not re-run.

### Task 2 · Demo preparation

- Compare columns: B0, R16, **AAES+ (RRRL)**. AP_RRRL was already selectable; it is now shown as "AAES+ (RRRL)" in the
  "Ours (AAES)" group (display only; id and configuration unchanged).
- `Sources/demo_preflight.sh` output (`demo_preflight_v6.txt`):

```
HYU Compass demo preflight  2026-11-21 11:51:53 KST  commit 092638e
PASS  Docker: MongoDB container running
PASS  Docker: Qdrant container running
PASS  Backend up and reaches MongoDB + Qdrant (http://127.0.0.1:8000/api/health)
PASS  Ollama running with qwen3.5:4b
PASS  Index hyu_20261110_97dc1269_r5 present
PASS  Frontend up (http://127.0.0.1:5173)
PASS  Warm-up B0_BASIC_DENSE_RAG: B0 — Basic Dense RAG: answered, 14.8 s
PASS  Warm-up R16_PROMPTED_CONDITIONAL: R16 — Prompted conditional answering: answered, 13.3 s
PASS  Warm-up AP_RRRL: AAES+ (RRRL): CONDITIONAL, 17.1 s
ALL PASS
```

- Rehearsal, 3 runs each, run 1 cold (`demo_trials_v6.csv`, `scripts/deck_v6_demo.py`; reply types by evaluator v2):

| Scenario | Standard dense (B0) | Prompted conditional (R16) | AAES+ (RRRL) |
|---|---|---|---|
| D1 insurance rules | answer 3/3 (7.6–12.6 s) | per case 3/3 (9.2–11.1 s) | per case 3/3 (10.2–13.9 s) |
| D2 counseling | answer 3/3 (0.7–5.6 s) | asks 1/3, answer 2/3 (2.8–8.1 s) | asks 3/3 (1.1–4.1 s) |
| D2 → "I'm a Seoul campus student." | answer 3/3 (5.9–11.4 s) | refers/abstains 2/3, answer 1/3 (4.8–7.6 s) | per case 2/3, answer 1/3 (5.9–12.1 s) |
| D3 Seoul student, pet dog in dorm | refers/abstains 3/3 (2.2–9.3 s) | refers/abstains 3/3 (2.4–9.0 s) | refers/abstains 3/3 (1.2–7.7 s) |
| D4 winter school (dev wording) | answer 3/3 (1.1–5.8 s) | answer 3/3 (2.1–7.5 s) | asks 3/3 (1.1–3.8 s) |

  D2: AAES+ answers the counseling question per degree level after the campus reply, 3/3, with "Answering your
  earlier question" in the trace; B0 and R16 treat the reply as a new question (dorm or "no information"). D3:
  AAES+ refers to "the Seoul campus OIA office" 3/3; B0 and R16 say they found nothing. D4 is the known failure:
  AAES+ asks the campus 3/3 while B0 and R16 answer; T2-011 (held-out wording) was not run.
- Fallback video D1–D3 in compare mode: `Report/slides/deck_v4/demo_D1_D3_fallback_v6.webm` (17 MB, committed;
  recorded after a first take that overlapped a backend reload was discarded, `.run/demo_video_v6_reloaded/`).
  Screenshot: `Report/figures/usability/u17_followup_answer.png` (question, campus question, reply, answer, and
  "Answering your earlier question" in the Execution tab).

### Task 3 · Logs, report, AI use

- `Report/results/TEST_RUNS.md`: the three deck v5 held-out rows now sit under "Held-out runs (deck v5)" with the
  columns Date | Run id | Git SHA | Configs | Reason; no row changed.
- `Report/report/draft.md`: new §11 (AAES+ design, 15-version ablation, selection rule, RRRL), §12 (held-out reply
  types, H1–H3, content by Claude Opus 5.5, gold-evidence wrong-group 0.509, seconds), §13 (Task 2 and the fix);
  §9 adds the LLM-only dev-2/test-3 labels, judge inconsistency, unpaired content rates, 41% over-asking, the 4B
  model, and a privacy paragraph (30-day trace expiry, the delete button, localhost only).
  `Report/notes/check_report_numbers.py` re-derives every new number from committed files: 377 checks, 0 mismatches.
- `Report/ai_use_statement.md`: new "Deck v4–v6" section (Claude Code, Opus 5.5 judges, Codex/GPT-6 Sol, the GPT-6
  Astra/Sol/Terra labels; no person checked dev-2/test-3).

### Decisions taken without the user (v6)

1. The clarify marker travels with the request (`followup` field) instead of being looked up server-side, because the
   API is stateless; the backend validates it (sizes, vocabulary values) and the flag decides whether it is used.
2. Imperative openers (tell, explain, show, give, list, describe) count like question words, after Codex showed
   "Tell me about dormitory fees at Seoul" being resolved back to the counseling question.
3. The dev check's judge items show the effective (earlier) question for resolved replies, so the judge scores the
   reply against what it answered.
4. The first fallback video was discarded because a backend auto-reload (my test edit) happened mid-recording; the
   second take had no reload and all 12 requests completed.
5. Demo method names: only the display name and group of AP_RRRL changed, so held-out results and freezes are untouched.

## Deck v5 (brief v5, 2026-11-20/21)

Label limitation, stated plainly: the dev-2 and test-3 labels are LLM-annotated, LLM-adjudicated and verified by one
model (GPT-6 Astra); no person checked them. All comparisons on them are relative.

**Summary (2026-11-21).** All six phases done and pushed to `hyu-aaes`. AAES+ = `AP_RRRL`. On held-out test-3 + test-2
(215 questions, run once; test-1 never touched) all three pre-registered hypotheses hold: more acceptable reply types
than AAES (+0.084), needed questions/splits kept (−0.030, non-inferior), and far better than prompted conditional
answering on student-dependent questions (+0.471). Over all questions AAES+ is still below every baseline (0.395 vs
0.54–0.67) because it asks or splits on 41% of questions that need one answer. Content (judged blind by Claude Opus
5.5): AAES+ answers cover facts about as well as the baselines, with fewer wrong-group replies on student-dependent
questions; CIs overlap. Demo: Scenario 2 works 3/3 for both; the winter-school question still triggers an unneeded
campus question with AAES+ (3/3), so it is not a success demo.

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
11. **H1 over both held-out sets:** test-3 and test-2 are separate runs; `deck_v5.py heldout` and `judge-items` now take
    several run ids, so H1–H3 are computed over all 215 questions as pre-registered ("all held-out questions run").
12. **Phase 5 judges:** 12 + 5 blind Claude Opus 5.5 subagents (one per batch) instead of one long session, to keep
    batches disjoint and each judge's context to its batch. Some ran a format check (line count, keys) after judging
    by hand; none produced judgments by program. Their split on partly stated facts is reported, not re-judged.
13. **Gold items judged** (usage allowed): 171 G1 replies, same procedure, scored separately (`--gold`).
14. **Demo script** `deck_v5_demo.py` reuses `deck_v4_demo.py` with methods A0 / AP_RRRL and scenarios S5 (winter
    school) and S2; it ran while the judges worked (the judges use no Ollama).

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
- Gold evidence (G1, 171 replies, judged the same way): facts covered 0.609 [0.559, 0.659], citation support 0.837,
  but wrong-group 0.509 on student-dependent questions.
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
