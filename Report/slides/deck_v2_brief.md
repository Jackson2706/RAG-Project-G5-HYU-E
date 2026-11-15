# Fact brief for presentation v2

For Claude (chat), who builds the deck. Every number names its source file (paths are repo-relative). Numbers marked
**post-hoc** were computed after the test run from saved replies; nothing was re-run on test-1. Labels are written
and checked by LLMs only (no human verification). In slide text, use the method names in the last table, not the
codes.

Data files in `Report/slides/deck_v2/`: `quotes.csv` (every page quote, verified), `counts_1c.json`,
`reply_types_test1_v2.csv`, `branching_cases_test1.csv`, `section5_posthoc.json`, `pipeline.mmd`, `demo_trials.csv`.

---

## Section 1. Why this problem matters at HYU

### 1a. Rules whose right answer depends on the student

Every quote below was checked verbatim (whitespace collapsed) against the frozen snapshot text and against the raw
crawled bytes (`Report/slides/deck_v2/quotes.csv`, made by `Sources/scripts/verify_deck_quotes.py`; 21 of 21 found
in both). The two ERICA part-time rows come from a table: the page shows table cells, so the quote lists the cells.

1. **Part-time work hours: campus, degree level and TOPIK.**
   - Seoul guide (attachment of https://oia.hanyang.ac.kr/notice/1813514, posted 2025-10-15): "The number of
     allowed hours for part-time work (For those submitting the Korean language proficiency standard) is 20 hours
     per week for language training students, 20 hours per week for undergraduate students (25 hours for
     IEQAS-certified universities), and 30 hours per week for masters/doctoral degree students."
   - ERICA visa page (https://global.hanyang.ac.kr/eng/s3/s3_1.php), "Permitted Hours" table: Bachelor's, Year 1-2,
     Korean level 3 met: **30 hours** on weekdays, no restriction on weekends and school holidays. Master's/Doctoral,
     Korean level 4 met: **35 hours** on weekdays, no restriction on weekends and holidays.
   - Differing values: an undergraduate with the Korean standard reads 20 h/week (Seoul guide) or 30 h on weekdays
     (ERICA table); a graduate student reads 30 h or 35 h.
2. **Part-time work hours without the Korean standard.**
   - Seoul guide (same attachment): "In case the Korean language proficiency standard is not fulfilled, the number of
     allowed work hours is limited to 10 hours for language training/undergraduate students, and 15 hours for
     masters/doctoral degree students"
   - ERICA table: Bachelor's, Year 1-2, Korean level 3 not met: **10 hours** weekdays, **10 hours** weekends.
   - Differing values: 10 h versus 30 h (undergraduate) depends on the TOPIK level alone.
3. **The Korean standard itself depends on degree and year.** Seoul guide (same attachment): "Korean language
   proficiency standard (TOPIK): Language training level 2, Associate degree level 3, Bachelor's degree (1st-2nd
   year) level 3, Bachelor's degree (3rd-4th year) level 4, Masters/doctoral degree level 4 or higher"
4. **University group insurance: campus.**
   - Seoul (https://oia.hanyang.ac.kr/notice/1814901, posted 2026-03-06): "Enrolled students : Premiums are paid in
     full through Hanyang University’s budget (Students do not need to pay premiums themselves)"
   - ERICA (https://global.hanyang.ac.kr/eng/s3/s3_2_1.php): "University Group Insurance Premium KRW 25,000 (same
     premium for undergraduate and graduate schools)" and "Students must pay their insurance premium (lump-sum) when
     paying for their tuition"
   - Differing values: an enrolled Seoul student pays nothing; an ERICA student pays KRW 25,000 with tuition.
5. **University group insurance: academic status.**
   - Seoul (same notice): "Students who completed coursework : Students who wish to enroll in insurance, they must pay
     directly the premiun of 25,000 won themselves." (sic)
   - ERICA (same page): "Returning students who took a leave of absence after paying tuition or those who completed
     the course residing in Korea must subscribe to the insurance individually through the insurance company's
     website"
6. **National Health Insurance premium: term.**
   - https://oia.hanyang.ac.kr/notice/1814881: "OIA would like to inform students of the contents of the National
     Health Insurance System for International Students that was applied from March 1, 2026. - Monthly Insurance
     premium: 76,390 won → 79,320 won"
   - https://oia.hanyang.ac.kr/notice/1812000: "… that was applied from March 1, 2025. - Monthly Insurance premium:
     75,490 won → 76,390 won"
   - Differing values: 79,320 won from March 2026, 76,390 won in the year before.
7. **Psychological health test: campus.**
   - Seoul (https://oia.hanyang.ac.kr/notice/1814943, posted 2026-03-09): "Eligibility: International undergraduate &
     graduate students at Seoul campus 🍀Period: Throughout March 🍀Language: Korean, English, Chinese 🍀Time
     required: About 1-2 minutes 🍀How to take the test: Log into HY-in > Foreign student > 유학생 정신건강 검사"
   - ERICA (https://global.hanyang.ac.kr/eng/s3/s3_5_1.php): "Reservation Instructions Hanyang University Web Portal
     HY-in -> Application -> Personal Counseling/Psychological Testing"
8. **Leave of absence: status (ERICA).** Attachment of
   https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=78 (posted 2025-12-22): "Those who apply for
   the leave of absence must leave Korea within 30 days, regardless of their visa validity periods."

### 1b. Consequences the pages state

- Working without a permit (Seoul part-time guide, attachment of https://oia.hanyang.ac.kr/notice/1813514): "Both
  students and employers may be subject to punishment if working before obtaining a part-time work permit.
  (Employment activities are allowed only at a permitted workplace)"
- A past violation blocks a new permit (ERICA visa page, https://global.hanyang.ac.kr/eng/s3/s3_1.php, in its list of
  restricted applicants): "Applicants who have not received a part-time work permit or have a history of violating
  the conditions of the permit"
- Unpaid group insurance at ERICA (https://global.hanyang.ac.kr/eng/s3/s3_2_1.php): "Failure to pay the insurance
  premium within the tuition payment period will render the student unable to enroll and thus be expelled from the
  university"
- Unpaid National Health Insurance (https://oia.hanyang.ac.kr/notice/1814881): "Failure to pay National Health
  Insurane will result in disadvantages in the immigration office's review of extension of stay period, so please pay
  by the deadline." (sic)
- A forged advisor form for a visa extension (https://oia.hanyang.ac.kr/notice/1808902, Korean title, English text):
  "This is an act of document forgery and whoever commits this crime shall be punished with fine or deportation from
  Korea."

No page in the snapshot states a penalty specifically for working more hours than permitted; the closest statements
are the first two above.

### 1c. Counts (`Report/slides/deck_v2/counts_1c.json`, index `hyu_20261110_97dc1269_r5`, 1,867 chunks)

The 9 vocabulary-v1 attributes (`Sources/backend/app/rag/applicability.py`): campus, degree_level, year,
student_type, visa, topik_level, english_track, academic_status, korean_standard.

| Attribute | Chunks tagged |
|---|---|
| campus (one campus only) | 1,775 |
| degree_level | 1,039 |
| academic_status | 950 |
| topik_level | 274 |
| student_type | 204 |
| visa | 88 |
| english_track | 45 |
| year | 34 |
| korean_standard | 4 |

- Chunks with a condition other than campus: 1,189 of 1,867; 6 have alternative condition sets ("TOPIK or English
  track"). Condition status: 1,189 conditioned, 291 unconditioned, 387 unknown.
- The academic_status count is large because the tagger marks pages written for applicants (or for enrolled
  students) by status; a chunk can carry several attributes.
- Test-1 questions whose right answer depends on the student: **15 of 121** (9 labelled conditional answer,
  6 labelled ask a question). Attributes they depend on (one case can depend on several): campus 6, degree_level 6,
  academic_status 5, year 4, topik_level 4, korean_standard 1, visa 1, english_track 1. Read from the frozen labels
  through the runner's reader (`evaluation.hyu_suite.load_cases`).

---

## Section 2. Baselines answer as if they know who is asking (test-1 saved replies)

### 2a. Reply types under evaluator v2 (`Report/slides/deck_v2/reply_types_test1_v2.csv`, from `Report/results/test-final/hyu_test_v2_per_case.csv`)

| Method | Answer | Conditional answer | Question | Referral |
|---|---|---|---|---|
| Standard dense retrieval | 67 | 1 | 0 | 53 |
| Hybrid retrieval with reranker | 69 | 0 | 0 | 52 |
| Scope filter | 71 | 0 | 0 | 50 |
| Self-query filter | 67 | 0 | 0 | 54 |
| Prompted conditional answering | 66 | 10 | 0 | 45 |
| Model only, no retrieval | 88 | 2 | 0 | 31 |
| Gold evidence | 66 | 0 | 0 | 55 |
| **AAES (ours)** | 11 | 29 | 52 | 29 |
| AAES with a hard filter | 12 | 29 | 54 | 26 |
| AAES with the true profile | 11 | 28 | 48 | 34 |
| AAES that always asks | 8 | 0 | 86 | 27 |
| AAES deciding from the question wording | 47 | 0 | 26 | 48 |
| AAES without the newest-notice rule | 12 | 28 | 52 | 29 |

Takeaway: no retrieval method ever asks the student a question, and only the prompted method gives per-case answers
(10 of 121); AAES asks on 52 cases and answers per case on 29.

### 2b. The 15 student-dependent cases (`Report/slides/deck_v2/branching_cases_test1.csv`)

In **6 of 15** cases all five retrieval baselines gave one plain answer and AAES gave a conditional answer or a
question: T14-014, T14-018, T14-041, T14-051, T14-088, T14-091.

| Case | AAES | Always-ask ablation | Evaluator v3 on AAES (post-hoc) |
|---|---|---|---|
| T14-014 | conditional answer | question | conditions do not match the evidence; no wrong-group information |
| T14-018 | question | question | asks about the attribute the answer depends on (campus) |
| T14-041 | question | question | asks about an attribute the answer does not depend on |
| T14-051 | question | question | asks about the attribute the answer depends on (campus) |
| T14-088 | question | question | asks about the attribute the answer depends on (degree level) |
| T14-091 | conditional answer | question | conditions do not match; contains wrong-group information |

So in 3 of the 6, AAES's question was the right one by the v3 judge; in the other 3 the reply type was right but
the content was not. The always-ask ablation also asked in all 6.

### 2c. The three clearest cases

**T14-018 "How can I take the psychological health test?"** Depends on: campus. Label: conditional answer (a
question is also accepted).
- Standard dense retrieval: "You can take the Psychological Health Test by logging into HY-in, navigating to Foreign
  student, and selecting 유학생 정신건강 검사 …"
- Hybrid retrieval with reranker, Scope filter and Self-query filter (identical): "You can take the test by logging
  into HY-in and navigating to Foreign student > 유학생 정신건강 검사 [E1][E2][E3]."
- Prompted conditional answering: "You can take the Psychological Health Test by logging into HY-in and navigating
  to **Foreign student > 유학생 정신건강 검사** …"
- AAES: "The answer depends on your campus. Which applies to you: Seoul or ERICA?"
- Why one answer is wrong for some students: the Seoul notice limits that route to Seoul students ("Eligibility:
  International undergraduate & graduate students at Seoul campus … Log into HY-in > Foreign student > 유학생 정신건강
  검사", https://oia.hanyang.ac.kr/notice/1814943); ERICA students book through "HY-in -> Application -> Personal
  Counseling/Psychological Testing" (https://global.hanyang.ac.kr/eng/s3/s3_5_1.php).

**T14-051 "How do I sign up for the university group insurance?"** Depends on: campus and academic status. Label: ask
a question.
- Standard dense retrieval: "To sign up for the university group insurance, students must pay their insurance
  premium as a lump sum when paying for their tuition. [E3] …" (the ERICA rule)
- Hybrid retrieval with reranker and Scope filter: "Students who took a leave of absence after paying tuition or
  those who completed the course residing in Korea must subscribe to the insurance individually …" (the ERICA
  status rule)
- Self-query filter: "Enrolled students do not need to sign up; premiums are paid in full through Hanyang
  University's budget …" (the Seoul rule)
- Prompted conditional answering: "To sign up for the university group insurance, you must pay your insurance
  premium as a lump-sum when paying for your tuition. …" (the ERICA rule)
- AAES: "The answer depends on your campus. Which applies to you: Seoul or ERICA?"
- Why one answer is wrong for some students: rule 4 in 1a (Seoul budget pays; ERICA KRW 25,000 with tuition). Four
  baselines gave the ERICA procedure to everyone, one gave the Seoul procedure to everyone.

**T14-088 "How many hours can an international student work part time?"** Depends on: degree level, year, TOPIK.
Label: ask a question (conditional answer also accepted).
- All five baselines list hours by degree and TOPIK, with the Seoul guide's figures, for example: "**20 hours per
  week** for undergraduate students … **30 hours per week** for masters/doctoral degree students." (Hybrid retrieval
  with reranker; Scope filter and Self-query filter identical; Standard dense retrieval and Prompted conditional
  answering give the same figures.)
- AAES: "The answer depends on your degree level. Which applies to you: undergraduate, master, doctoral, language
  program or non degree?"
- Why one answer is wrong for some students: at ERICA the same student reads 30 h on weekdays (bachelor's, Korean
  level 3) and 35 h (master's/doctoral, level 4) (rule 1 in 1a). Note: the baselines do split by degree; what they
  miss is that the figures are campus-specific.

---

## Section 3. The AAES pipeline as tested (AAES (ours), the version with test results)

Sources: `Sources/backend/app/rag/aaes.py`, `Sources/backend/app/rag/presets.py` (A0_AAES),
`Sources/backend/app/rag/blocks/evidence/`, `Sources/scripts/ingest_snapshot.py`, the A0 task config in
`Report/results/test-final/status.json`. Diagram: `Report/slides/deck_v2/pipeline.mmd`.

### 3a. Stages

| Stage | Input | Output | LLM or rule | Key parameters |
|---|---|---|---|---|
| Crawl | 2 English OIA sites | raw pages and attachments | rule | robots.txt, 1 request per 2.5 s, 2026-11-10; 1,423 requests (`Sources/data/DATA.md` §2) |
| Clean | raw bytes | English text blocks | rule | Latin-letter filter, e-mail mask, dedup, version families (§3) |
| Snapshot | cleaned pages | 362 documents (306 Seoul, 56 ERICA) | rule | frozen, sha256-checked (§4) |
| Chunk | snapshot | 1,867 chunks | rule | section-aware, 320 BGE tokens, 48 overlap (`ingest_snapshot.py`) |
| Applicability tagging | chunk + heading | condition: campus, attribute constraints, status | rules first; LLM fallback | r1 used qwen3.5:4b (772 calls, cached); the tested index r5 is rules only (`DATA.md` §5) |
| Index | chunks | Qdrant vectors + MongoDB chunks and tags + BM25 | rule (embedding model) | BAAI/bge-small-en-v1.5, 384-d, cosine, exact search |
| Step 1 Profile | question + earlier turns | per attribute: stated, remembered, stale, scope default or missing | rules, no LLM | regex patterns in `aaes.py` |
| Retrieval | question | 20 candidates | rule | dense top 10 (exact cosine) + BM25 top 10, RRF k = 60, keep 20 |
| Step 2 Labels and penalty | candidates + profile | reranked list with a label per chunk | cross-encoder (not an LLM) | cross-encoder/ms-marco-MiniLM-L6-v2, depth 20; score − 4 × conflicting − 2 × outdated; nothing removed |
| Evidence selection | reranked list | top 3 chunks | rule | top_k = 3; "relevant" = query-word coverage ≥ 0.30 |
| Step 3 Branches | relevant chunks + profile | branch table, information gain per attribute | rule | see 3b |
| Step 4 Decision | branch table | action | rule | max_branches = 3; see 3c |
| Generation | question (+ branch note) + evidence | reply with [E#] citations | LLM | qwen3.5:4b, temperature 0, seed 42, top_p 0.9, top_k 40, max 1,024 tokens, context 4,096, thinking off |
| Template reply | action | fixed text for question, referral or confirm | rule | no LLM call |

### 3b. Step 3 as built

For each student attribute that is not known, plus the campus, which is always a candidate (`_condition_attributes`
starts from campus): for every value of the attribute, AAES computes **which relevant chunks still apply** (are not
conflicting). The information gain is the entropy of those chunk sets over the values. An attribute branches when the
set of applying chunks changes with its value. AAES does **not** compare what the chunks say: two campus pages that
state the same fee still give two different chunk sets, so the campus branches (`information_gain` in `aaes.py`).

### 3c. Decision rule (`decide` in `aaes.py`, in this order)

| Condition | Reply type |
|---|---|
| No relevant chunk, or every relevant chunk conflicts with the profile | Referral (abstain), with the student's campus office |
| A remembered (stale) value would change which chunks apply | Confirm question |
| No attribute changes which chunks apply | Answer |
| More than 3 branch combinations | Question about the attribute with the highest information gain |
| The differing chunks come from more than one document | Question (reason "different procedures") |
| Otherwise (≤ 3 branches, one document) | Conditional answer, one case per branch |

When the newest-notice rule is on, an outdated chunk is dropped if a current one applies.

---

## Section 4. Experimental setup

### 4a. Hardware (`system_profiler`, `sw_vers`)

MacBook Air (Mac16,12), Apple M4, 10 CPU cores (4 performance, 6 efficiency), 8-core GPU, 16 GB memory, macOS
27.0.1 (build 26A434).

### 4b. Software

Python 3.13.12 (conda env RAG); Ollama 0.40.15 during the test run (`Report/results/test-final/run_manifest.json`;
0.40.16 now); Docker 29.9.2; MongoDB 8.0.32 and Qdrant v1.19.0 (images in `Sources/docker-compose.yml`); torch
2.14.1, transformers 5.18.0, sentence-transformers 6.1.0, qdrant-client 1.20.0, pymongo 4.19.0 (run manifest).

### 4c. Models

| Role | Model | Settings / notes |
|---|---|---|
| Generator (all methods) | qwen3.5:4b (4.5B parameters, nvfp4 quantization) | temperature 0, seed 42, top_p 0.9, top_k 40, max 1,024 output tokens, context window 4,096, thinking off (`test-final/status.json`); quantization from `ollama show` |
| Second generator | llama2:7b (Q4_0) | only in the generation-backbone comparison on BEIR evidence (44 cases, `Report/results/2026-11-01_main/summary.md` Report C, and `dev-02`); never on HYU questions |
| Embedding | BAAI/bge-small-en-v1.5 | 384-d, cosine; BGE query instruction (`Sources/backend/app/config.py`) |
| Reranker | cross-encoder/ms-marco-MiniLM-L6-v2 | hybrid, scope filter, self-query, prompted conditional, all AAES variants |
| Self-query filter writer | the first installed Ollama model | model setting empty; today that is qwen3.5:4b, the run did not record it (unverified) |
| Tagging fallback (index r1) | qwen3.5:4b | cached; r5 used rules only |
| Question drafting | Codex (gpt-5) and Claude Code | 180 agent-written questions (`Report/ai_use_statement.md`) |
| Labelling | codex:gpt-5 (batches 01-03), claude-sonnet-5-5 (04-06) | blind, independent |
| Adjudication | claude-opus-5-5 | 47 rows |
| Verification | claude-opus-5-5, never the case's annotator | 154 cases |
| Reply-type classifier (evaluator v2) | rules + qwen3.5:4b | prompt hash 5151f273055b; checked against a blind Opus 5.5 labeller, κ = 0.899 |
| Answer-quality judge (evaluator v3, post-hoc) | claude-opus-5-5 | checked against Sonnet 5.5 (100 dev replies) and GPT-6.1 in ChatGPT, max thinking (20) |
| test-2 (built, not run) | drafter and selector Sonnet 5.5; annotators Opus 5.5 and Sonnet 5.5; adjudicators Opus 5.5 and Haiku 5.5 | `Sources/data/HYU/labels/test2/NOTES.md` |

### 4d. Run cost (test-1)

Mean seconds per question, from the saved per-question times (`total_ms` in `Report/results/test-final/raw/`):

| Method | Mean s | Median s |
|---|---|---|
| Standard dense retrieval | 9.9 | 8.4 |
| Hybrid retrieval with reranker | 10.9 | 9.9 |
| Scope filter | 10.0 | 9.2 |
| Self-query filter | 15.4 | 14.4 |
| Prompted conditional answering | 17.7 | 16.0 |
| Model only, no retrieval | 16.5 | 14.7 |
| Gold evidence | 4.2 | 2.9 |
| AAES (ours) | 3.0 | 0.3 |
| AAES that always asks | 0.6 | 0.2 |

AAES is fast mainly because questions and referrals are templates with no generation. The per-question times of all
13 methods add up to 229 minutes. Wall-clock time of the whole test run was not recorded precisely: it ran in two
sessions after the Mac slept (`Report/results/TEST_RUNS.md`); `status.json` task times sum to 12,460 s, but the three
resumed tasks may count only their resumed part.

### 4e. Data preparation (stages for a figure)

1. **Crawl**: 2026-11-10, Seoul OIA (`oia.hanyang.ac.kr`) and ERICA OIA English site (`global.hanyang.ac.kr/eng/`);
   1,423 requests in 59 min; staff pages denied (`Sources/data/DATA.md` §1-2).
2. **Snapshot**: 362 English documents, 306 Seoul and 56 ERICA, 10 aliases, 2 version families, 3 superseded (§4).
3. **Chunking**: 1,867 chunks, 320 tokens, 48 overlap (r5 index report in `Report/results/index_reports/`).
4. **Tagging**: applicability conditions by rules, LLM fallback only in r1 (§5).
5. **Questions**: 11 personas (`Sources/data/HYU/labels/personas.json`), 230 drafts, 180 kept, five slices.
6. **Labelling**: two blind annotators (gpt-5, Sonnet 5.5), Opus 5.5 adjudication and verification.
7. **Agreement before adjudication** (`Report/results/labels/`): answerability κ 0.559 (Codex vs Opus,
   `agreement_v11_part1`) and 0.425 (Sonnet vs Opus, `agreement_v12_part2`); expected behaviour 0.683 and 0.666.
8. **Splits**: dev 47, test 121, excluded 12 (`Sources/data/HYU/labels/excluded.jsonl`); test-2 75 (built later,
   frozen, not run).
9. **Test-1 label types**: answer 60, referral 46, conditional answer 9, question 6 (`counts_1c.json`).

---

## Section 5. Results: strongest first, then the full picture

### 5a. Strengths (all post-hoc unless marked)

- **Branching cases, reply type** (15 cases, evaluator v2 acceptability; `section5_posthoc.json`): AAES right and
  baseline wrong / the reverse: 10 / 0 against standard dense retrieval, hybrid with reranker, scope filter and
  self-query filter (exact McNemar p = 0.002 each); 9 / 1 against prompted conditional answering (p = 0.021).
  Post-hoc, not Holm-corrected. This compares reply types, not content.
- **Branching cases, content** (evaluator v3, post-hoc LLM judge): right conditions or a relevant question in 4 of 15
  for AAES, 0 for standard dense retrieval, self-query filter and prompted conditional answering (4 / 0 each,
  p = 0.125, not significant). Hybrid with reranker and scope filter were not judged by v3.
- **Among answered replies** (evaluator v3; each rate is over that method's own answers, so not like-for-like: AAES
  answers 40 cases, standard dense 68, self-query 67, prompted conditional 76):

| AAES vs | Wrong fact: AAES / baseline, diff [95% CI], p | Wrong-group information: AAES / baseline, diff [95% CI], p |
|---|---|---|
| Standard dense retrieval | 0.125 / 0.279, −0.154 [−0.294, −0.014], p = 0.045 | 0.125 / 0.265, −0.140 [−0.280, +0.001], p = 0.062 (n.s.) |
| Self-query filter | 0.125 / 0.313, −0.188 [−0.326, −0.051], p = 0.011 | 0.125 / 0.194, −0.069 [−0.200, +0.067], p = 0.33 (n.s.) |
| Prompted conditional answering | 0.125 / 0.237, −0.112 [−0.243, +0.023], p = 0.12 (n.s.) | 0.125 / 0.224, −0.099 [−0.240, +0.046], p = 0.18 (n.s.) |

- **Replies stating at least one wrong fact, over all 121 cases** (post-hoc, v3): AAES 0.041, standard dense
  retrieval 0.157, self-query filter 0.174, prompted conditional answering 0.149, model only 0.380, gold evidence
  0.025. Partly because AAES answers less often.

### 5b. Full picture

- **Acceptable-action rate**, test-1, evaluator v2 (`Report/results/test-final/hyu_test_v2_slices.csv`): standard dense
  0.661, hybrid with reranker 0.653, scope filter 0.653, self-query 0.661, prompted conditional 0.628, model only
  0.669, gold evidence 0.719, **AAES 0.256**; ablations: hard filter 0.256, true profile 0.273, always asks 0.240,
  question wording 0.471, no newest-notice rule 0.264.
- **Facts covered** on the 60 answer cases (evaluator v3, post-hoc, `Report/results/quality_v3/metrics_test.csv`):
  standard dense 0.300, self-query 0.269, prompted conditional 0.258, **AAES 0.119**, model only 0.079, gold evidence
  0.463 (others not judged).
- **Pre-registered comparisons** (`Report/report/draft.md` section 6):
  1. AAES vs self-query filter on wrong-group answers (applicability error rate): only 2 comparable cases, difference
     0.000, p = 1.0 (v1 and v2): **no result** (test cannot separate them).
  2. AAES vs self-query filter on correctness, unconditional slice, 3-point non-inferiority: not computed at the run;
     post-hoc with evaluator v3, −0.185 [−0.312, −0.065], p = 0.0065: **fails**.
  3. AAES vs "deciding from the question wording" on action macro-F1: −0.066 [−0.132, +0.005], Holm p = 0.463 (v2):
     **fails** (not significant, favours the ablation).
- **Always-ask ablation**: hits 11 of the 15 student-dependent cases, a superset of AAES's 10 (branching precision
  11/86 vs 10/81; `Report/results/test-final/posthoc.md`). Choosing when to ask from the evidence added nothing to
  recall.
- **Generator** (v3, post-hoc): facts covered / replies with a wrong fact on answer cases: model only 0.079 / 0.383,
  standard dense retrieval 0.300 / 0.117, gold evidence 0.463 / 0.033. Retrieval clearly helps content; even with
  gold evidence the 4B generator states under half the facts.

### 5c. Insights

1. Baselines never ask: 0 questions in 121 cases for every retrieval method (2a); AAES is the only method that
   branches where the answer depends on the student (10 / 0 vs four baselines, 5a).
2. But the branching mostly comes from willingness to ask: the always-ask ablation hits the same 10 cases plus one
   (5b), and on content AAES's advantage shrinks to 4 of 15 (p = 0.125).
3. AAES over-triggers: 52 questions and 29 conditional answers for 15 cases that need them; acceptable action 0.256 vs
   0.661 for standard dense retrieval (5b). The cause is in Step 3: it compares chunk sets, not answers (3b).
4. When AAES answers, it states fewer wrong facts (0.125 vs 0.279 among answers, p = 0.045 vs standard dense), but it
   answers 40 cases against 68, and covers fewer required facts (0.119 vs 0.300) (5a, 5b).
5. The generator is the largest loss in every system: gold evidence lifts facts covered only to 0.463 (5b).
6. The action metric hid that retrieval helps: model only matches standard dense retrieval on acceptable action
   (0.669 vs 0.661) but covers 0.079 of the facts against 0.300 (5b).

---

## Section 6. Demo scenarios (live, index r5)

### 6a. Candidates (dev questions or new wording, never test-1)

| # | Shows | Turn 1 (if any) | Question | Source |
|---|---|---|---|---|
| S1 | conditional answer | | Which insurance rules apply to me? | dev T14-132 |
| S2 | useful question (campus) | | How do I book the international student counseling program? | dev T14-017 |
| S3 | useful question (degree, year, TOPIK) | | Can I work part time here? | dev T14-130 |
| S4 | useful question (degree level) | | Does my insurance change after my visa switches from D-4 to D-2? | dev T14-120 |
| S5 | profile first, then a direct answer | I'm a second-year undergraduate at the ERICA campus and I have TOPIK level 3. | Can I work part time here? | new + dev T14-130 |
| S6 | campus stated, then a direct answer | I'm a Seoul campus student. | How do I book the international student counseling program? | new + dev T14-017 |
| S7 | old notice vs current notice | | How much is health insurance this year? | dev T14-147 |
| S8 | honest limitation | | Is there a winter school for international students? | dev T14-042 |

**Session-history check first.** In the app, the earlier turns reach AAES's step 1 (the profile), but the generator
sees only the last question; standard dense retrieval and prompted conditional answering do not use the earlier
turns at all. So a two-turn demo shows AAES using the profile to decide, not the generator reading the history.

### 6b. Trials (`Report/slides/deck_v2/demo_trials.csv`, 8 scenarios × 3 runs × 3 methods, compare mode order standard dense retrieval → prompted conditional answering → AAES, index r5, run by `Sources/scripts/demo_trials.py`; reply types by evaluator v2, unchanged)

| # | Standard dense retrieval | Prompted conditional answering | AAES (decision; reason) | Compare-mode time per run |
|---|---|---|---|---|
| S1 | answer ×3 | conditional answer ×3 | conditional answer ×3 (CONDITIONAL; branches campus + academic status, 3/3) | 50, 32, 32 s |
| S2 | answer ×3 | answer ×3 | question ×3, identical text (CLARIFY on campus; different procedures) | 8, 6, 4 s |
| S3 | answer ×3 | answer ×3 | answer ×3 (no branch found) | 29, 22, 31 s |
| S4 | referral ×3 | referral ×3 | question ×3, identical text (CLARIFY on degree level; many branches) | 12, 6, 5 s |
| S5 | answer ×3 | answer ×3 | answer ×3 (no branch); none of its replies states the ERICA 30-hour figure | 30, 26, 19 s |
| S6 | answer ×3 | answer ×3 | CONDITIONAL on degree level 3/3; v2 calls the wording conditional once and answer twice | 14, 10, 10 s |
| S7 | answer ×3 | answer ×3 | answer ×3; **all nine replies give 76,390 won (the 2025 premium)**, none the current 79,320 won | 14, 9, 12 s |
| S8 | answer ×3 | answer ×3 | question ×3 on campus (unneeded: one winter school) | 11, 7, 4 s |

No code, preset or prompt was changed. Reply wording varies between runs for every generated reply (see
"distinct texts" in the CSV); AAES's decision was the same in 3 of 3 runs in every scenario.

### 6c. Recommended scenarios

1. **S1 Conditional answer (about 35-50 s for three columns).** Type "Which insurance rules apply to me?". Point at:
   standard dense retrieval lists rules as if all applied; AAES answers per campus and status. Open AAES's
   **Execution tab**: profile (campus and status missing) → applicability labels → branch table (the Seoul rows have
   no applicable chunk, which is why that case says "ask the OIA office") → CONDITIONAL.
2. **S2 then S6, one question, then the same question with the campus stated (about 5-10 s, then 10-15 s).** S2: "How
   do I book the international student counseling program?" AAES asks "Seoul or ERICA?" (3/3); both baselines answer
   one way. S6: first type "I'm a Seoul campus student.", then the same question: AAES no longer asks for the campus
   and splits by degree level (CONDITIONAL 3/3). In the Execution tab, show campus "remembered" in the profile.
3. **S4 Useful question where baselines refer (about 5-12 s).** "Does my insurance change after my visa switches
   from D-4 to D-2?" Both baselines say the pages do not answer; AAES asks for the degree level (3/3), which is what
   the ERICA evidence splits on (degree students pay the group insurance on the tuition bill; language-course
   students ask their language school).
4. **Optional honest limitation, S8 (about 5-10 s).** "Is there a winter school for international students?" AAES asks
   for the campus although there is one winter school; both baselines answer correctly. (S7 is a second, stronger
   limitation if needed: every method, AAES included, gives last year's insurance premium.)

Not recommended: S3 and S5 (AAES does not ask, and its answer omits the hour figures), S7 as a strength.

---

## Code → name

| Code | Name | What it is (from the code) |
|---|---|---|
| B0 | Standard dense retrieval | Dense search (BGE-small, exact cosine) top 5, top 3 evidence, standard prompt. |
| R5 | Hybrid retrieval with reranker | Dense top 10 + BM25 top 10, RRF (k = 60) top 20, cross-encoder MiniLM-L6 reranker, top 3 evidence. |
| R9S | Scope filter | R5, plus a filter before search that drops chunks whose tags do not fit what the student stated (rule profile). |
| R15 | Self-query filter | R5, plus an LLM that writes the student's stated attributes as JSON, turned into the same pre-search filter. |
| R16 | Prompted conditional answering | R5's retrieval; the prompt adds: if the answer depends on unstated facts, answer per case ("If you are …") or ask one question. |
| G0 | Model only, no retrieval (reference) | The generator answers from memory, no documents. |
| G1 | Gold evidence (upper reference) | The generator gets the labelled gold evidence instead of retrieved chunks. |
| A0 | AAES (ours) | Rule profile → hybrid retrieval → cross-encoder with an applicability penalty (λ = 4, μ = 2) → top 3 → branches by which chunks apply → decision. |
| A1 | AAES with a hard filter | A0, but chunks that conflict with the profile are removed instead of moved down. |
| A2 | AAES with the true profile | A0, but step 1 is replaced by the labelled stated profile. |
| A3 | AAES that always asks | A0, but it asks whenever an attribute of a relevant chunk is unknown. |
| A4 | AAES deciding from the question wording | A0, but it asks only when the question's words mention an attribute, ignoring the evidence. |
| A6 | AAES without the newest-notice rule | A0, but outdated versions of a notice count like the newest one. |

Note: all methods were evaluated on the same r5 index (320/48 chunks), whatever chunking their preset lists for its
own index (`status.json` index_id for every task).

## Could not verify

- Which Ollama model the self-query filter's LLM call used during the test run (empty setting; the first installed
  model, probably qwen3.5:4b).
- Wall-clock duration of the test run (two sessions; resumed tasks).
- Content quality of hybrid retrieval with reranker, scope filter and the AAES ablations: evaluator v3 judged only
  six methods.
- No page states a penalty for working over the hour limit specifically (1b).
- Everything rests on LLM-made labels; nothing was verified by a person.

Commit: 5b9e2ce (the brief and its data files; this line was added in the next commit).
