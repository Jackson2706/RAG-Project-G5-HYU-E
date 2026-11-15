# Fact brief v3 for the presentation

For Claude (chat), who builds the deck. Paths are repo-relative. **Post-hoc** = computed after the single test-1 run
from saved outputs; nothing was re-run on test-1 (not even retrieval). New live runs happened only on new questions
(Part 1c) and the demo questions (Part 2c), index `hyu_20261110_97dc1269_r5`, 2026-11-16. Labels are LLM-made and
LLM-checked, never by a person. In slide text use the method names (table at the end), not the codes.

Data in `Report/slides/deck_v3/`: `part1a_branching_cases.csv`, `part1b_wrong_group.json`,
`illustrative_questions.json`, `illustrative_runs.csv`, `illustrative_scores.csv`, `illustrative_comparison.json`,
`judge/` (items, key, judgments), `quotes.csv` (24 verified quotes), `trace_offline.md`, `trace_S1.json`,
`trace_S2_S6.json`, `trace_online.md`, `part3.json`. Scripts: `Sources/scripts/deck_v3_*.py`,
`Sources/scripts/verify_deck_quotes.py`.

---

## PART 1. Underspecified questions: one answer is wrong for some students

### 1a. The 15 student-dependent test-1 cases (`part1a_branching_cases.csv`; v2 reply types, v3 verdicts post-hoc)

Each row has the question, the missing detail(s) from the label, all 13 methods' reply types (v2), the v3 verdict for
the six judged methods (facts covered, wrong fact, wrong group, or question/referral quality), AAES's reply and the
label. Totals: **AAES right on reply type 10 of 15** (v2 acceptability) and **right on content 4 of 15** (v3: a
conditional answer whose conditions match, or a question about the missing detail).

What the baselines got wrong, by pattern (from the CSV):
- One campus's procedure given to everyone (T14-018 psychological test, T14-051 group insurance): all five baselines
  answer; their route or rule holds for one campus only.
- Seoul figures stated for both campuses (T14-088 part-time hours): the baselines split by degree and TOPIK but use the
  Seoul guide's 20/30 h, while ERICA's table says 30/35 h.
- One plain answer where the label wants a conditional answer or a question (T14-014, T14-041, T14-091: all five baselines answer).
- Referral although the pages answer per group (T14-114, T14-124: four baselines refer).
AAES's own misses on these 15: wrong conditions (T14-009, T14-014, T14-091, T14-121), a question about the wrong
detail (T14-041, T14-124), a referral (T14-069, T14-083, T14-224), a plain answer (T14-094, T14-117).

### 1b. Wrong-group replies over all 121 (`part1b_wrong_group.json`; v3, post-hoc; judged only on answered replies)

| Method | Wrong-group replies | Answered replies |
|---|---|---|
| Standard dense retrieval | 18 | 68 |
| Self-query filter | 13 | 67 |
| Prompted conditional answering | 17 | 76 |
| AAES | 5 | 40 |
| Model only, no retrieval | 18 | 90 |
| Gold evidence | 5 | 66 |

AAES has the fewest mostly because it answers least. Where a baseline was wrong-group and AAES was not, AAES usually
asked or referred: against standard dense retrieval, in 16 such cases AAES asked 8 times, gave a conditional answer 4
times, answered once and referred 3 times. The reverse (AAES wrong-group, baseline not): T14-059, T14-202, T14-227
(vs standard dense), plus T14-220 (vs self-query) and T14-091 (vs prompted conditional).

Three clearest cases where the student **stated their group** and a baseline answered for the other group (cited
pages from the saved `cited` chunks):
1. **T14-218** (earlier turns: "I'm returning to Seoul after a leave of absence." / "I'm a degree-seeking
   undergraduate on D-2."; question "Which insurance paper should I prepare?"). Standard dense retrieval and prompted
   conditional answering cite the ERICA return-to-school guide
   (https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=67) and tell the student to pay the insurance
   fee and upload proof. Seoul rule (https://oia.hanyang.ac.kr/notice/1814901): "Enrolled students : Premiums are paid
   in full through Hanyang University’s budget (Students do not need to pay premiums themselves)".
2. **T14-216** (earlier turns: "I'm a fourth-year Seoul undergraduate on leave." / "I want to return for spring 2026.";
   question "What's my next step to come back?"). Standard dense retrieval cites the ERICA 2026 spring
   return-to-school guide (wr_id=79), prompted conditional answering the ERICA 2026 fall guide (wr_id=85). Seoul rule
   (attachment of https://oia.hanyang.ac.kr/notice/1814062): "Application Period: 2026.01.05 (Mon) ~ 01.16 (Fri)" and
   "• ALL: Bank balance certificate and passport copy". AAES referred to the Seoul OIA (label: answer).
3. **T14-065** ("How does the ERICA group visa application work?"). Self-query filter and prompted conditional
   answering cite a 2021 Seoul undergraduate admission guideline (https://oia.hanyang.ac.kr/sub4_01/1162). ERICA rule
   (https://global.hanyang.ac.kr/eng/s3/s3_1.php): "Please check registration notices each semester for information
   regarding group registrations." and "Students who cannot proceed with the group application must visit Hi Korea to
   book their application appointment, and visit the immigration office with all of the documents listed to apply
   separately." AAES asked about academic status (label: refer).

All quotes verified verbatim in snapshot and raw bytes (`quotes.csv`).

### 1c. Ten new underspecified questions (`illustrative_questions.json`, `illustrative_runs.csv`, `illustrative_comparison.json`)

Built on verified rules (`quotes.csv`); none duplicates a test-1 or dev question (nearest content-word Jaccard ≤ 0.62,
different questions). **These questions were written to be underspecified, so they favour a method that asks; they
illustrate, they do not measure.** Each was run 3 times on standard dense retrieval, self-query filter, prompted
conditional answering and AAES (120 runs, all logged), and judged by a fresh Opus 5.5 subagent with the evaluator v3
prompt unchanged, the per-group answers as reference facts, items blind and shuffled (`judge/`). Score per reply
(fixed and committed before judging, `Sources/scripts/deck_v3_illustrative_judge.py`): 2 = right conditions or a
question on a missing detail; 1 = a correct partial answer with no wrong fact or group; 0 = otherwise.

| # | Question | Missing | Standard dense | Self-query | Prompted conditional | AAES (reply type ×3) |
|---|---|---|---|---|---|---|
| I01 | How many hours per week can I work part-time? | campus, degree, TOPIK | 0 | 0 | 0 | 2 (asks degree level) |
| I02 | I don't have TOPIK yet. How many hours am I allowed to work? | campus, degree | 0 | 0 | 1 | 2 (asks degree level) |
| I03 | What TOPIK level do I need to be allowed the full part-time hours? | degree, year | 1 | 1 | 0.33 | 2 (asks degree level) |
| I04 | Do I have to pay for the university group insurance myself? | campus, status | 0 | 0 | 0 | 0 (conditional, wrong conditions) |
| I05 | I finished my coursework but I'm still living in Korea. How do I get insured? | campus | 1 | 1 | 1 | 0 (refers) |
| I06 | How do I take the mental health check for international students? | campus | 0 | 0 | 0 | 2 (asks campus) |
| I07 | How do I get a counseling appointment? | campus | 0 | 0 | 0 | 2 (asks campus) |
| I08 | What is the monthly National Health Insurance premium for international students? | term | 0.67 | 1 | 0.33 | 1 (answers, all years) |
| I09 | What happens if I don't pay my insurance on time? | campus, which insurance | 0 | 0.33 | 0.67 | 2 (asks campus) |
| I10 | If I take a leave of absence, can I stay in Korea? | campus | 0 | 1 | 0 | 2 (asks campus) |

Mean of 3 runs. **AAES vs standard dense retrieval: better 8, same 1, worse 1; vs self-query filter: better 7, same 2,
worse 1; vs prompted conditional answering: better 8, same 1, worse 1.** Why: on 8 questions AAES asked about a
detail the answer depends on in 3 of 3 runs, while the baselines gave one campus's answer (I06: all three gave the
Seoul route "HY-in > Foreign student > 유학생 정신건강 검사") or the Seoul figures (I01). AAES lost on I05 (it found no
relevant chunk and referred, though both campuses answer) and tied on I04 (its conditional answer rested on one ERICA
chunk and sent all Seoul students to the OIA office, as in the test-1 demo S1). On I08 the term is not a vocabulary
attribute, so AAES answered plainly, listing all three premiums.

Recommended slide examples: **I06** (mental health check: AAES asks campus; every baseline gives the Seoul route; the
ERICA route differs), **I01** (part-time hours: baselines give Seoul's 20/30 h; ERICA allows 30/35 h; AAES asks the
degree level), **I05** as the honest loss (AAES refers although both campuses answer).

---

## PART 2. How each component works (the tested AAES, preset A0_AAES)

### 2a. Components

| Component | Code | Input → output | How | Parameters | LLM? | Known failure modes |
|---|---|---|---|---|---|---|
| Crawl | `Sources/crawler/run.py` (`crawler.run`), `fetch.py` | seed URLs, robots.txt → raw bytes + `manifest.jsonl` row (url, sha256, raw_path) | 1) sitemap / board listing; 2) robots check; 3) fetch one at a time ≥ 2.5 s; 4) store bytes once by sha256 | 2 hosts, staff pages denied | rule | 5 × HTTP 403 attachments; image-only posts give no text |
| Clean | `Sources/crawler/extract.py` (`extract_document`, `rows_to_lines`, `mask_email`), `dedup.py` | HTML/PDF/DOCX → English text + spans (heading, paragraph, table_row) | 1) drop script/style; 2) keep blocks with < 5% non-Latin letters; 3) table rows as "header: value; …"; 4) mask e-mails; 5) MinHash dedup → version families | Latin share 0.5/0.7 | rule | one r5 chunk still contains raw HTML (`<div class="dl-box flex-box">…`, ERICA insurance "Enquiries" section): reported, not fixed |
| Chunk | `Sources/backend/app/rag/snapshot.py` (`load_snapshot`), `scripts/ingest_snapshot.py` | snapshot doc → chunks (text, section heading, source spans) | 1) new section at each English heading; 2) cut at span boundaries before max tokens; 3) token windows with overlap | 320 BGE tokens, 48 overlap; 1,867 chunks | rule | a multi-row table can land in one chunk (see tagging) |
| Tag | `.../metadata_extraction/applicability_extractor.py` (`tag_chunk` and `_degree_level`, `_topik_level`, `_any_of`, …) | chunk + title + heading path → condition {campus, scope, constraints, any_of, effective_term, superseded_by}, status | 1) scope national or site campus; 2) one regex rule per attribute (first match); 3) "TOPIK … or IELTS/TOEFL/English track" → alternative sets; 4) cue without rule → status unknown; 5) LLM fallback only in r1 | 9 attributes | rules (r5); qwen3.5:4b fallback r1 only | one tag set per chunk: a table chunk with several rows takes the first row's TOPIK value (example below); 387 chunks "unknown" |
| Index | `ingest_snapshot.py`, `Sources/backend/app/database.py` | chunks → Qdrant vectors + MongoDB chunks/tags + BM25 | embed with BGE, write payload `app_*` fields, VERIFY 15 checks | BAAI/bge-small-en-v1.5, 384-d, cosine, exact search | embedding model | none found by VERIFY (Part 3) |
| Profile (step 1) | `Sources/backend/app/rag/aaes.py` `extract_profile`, `_statements` | question + earlier turns → per attribute {values, status} | regex patterns (campus, visa codes, degree, year, student type, TOPIK, track, status, Korean standard); later statements win; earlier turns = "remembered"; academic status defaults to "not applicant" | patterns in `aaes.py` | rule | the generator does not see earlier turns (only the profile does) |
| Retrieve | `.../retrieval/` dense `qdrant_cosine`, lexical `bm25`, fusion `rrf` | question → ≤ 20 candidates with dense, BM25, RRF scores | dense top 10 + BM25 top 10 → reciprocal rank fusion | top 10 + 10, RRF k = 60, keep 20 (18 unique in S1) | rule | lexical matches on Korean-titled notices |
| Labels + rerank (step 2) | `.../reranking/applicability_reranker.py` `rerank`; `aaes.py` `label_chunk`, `penalized_score`; `applicability.py` `condition_fit` | candidates + profile → reranked list, label per chunk | 1) cross-encoder logit per (question, chunk); 2) label: conflicting / compatible / open / unconditioned / unknown; 3) score − 4 × conflicting − 2 × outdated; 4) sort | cross-encoder/ms-marco-MiniLM-L6-v2, depth 20, λ = 4, μ = 2 | cross-encoder (not an LLM) | soft penalty keeps conflicting chunks (applicability precision@3 0.537, Part 3) |
| Evidence + relevance check | `.../evidence_selection/` top_k; `applicability_sufficiency.py` `relevant_chunks`; `text.py` `query_coverage` | reranked → top 3; relevant = coverage ≥ 0.30 | share of question content words in the chunk | top_k 3, threshold 0.30 | rule | lexical: in S1 only 1 of 3 chunks passes, so all branching rests on one chunk |
| Branching (step 3) | `aaes.py` `information_gain`, `_condition_attributes`, branch table in `decide` | relevant chunks + profile → per unknown attribute: chunks that apply per value; information score; joint branch table | for each unknown attribute (campus always): for each value, which chunks are not conflicting; entropy of those sets | — | rule | compares chunk sets, not answers; empty branches count |
| Decision (step 4) | `aaes.py` `decide` | branch table → ANSWER / CONDITIONAL / CLARIFY / ABSTAIN / CONFIRM + reason | see the deck v2 table: no relevant chunk → refer; stale value → confirm; no branch → answer; > 3 branches → ask; > 1 document → ask; else conditional | max_branches 3 | rule | asks before checking that evidence answers |
| Reply writing | `.../context_construction/standard_context.py`, `aaes.py` `branch_note`, `.../generation/ollama_generator.py`; templates `render_action` | evidence (+ branch note) → reply; or fixed template | CONDITIONAL adds "Answer every case below separately…" with per-branch evidence labels | qwen3.5:4b, temp 0, seed 42, max 1,024 tokens, context 4,096 | LLM (answers); templates for ask/refer/confirm | empty branch becomes "ask the OIA office" |
| Citations | `pipeline.py` `attach_sources`, `aaes.py` `with_caveat` | reply text → sources with [E#] → chunk, cited flag | parse [E#] markers; append caveat when evidence status is unknown | — | rule | an answer without markers is scored over all evidence |

**The 9 attributes and their allowed values** (`Sources/backend/app/rag/applicability.py`): campus: seoul, erica;
degree_level: undergraduate, master, doctoral, language_program, non_degree; year: 1-4 (undergraduate); student_type:
degree_seeking, exchange, visiting, language_program; visa: D-2, D-2-5, D-2-8, D-4, D-10, other; topik_level: none,
1-6; english_track: yes, no; academic_status: applicant, admitted_not_enrolled, enrolled, leave_of_absence,
completed_coursework, graduating; korean_standard: pass, exempt, fail.

**How a tag is extracted, two real examples (index r5):**
1. ERICA "Permitted Hours" chunk, text "University Type: Bachelor's; Year: Year 1-2; Korean Language Proficiency Level:
   Level 3; Korean Language Proficiency Level: X; … Permitted Hours / Weekdays: 10 hours …" (and further rows). The
   TOPIK rule (`_topik_level`) matches "Level 3 … : X" = not met → **topik_level none/1/2**; the degree and year rules
   add degree_level undergraduate/master/doctoral and year 1-4. Failure: the same chunk also holds the rows for
   students *with* level 3 (30 h), but one tag set covers the whole chunk, so a TOPIK-3 student is "conflicts".
2. ERICA insurance chunk "KRW 25,000 (same premium for undergraduate and graduate schools)" → the degree rule matches
   "undergraduate" and "graduate" → **degree_level undergraduate/master/doctoral**, campus erica (site default)
   (`trace_offline.md`).

**Condition sets ("TOPIK or English track").** `_any_of` looks for one sentence with a TOPIK threshold or "TOPIK
certificate", then "or", then IELTS/TOEFL/TEPS/English track, and stores two alternative sets, e.g. a Seoul HIEA
scholarship chunk: `any_of = [{topik_level: 1-6}, {english_track: yes}]`. `condition_fit` treats a chunk as
compatible if any set fits, conflicting only if every set conflicts, otherwise "depends". 6 chunks in r5 have such sets.

### 2b. Offline trace (`trace_offline.md`)

The ERICA "International Student Insurance" page (https://global.hanyang.ac.kr/eng/s3/s3_2_1.php): raw HTML snippet
around the premium table → cleaned snapshot text → its **10 chunks** (headings, token counts) → full tags of chunk 2
(premium: campus erica, degree_level undergraduate/master/doctoral, status conditioned, rule) and chunk 5 (penalties:
campus erica, no constraints, status unknown: a cue but no rule).

### 2c. Online traces (`trace_S1.json`, `trace_S2_S6.json`, readable: `trace_online.md`)

- **S1 "Which insurance rules apply to me?"** Profile: everything missing; academic status = scope default. 18 unique
  candidates after RRF (dense and BM25 top 10 overlap). Labels: depends / unknown / conflicts per chunk, with the
  tags. Top 3: two ERICA insurance pages and the ERICA return-to-school guide; coverage 0.25 / 0.75 / 0.25, so only
  the return-to-school chunk is relevant. Branches: campus (information 1.0: Seoul → 0 chunks, ERICA → 1) and
  academic status (0.72). Decision CONDITIONAL (few branches). The branch note sends the Seoul / other-status case to
  "no evidence: say the student should ask the OIA office". Final reply: per campus and status.
- **S2 counseling question, no profile**: branches on campus and degree level; the chunks come from more than one
  document → CLARIFY on campus (different procedures), fixed template, no LLM call.
- **S6 same question after "I'm a Seoul campus student."**: profile campus = seoul (remembered, from the earlier
  turn); campus no longer branches; degree level splits two Seoul chunk sets → CONDITIONAL.

---

## PART 3. Evaluations that follow Lessons 3-6 (`part3.json`, post-hoc unless stated)

### Lesson 3: the index

- **15 verification checks, r5, all pass** (`Report/results/index_reports/hyu_20261110_97dc1269_r5.json`):
  documents_expected, chunks_equal_points, dimension_384, chunk_ids_unique, every_point_has_chunk, max_tokens_le_512,
  truncated_zero, applicability_valid, llm_errors_zero, partition_complete, span_text_matches,
  payload_has_scope_campus, no_unmasked_emails, no_hangul_headers, default_index_unchanged. Facts: 362 documents,
  1,867 chunks = 1,867 points, max 344 embedded tokens, 0 truncated, 0 span mismatches, 0 unmasked e-mails.
- **r1 → r5** (`Sources/data/DATA.md` §5): r1 first build (vocabulary v0, 772 LLM calls); r2 TOPIK thresholds stored as
  ranges (0 new LLM calls); r3 vocabulary v1 + post-check fixes; r4 audit fixes, rules only, new "unknown" bucket;
  r5 degree level from the guide title and other rule fixes, rules only. Tag partition r5: 1,189 rule-tagged, 291
  rule-unconditioned, 387 unknown.
- **Crawl** (`DATA.md` §1-2): 1,423 requests in 59 min, all HTTP 200 except 5 × 403 (attachments of one Seoul page);
  robots.txt excluded nothing; staff pages denied by configuration; 362 English documents, 306 Seoul, 56 ERICA.
- **Chunk lengths** (BGE tokens, r5): min 1, p25 217, median 320, p75 320, max 320, mean 257.3; 1,169 chunks reach
  the 320 cap, 131 are under 40 tokens.
- **Rebuild determinism**: r4 and r5 have the same 1,867 chunk ids and identical texts (only tags changed between
  them).

### Lesson 4: retrieval vs response (saved top-10 ranked chunks of test-1; 98 cases with gold spans)

| Method | Gold hit@3 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Applicability precision@3 |
|---|---|---|---|---|---|---|
| Standard dense retrieval | 0.459 | 0.395 | 0.469 | 0.469* | 0.402 | 0.518 |
| Hybrid with reranker | 0.408 | 0.343 | 0.428 | 0.523 | 0.393 | 0.413 |
| Scope filter | 0.439 | 0.367 | 0.463 | 0.569 | 0.434 | 0.551 |
| Self-query filter | 0.439 | 0.336 | 0.411 | 0.495 | 0.400 | 0.667 |
| Prompted conditional | 0.408 | 0.343 | 0.428 | 0.523 | 0.393 | 0.413 |
| AAES | 0.449 | 0.370 | 0.459 | 0.550 | 0.421 | 0.537 |
| AAES, hard filter | 0.459 | 0.380 | 0.461 | 0.525 | 0.422 | 0.574 |
| AAES, true profile | 0.439 | 0.368 | 0.467 | 0.541 | 0.426 | 0.518 |

\* standard dense retrieval keeps only 5 chunks, so @10 = @5. Always-ask, question-wording and no-newest-notice
ablations retrieve exactly like AAES. **Recall@20 cannot be computed: only the top 10 chunks were saved per case**, and
test-1 may not be re-run. Applicability precision@3 = share of top-3 evidence whose tags do not conflict with the
case's labelled student profile (`label_chunk`). Citation support (v3, `Report/results/quality_v3/metrics_test.csv`):
gold evidence 0.880, standard dense 0.573, self-query 0.561, prompted conditional 0.520, AAES 0.506. No retrieval /
normal / gold (facts covered, v3): 0.079 / 0.300 / 0.463.

### Lesson 5: deciding to proceed (v2; full 4×4 matrices per method in `part3.json` `l5_confusion`)

| Method | "Should not answer plainly": precision / recall | Over-asking (asked or branched when a plain answer was expected) | Answered share | Wrong fact among answered (v3) |
|---|---|---|---|---|
| Standard dense | 0.574 / 0.508 | 0.017 | 0.562 | 0.279 |
| Hybrid with reranker | 0.558 / 0.475 | 0.000 | 0.570 | not judged |
| Scope filter | 0.540 / 0.443 | 0.000 | 0.587 | not judged |
| Self-query | 0.574 / 0.508 | 0.000 | 0.554 | 0.313 |
| Prompted conditional | 0.582 / 0.525 | 0.083 | 0.628 | 0.237 |
| Model only | 0.545 / 0.295 | 0.017 | 0.744 | 0.511 |
| Gold evidence | 0.691 / 0.623 | 0.000 | 0.545 | 0.045 |
| **AAES** | 0.527 / **0.951** | **0.617** | 0.331 | **0.125** |
| AAES, always asks | 0.522 / 0.967 | 0.667 | 0.066 | not judged |
| AAES, question wording | 0.527 / 0.639 | 0.217 | 0.388 | not judged |

"Should not answer plainly" = expected refer, conditional or ask (61 cases). AAES's matrix (expected → reply): answer →
answer 8, conditional 17, ask 20, refer 15; refer → refer 11, ask 27, conditional 7, answer 1; conditional → conditional
2, ask 3, refer 3, answer 1; ask → ask 2, conditional 3, answer 1. Risk-coverage points (answered share, wrong fact
among answered): standard dense (0.562, 0.279), self-query (0.554, 0.313), prompted conditional (0.628, 0.237), AAES
(0.331, 0.125), model only (0.744, 0.511), gold evidence (0.545, 0.045).

Prefilter vs hard filter vs soft penalty: scope filter (prefilter before search) acceptable 0.653, applicability
precision@3 0.551; AAES hard filter 0.256, 0.574; AAES soft penalty 0.256, 0.537. Removing conflicting chunks raised
applicability precision only slightly and did not change acceptable action (paired diff 0.000 [−0.025, +0.025]).

### Lesson 6: methodology

**Timeline (git):** labels frozen (dev 47 / test 121 / excluded 12) at 6cdaf0b, 2026-11-13 11:10; config freeze tag
`config-freeze` at c556bb5, 11-13 14:09 (best baseline = self-query, from dev); single test run started at eaa8b55
(11-13), resumed once after the Mac slept (1c64d7b, logged in `Report/results/TEST_RUNS.md`); evaluator v2 frozen on
dev at facacc3 (11-14 11:18), test re-scored afterwards; test-2 frozen at 3ef55a3 (11-14 15:50); AG dev gate NO-GO at
367ca4a (11-14 16:02); evaluator v3 judge prompt frozen at c0b2a70 (11-14 16:24) before any test reply was judged.

**Pre-registered hypotheses (test-1):**

| # | Hypothesis | Effect | 95% CI | p | Holm p | Result |
|---|---|---|---|---|---|---|
| 1 | AAES has fewer wrong-group answers than self-query (conditional + temporal) | 0.000 (2 comparable cases) | [0, 0] | 1.0 | 1.0 | no result |
| 2 | AAES is non-inferior to self-query on correctness (unconditional, 3-point margin) | −0.185 (v3, post-hoc) | [−0.312, −0.065] | 0.0065 | (not in the original Holm family) | fails |
| 3 | AAES beats "deciding from the question wording" on action macro-F1 | −0.066 (v2) | [−0.132, +0.005] | 0.154 | 0.463 | fails |

Sources: `Report/results/test-final/hyu_test_v2_comparisons_paired.csv`, `Report/results/quality_v3/comparisons.csv`.

**Paired bootstrap, acceptable-action rate (v2), AAES minus each method** (`part3.json` `l6_paired_acceptable_v2`):
standard dense −0.405 [−0.521, −0.281]; hybrid with reranker −0.397 [−0.512, −0.273]; scope filter −0.397 [−0.512,
−0.273]; self-query −0.405 [−0.521, −0.281]; prompted conditional −0.372 [−0.488, −0.248]; model only −0.413 [−0.529,
−0.298]; gold evidence −0.463 [−0.579, −0.339]; all p = 0.0001.

**Ablations** (what changed; acceptable-action delta = AAES minus the variant, v2):

| Variant | What changes | Delta [95% CI] | p |
|---|---|---|---|
| AAES with a hard filter | conflicting chunks removed, not demoted | 0.000 [−0.025, +0.025] | 1.0 |
| AAES with the true profile | step 1 replaced by the labelled stated profile | −0.017 [−0.058, +0.025] | 0.69 |
| AAES that always asks | asks whenever a detail is unknown | +0.017 [−0.017, +0.050] | 0.63 |
| AAES deciding from the question wording | asks only if the question names a detail | −0.215 [−0.322, −0.107] | 0.0003 |
| AAES without the newest-notice rule | old notice versions count like new | −0.008 [−0.025, 0.000] | 1.0 |

**Slices (acceptable action, v2, `l6_slices_acceptable_v2`)**: by campus, AAES 0.176 Seoul (74 cases) / 0.383 ERICA
(47) vs standard dense 0.689 / 0.617; by slice, AAES 0.239 unconditional, 0.370 conditional, 0.167 temporal, 0.292
negative, 0.083 multi-session vs standard dense 0.587 / 0.556 / 0.583 / 0.917 / 0.750; by missing detail (cases whose
label lists it): campus 0.667 vs 0.333 (9 cases), degree level 0.500 vs 0.000 (6), academic status 0.667 vs 0.167
(6), year 0.750 vs 0.000 (4), TOPIK 0.500 vs 0.000 (4). By expected action: `Report/results/test-final/posthoc.md`.

**Evaluator versions.** v1 → v2 acceptable (`l6_v1_vs_v2_acceptable`): standard dense 0.736 → 0.661, prompted
conditional 0.694 → 0.628, gold evidence 0.818 → 0.719, AAES 0.248 → 0.256: v1 inflated the baselines (it could not
see that a reply only said what was missing). v2 validation κ = 0.899 (blind Opus labeller, 100 dev replies). v3
validation: Sonnet 5.5 κ facts 0.859, wrong group 0.854, referral 0.791, citation 0.656 (100 dev); GPT-6.1 in
ChatGPT facts κ 0.679, wrong group 1.0 (20 dev) (`Report/results/quality_v3/validation.json`). Label agreement
before adjudication: answerability κ 0.559 and 0.425, expected behaviour 0.683 and 0.666 (`Report/results/labels/`).

**AAES error taxonomy on test-1** (90 replies not acceptable under v2; first matching category; `l6_a0_error_taxonomy`):

| Category | Count | Examples |
|---|---|---|
| Asked instead of referring (label: refer) | 27 | T14-002, T14-004, T14-005 |
| Split into cases when one answer was expected | 23 | T14-016, T14-022, T14-030 |
| Referred when an answer existed | 17 | T14-006, T14-040, T14-048 |
| Unneeded or wrong detail asked (not campus) | 11 | T14-003, T14-021, T14-055 |
| Unneeded campus question | 9 | T14-011, T14-013, T14-024 |
| Answered when it should refer or branch | 3 | T14-094, T14-117, T14-165 |

Plus 5 "thin answers": acceptable answer type but under half the required facts (v3), e.g. T14-073, T14-110. Campus
questions also occur inside "asked instead of referring" (first-match rule).

---

## Code → name

| Code | Name | What it is |
|---|---|---|
| B0 | Standard dense retrieval | Dense search top 5, top 3 evidence, standard prompt. |
| R5 | Hybrid retrieval with reranker | Dense 10 + BM25 10, RRF (k 60) top 20, cross-encoder MiniLM-L6, top 3. |
| R9S | Scope filter | Hybrid with reranker plus a pre-search filter on what the student stated. |
| R15 | Self-query filter | Hybrid with reranker plus an LLM that writes the stated profile as a filter. |
| R16 | Prompted conditional answering | Hybrid with reranker; the prompt asks for per-case answers or one question. |
| G0 | Model only, no retrieval (reference) | The generator answers from memory. |
| G1 | Gold evidence (upper reference) | The generator gets the labelled gold evidence. |
| A0 | AAES (ours) | Rule profile, hybrid retrieval, applicability penalty, branches by which chunks apply, decision. |
| A1 | AAES with a hard filter | Conflicting chunks removed instead of demoted. |
| A2 | AAES with the true profile | Step 1 replaced by the labelled stated profile. |
| A3 | AAES that always asks | Asks whenever a detail of a relevant chunk is unknown. |
| A4 | AAES deciding from the question wording | Asks only when the question's words name a detail. |
| A6 | AAES without the newest-notice rule | Old versions of a notice count like the newest. |

## Could not compute or verify

- Recall@20 on test-1: only 10 ranked chunks per case were saved; test-1 may not be re-run.
- v3 content metrics for hybrid with reranker, scope filter and the AAES ablations (v3 judged six methods).
- Which model the self-query filter's LLM call used during the test run (empty setting).
- The 1c comparison is illustrative: questions written by us to be underspecified, one LLM judge, 3 runs.
- Reported, not fixed: one r5 chunk contains raw HTML; multi-row table chunks get one tag set (TOPIK example in 2a);
  the generator does not see earlier turns (only the profile does).
- No person checked labels or judgments.

Commit: see the next line, added after the commit.
