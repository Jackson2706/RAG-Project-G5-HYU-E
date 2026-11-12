# AAES: applicability tagging (offline) and online steps 1–4

The first part covers the offline step: the tagger records who a chunk applies to before the chunk
is stored. The section "Online steps (P7)" specifies profile understanding, applicability labels,
branches with information gain, and the answer policy. Its pure functions live in
`backend/app/rag/aaes.py`; T24 (`backend/tests/test_aaes_t24.py`) tests them.

## Vocabulary v1

An absent attribute means that the chunk does not state a constraint for that attribute.

| Attribute | Allowed values |
|---|---|
| `campus` | `seoul`, `erica` |
| `degree_level` | `undergraduate`, `master`, `doctoral`, `language_program`, `non_degree` |
| `year` | `1`, `2`, `3`, `4` |
| `student_type` | `degree_seeking`, `exchange`, `visiting`, `language_program` |
| `visa` | `D-2`, `D-2-5`, `D-2-8`, `D-4`, `D-10`, `other` |
| `topik_level` | `none`, `1`, `2`, `3`, `4`, `5`, `6` |
| `english_track` | `yes`, `no` |
| `academic_status` | `applicant`, `admitted_not_enrolled`, `enrolled`, `leave_of_absence`, `completed_coursework`, `graduating` |
| `korean_standard` | `pass`, `exempt`, `fail` |
| effective term | `YYYY-1` or `YYYY-2`; this is an open-ended pattern, not an enumerated attribute |

The vocabulary and its order live only in `backend/app/rag/applicability.py`.

## Chunk condition

The full condition is stored with MongoDB chunk metadata. A compact copy of the filterable fields
is written to the Qdrant payload during ingestion.

```json
{
  "constraints": {"degree_level": ["undergraduate"], "year": ["1", "2"]},
  "any_of": [{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}],
  "scope": "national",
  "campus": ["seoul", "erica"],
  "requirements": ["attendance rate of less than 70%"],
  "effective_term": "2026-1",
  "superseded_by": null,
  "extraction_method": {"campus": "rule", "year": "rule", "effective_term": "rule"},
  "evidence": {"year": "Year: Year 1-2"}
}
```

`scope` is `campus` or `national`. A national condition always applies to both campuses.
`any_of` contains alternative condition sets that the source explicitly joins with “or.” The
ordinary `constraints` must fit and at least one alternative set must fit. Alternative attributes
are not duplicated in `constraints`.
`requirements` holds conditions outside the fixed vocabulary, such as GPA, attendance, money, or a
preference. `superseded_by` comes from the frozen snapshot. Extraction methods are recorded
per field as `site_default`, `rule`, `llm`, or `snapshot`. Evidence values are exact substrings when
a short supporting span is available; every LLM field must have one.

## Rule-first extraction

The tagger combines `heading_path` and chunk text, and also reads the title. This matters for table
rows, whose text repeats cells as `Header: value`.

- Campus defaults to the chunk's `site`. A national visa or immigration rule, part-time work rule,
  alien-registration rule, or National Health Insurance rule applies to both campuses unless the
  chunk gives a campus-specific procedure.
- Bachelor's and undergraduate text maps to `undergraduate`; Master's and Doctoral/Ph.D. map to
  their respective levels. Explicit language-program and non-degree audiences use those values.
- The tagger unions every stated study-year range in a chunk. It handles numeric forms such as
  `Year 1-2`, `Year 3, 4`, and `Bachelor's degree 1~2 years`, plus ordinal forms such as `First
  year` and `Third and fourth years`. Durations such as `four-year scholarship`, `1 year`, and `up
  to 2 years` add nothing. `Year: N/A` also adds nothing.
- In a required-level table row, `X` means `none` through the level below the stated level; `O`
  means the stated level through `6`. “TOPIK level N or higher” also expands through `6`.
- The Korean Language Standards wording maps separately from TOPIK: satisfied or exempted maps to
  `pass, exempt`, exempted alone maps to `exempt`, and did not satisfy or Korean Standard Fail maps
  to `fail`.
- Visa codes are read literally, and `D-10-1` normalizes to `D-10`. A status change from one visa
  to another keeps only the target visa, including OCR-spaced forms such as `D -4` to `D -2`.
- Degree, exchange, visiting and language-program wording maps to `student_type`. `Degree Program
  Students` maps to `degree_seeking`. A parenthesized or colon-delimited ineligibility list does
  not contribute `student_type`, `degree_level`, or `academic_status` values. English-track or
  English-taught wording maps to `english_track` when explicit.
- Academic status needs stated wording. `enrolled` comes from phrases such as `currently enrolled`,
  `enrolled students`, `students who enrolled at`, or `currently in school`, not from an audience
  such as international students or freshmen. A leave-of-absence application notice is for
  `enrolled` students, while a return-to-school or re-registration notice is for
  `leave_of_absence` students.
- Every chunk in a document whose title identifies an admission guide gets `applicant`, even if the
  chunk has no applicant wording. Sections about successful candidates, an admission certificate,
  deposit payment after the result, or an admission result get `admitted_not_enrolled` instead.
  Leave-of-absence information inside an admission guide does not change the applicant status.
  Scholarship references to applicants do not gain the applicant tag.
- Within one sentence or list line, a TOPIK condition joined by “or” to IELTS, TOEFL, TEPS or an
  English-track condition becomes `any_of`. A TOPIK threshold expands through level 6; a valid
  certificate without a level means levels 1–6. The two attributes are removed from ordinary
  `constraints`.
- If a TOPIK threshold is an alternative to a condition outside vocabulary v1, the tagger stores
  the sentence or `Sort:` row as a requirement of at most 200 characters. Social Integration/KIIP,
  IIE levels, King Sejong Institute levels, and pre-assessment scores are outside the vocabulary.
  The tagger writes no TOPIK constraint or TOPIK `any_of` set for that alternative.
- GPA, attendance, monetary thresholds, English standards, and a required higher TOPIK score are
  short free-text requirements.
- Preferred, additional-points, bonus, advantage and optional wording never creates a constraint.
  A matched preference from the chunk is retained as a `preference:` requirement.
- An explicit `YYYY Spring/Fall Semester`, `YYYY-1/2`, or “applied from” date sets the effective
  term. Otherwise the post date supplies January–June as term 1 and July–December as term 2.
  Undated chunks have no effective term.
- `superseded_by` is copied from the snapshot without trying to infer newer versions.

## Profile fit and scope defaults (Step 2 helper; P7 must use these)

`condition_fit(condition, stated_profile)` in `app/rag/applicability.py` gives A_e(u) for one chunk.
The result is `compatible`, `conflicting` or `open`.

- **One condition set:**
  - conflicting if a known profile value lies outside an allowed list;
  - open if a constrained attribute is unknown;
  - else compatible.
  - Campus is always part of the check, and `scope: national` means both campuses.
- **`any_of`:** the chunk applies when `constraints` fit AND at least one alternative set fits.
  - It is conflicting only if every set conflicts.
  - Example: an English-track student with no TOPIK fits "valid TOPIK certificate **or** IELTS/TOEFL
    (English track)".
- **Scope defaults** (`SCOPE_DEFAULTS`, A17):
  - Unless the user states it, `academic_status` is assumed to exclude `applicant`. Step 1 records
    this attribute with status `scope_default` next to `stated` / `remembered` / `missing` /
    `stale`, and the trace shows it.
  - A scope default only rules values **out**. An applicant-only chunk conflicts. An enrolled-only
    chunk stays `open`, never `compatible`, so a real branch (e.g. enrolled vs completed
    coursework) is never hidden.
- **The Qdrant payload** carries `app_any_of: true` for chunks with alternatives. A hard prefilter
  must not drop those chunks on the alternative attributes.

## Unknown condition status (PLAYBOOK A23; P7 must implement, T24 tests it)

Every chunk has `condition_status` = `conditioned`, `unconditioned` or `unknown` (A6). `unknown` means the
chunk has an eligibility cue but no rule resolved it (bucket `rule_cue_unknown` in r4, 387 of 1,867
chunks; also `llm_rejected` / `llm_errors` in older revisions).

- **Never silently unconditioned.** An unknown chunk is not treated as "applies to everyone". Its
  applicability label in Step 2 is `unknown`, shown as such in the trace, next to compatible / conflicting /
  open.
- **AAES still answers** from it when it is the best evidence (it is not dropped and does not force
  ABSTAIN on its own).
- **Caveat.** When the answer relies on at least one unknown chunk, the generated answer ends with:
  "This may depend on your situation; please confirm with the OIA office."
- **Trace flag.** The sufficiency step sets `unknown_condition_evidence = true` (false otherwise) in its
  typed output, so the Execution tab shows it.
- **Metric (P8).** Unknown-caveat rate per slice: the share of answered cases whose answer carries the
  caveat, per slice and campus.

## Online steps (P7)

Four steps run per question. They reuse `condition_fit` and the scope defaults above. Every step writes its
typed input and output into the trace. The pure logic is in `app/rag/aaes.py`. The blocks are thin wrappers:

| Step | Block (stage) | Method id | `aaes.py` |
|---|---|---|---|
| 1 Profile | query_understanding | `profile_understanding` | `extract_profile`, `known_values` |
| 2 Labels + soft penalty | reranking | `applicability_reranker` | `label_chunk`, `penalized_score` |
| 3 Branches + IG, 4 Policy | evidence_sufficiency | `applicability_sufficiency` | `information_gain`, `decide` |
| templates | (pipeline, after step 4) | — | `render_action`, `with_caveat` |

### Step 1: profile

`extract_profile(question, history=(), remembered=None)` returns one entry per vocabulary attribute:
`{"values": [...], "status": s, "evidence": "<quote>"}` with `s` one of:

- `stated`: said in the current question (rule patterns: campus names incl. Ansan, degree words, "year N" /
  freshman, exchange/visiting/language-program, visa codes, "TOPIK N" / "no TOPIK", English track,
  leave of absence, completed coursework, graduating, "I was admitted");
- `remembered`: said in an earlier user turn of `history`, or given by a memory with status `remembered`.
  A later statement replaces an earlier one (the latest turn wins; the current question wins over history);
- `stale`: a remembered value that the memory flags as possibly outdated (M2). It is used for the labels,
  but step 4 may ask to CONFIRM it;
- `scope_default`: unstated `academic_status` (excludes `applicant`, A17). A question about applying for
  admission ("how do I apply", "admission requirements") states `applicant` (GUIDELINES 8.2);
- `missing`: unknown, values `[]`.

`known_values(profile)` keeps the stated, remembered and stale values as `{attribute: [values]}`, the input
of `condition_fit` (which adds the scope default itself).

### Step 2: applicability labels and the soft penalty

`label_chunk(condition, condition_status, known)` gives one label per candidate:

| Label | When |
|---|---|
| `conflicting` | `condition_fit` is conflicting (campus included; an applicant-only chunk under the scope default) |
| `unknown` | `condition_status == "unknown"` and not conflicting. **Never** treated as unconditioned (A23) |
| `unconditioned` | no `constraints` and no `any_of`, and the campus fits |
| `compatible` / `open` | `condition_fit` otherwise |

**Condition sets.** A chunk with `any_of` applies when its `constraints` fit and at least one set fits. It is
conflicting only when every set conflicts (an English-track student without TOPIK fits "TOPIK or
IELTS/TOEFL for English track").

**Soft penalty.** `penalized_score(score, label, outdated, lam, mu) = score − lam·[conflicting] −
mu·[outdated]`; `outdated` means `superseded_by` is set. Nothing is removed. λ and μ are tuned on dev only.
Variant A1 (`hard_filter: true`) drops conflicting candidates instead.

### Step 3: branches and information gain

Step 3 looks only at the *relevant* selected evidence (query coverage ≥ `relevance_threshold`, the
Lesson-5 signal; A5 swaps in an LLM judge). Its *support* is the relevant evidence that is not
conflicting. With the temporal rule on (A6 turns it off), outdated support is dropped when non-outdated
support exists.

For an attribute `a` that is not known (missing or scope default), the value space `V_a` is its vocabulary
values, narrowed by the scope default (no `applicant`). For each `v ∈ V_a`, the *outcome* is the set of
support chunks that are not conflicting when `a = v`. With a uniform prior over `V_a`:

- `D(a)` = number of distinct outcomes;
- `IG(a)` = entropy of the outcome distribution in bits, so `IG(a) = 0` exactly when no value of `a` changes
  which evidence applies.

Branch attributes are those with `IG > 0`. Campus is an ordinary branch attribute when unstated (GUIDELINES
8.3); a national rule never splits on campus.

### Step 4: policy

`decide(chunks, profile, max_branches=3, temporal=True, policy="aaes")`, in this order:

1. **ABSTAIN**: no relevant evidence (`reason: no_evidence`), or every relevant chunk conflicts
   (`reason: not_applicable`, refer to the office of the student's own campus; never answer from the other
   campus's rule).
2. **CONFIRM**: a `stale` attribute would have `IG > 0` if it were unknown. Ask whether the remembered value
   still holds, before answering.
3. **ANSWER**: no branch attribute.
4. **CONDITIONAL**: the joint number of outcomes over all branch attributes is ≤ `max_branches` and the
   branches share one procedure.
5. **CLARIFY**: otherwise. Ask one question about the branch attribute with the highest IG (ties: vocabulary
   order). shortcut: "different procedure" means the chunks that differ between branches come from more
   than one document; upgrade to an office/form check if dev shows false CLARIFYs.

Variant A3 (`policy: "always_clarify"`) clarifies whenever any attribute of a relevant chunk's condition is
not known, without information gain.

Variant A4 (`policy: "question_only"`) is the question-only ambiguity detector: after the ABSTAIN rule it
asks about the first attribute (vocabulary order) that a fixed cue list (`QUESTION_CUES`) finds in the
question text and the profile does not fix; otherwise ANSWER. It computes no information gain, never returns
CONDITIONAL or CONFIRM, and ignores how the evidence splits. Pre-registered comparison 3 is A0 vs A4 on action
macro-F1.

**Unknown caveat (A23).** When the action is ANSWER or CONDITIONAL and the support contains at least one
`unknown` chunk, `unknown_condition_evidence = true` and `with_caveat(answer, decision)` appends: "This may
depend on your situation; please confirm with the OIA office." Otherwise the flag is false and the answer is
unchanged.

`decide` returns `{action, reason, support, branch_attributes, branches: {attr: {ig, outcomes}},
clarify_attribute, confirm_attribute, unknown_condition_evidence}`. CLARIFY, ABSTAIN and CONFIRM are
rendered by `render_action(decision, profile)` from fixed templates without an LLM call. ANSWER and
CONDITIONAL go to generation; CONDITIONAL adds the branch table to the prompt so each branch is stated
with its citation. The chat shows the action as a badge.

## LLM fallback contract

The fallback runs only when enabled and the rules found no vocabulary constraint or `any_of` set.
Prompt v3 asks for JSON only, includes the complete v1 constraint vocabulary, tells the model not
to tag preferences, and requires an evidence quote for every field. It does not ask the model for
`any_of`; alternatives are rule-only. The auxiliary Ollama call uses `qwen3.5:4b` by default,
temperature 0, thinking off, a fixed seed and a bounded output.

With the fallback disabled, a chunk that has an LLM cue but no rule constraint or `any_of` set goes
to `rule_cue_unknown`, with `condition_status="unknown"`. A chunk without a cue remains
`rule_unconditioned`. No model is resolved or called in either case.

Postcheck p1 first maps unknown F and D- visa codes to `other`, drops `student_type` values
`international` and `volunteer`, and drops the unknown `semester` attribute. It then matches the
evidence quote after collapsing whitespace and ignoring case, while storing the exact substring
from the chunk. A field that allows every vocabulary value is not a constraint. Unknown fields,
invalid values, missing or invented quotes, every-value fields, and preferences are dropped with a
fixed reason label. Missing or invalid JSON uses `bad_json`; LLM-call errors produce no fallback
tags and never stop offline tagging.

## Index

Each chunk of the HYU snapshot index carries one validated `ChunkCondition`.

- MongoDB stores the full form (`chunk["applicability"]`). Qdrant stores the compact filterable
  copy from `ChunkCondition.to_payload()`.
- MongoDB also stores `source_spans`, the snapshot character offsets for the source spans covered
  by the chunk. VERIFY reconstructs whole-span chunks from `documents.jsonl`. A token window inside
  one long span must be a substring of that span.
- `superseded_by` is converted from the snapshot doc_id to the index doc_id of the newer version.
- The index manifest's `applicability` block records:
  - the vocabulary version;
  - chunks tagged by rules or by the LLM, unconditioned chunks, LLM calls, cache hits, rejected
    outputs by reason, and LLM errors;
  - the auxiliary LLM model and digest, prompt version, temperature, `num_ctx`, seed, thinking
    setting, cache file path, postcheck version, and vocabulary version.

The cache key is the SHA-256 of the resolved model digest, `TAG_PROMPT_VERSION`, and the SHA-256 of
the chunk text, separated by newlines. The model and its digest are resolved before a cache lookup.
A missing digest or failed Ollama call counts as an LLM error and is not cached. With LLM fallback
disabled, the tagger does not resolve a model and records `llm.enabled` as false.

VERIFY checks the reconstructed span text and recounts tokens from the exact embedded string,
`section + "\n" + text` when a section exists. It also requires zero LLM errors. Rejected LLM
outputs remain in the report but do not block publication; an LLM error or any failed VERIFY check
leaves the index in `built` state.

## Tag audit

The A14 automated audit uses `python -m labeling.auto_audit`. Each command accepts `--out NAME` and
writes under `Report/results/tag_audit/<index_id>/<NAME>/`; the default name is `auto`. `sample`
reads the published MongoDB index and draws from the seven A6 buckets, including
`rule_cue_unknown`, with campus stratification inside each bucket. At `--n 150`, the bucket quotas
are 50 `rule_tagged`, 25 `rule_unconditioned`, 35 `rule_cue_unknown`, 20 `llm_tagged`, and 35
`llm_unconditioned`; all `llm_rejected` and `llm_errors` chunks are included. Quotas and floors
scale with `--n`, empty buckets have zero quota, and floors are capped by the eligible chunks in
the index. Repeatable `sample --quota BUCKET=N` values replace the scaled quota for those buckets;
an explicit quota is exact, while unlisted buckets can still receive fill chunks. The dev-100 sample
uses `--n 100 --quota rule_cue_unknown=30`. `sample_meta.json` records the requested, capped, and
achieved floor counts.

`sample --exclude META` removes the chunk IDs in each supplied metadata file before sampling and
records each file and count. `sample --reuse META` keeps the old chunk IDs without applying quotas
or floors, recalculates their buckets against the current index, and uses the current manifest
partition. Reuse checks every chunk text against the old blind input and then copies that file byte
for byte. The blind JSONL contains only the chunk ID, site, title, heading path, post date, and text.
Predicted conditions, buckets, methods, and status remain in `sample_meta.json`.

The test-100 audit uses `sample --design cue --n 100` with `--min-cue visa=20`, `--min-cue
student_type=20`, and `--min-cue degree=20`. Cue matching reads the chunk text, document title, and
heading path. It does not read predicted tags. The first match wins in this order: visa code or
`visa`; exchange, visiting, degree-program, language-program, or non-degree wording; degree wording;
then `none`. The sampler allocates each cue minimum across tag buckets in proportion to the eligible
population and keeps at least 30% ERICA chunks inside a stratum when enough are available. Remaining
places are allocated in proportion to the remaining bucket-by-cue strata. `sample_meta.json` records
the stratum of each sampled chunk and the population (`N_h`) and sample count (`n_h`) of every
eligible stratum. The command prints the achieved count for each cue. These counts estimate where an
attribute may occur; only blind annotation establishes the number of reference occurrences.

The reference annotator follows `Report/notes/tag_audit_rules.md` without seeing the system tags.
`compare` validates every v1 value and checks whitespace-normalized evidence quotes against the
chunk text before it reads the current predicted tags from MongoDB. It expands `any_of` sets into
their attribute values for TP, FP, and FN counts, and also reports chunk-level exact match for the
sets. A stored `condition_status=unknown` makes constraint attributes unresolved; campus, scope,
and effective term remain resolved. Per attribute, coverage is the share of reference occurrences
that fall in resolved chunks. Precision, recall, and bucket-weighted recall use resolved chunks
only. Strict recall uses all chunks and counts every reference value on an unknown chunk as a miss;
strict weighted recall uses the full index bucket partition. These proportions have Wilson 95%
intervals. Scores are also split by rule/LLM family, bucket, and campus. This bucket-weighted method
is retained for samples without a recorded design.

For a cue-designed sample, a chunk in stratum `h` has weight `N_h / n_h`. TP, FP, FN, coverage,
resolved precision and recall, strict recall, and the unknown-condition share use these weights.
Their Wilson intervals use the Kish effective sample size `(sum(w))^2 / sum(w^2)` over the units in
that denominator. Reports show the design-weighted estimates and the unweighted sample values. The
degree-level error section gives the raw FP and FN units in chunks whose predicted academic status
contains `applicant`, together with each group's design-weighted share of all degree-level FP or FN
units.

The report gives the share of sampled unknown chunks whose reference contains a constraint or
`any_of`, its Wilson interval, and the share and interval scaled by the index's unknown-chunk count.
It also lists the most frequent reference attributes in those chunks. `report --side-by-side OUT_A
OUT_B [OUT_C ...] --label LABEL_A --label LABEL_B [--label LABEL_C ...] --to FILE.md` reads two or
more `scores_final.json` files and puts their occurrences, coverage, resolved gate scores, strict
recall, gate result, unknown estimate, and applicant-chunk degree errors next to each other. The
number of labels must match the number of folders. The last folder is marked as the gate sample.

Disagreements are written with the two sides assigned to `a` and `b` by a seeded shuffle. The side
key is stored separately and is not provided to the reviewer. With `compare --carry-decisions DIR`,
a decision is copied when its chunk, attribute, and both value sets match a decided row in `DIR`.
Only unmatched rows are written to `disagreements.jsonl`. `finalize` combines the carried and new
decisions, maps them through the current side key, excludes ambiguous rows, and reports the carried
count. For an attribute with at least five reference occurrences, Gate G2b passes when resolved
precision is at least 0.8 and resolved weighted recall is at least 0.7. Coverage and strict recall
are reported in the same gate row but do not change the verdict. The final report also records
disagreement outcomes, frequent out-of-vocabulary conditions, audience counts, and TOPIK-scope
counts. The report states that the automated reference is not human-validated and that Codex also
wrote the tagging rules.


## Metrics (P8)

Code: `evaluation/metrics/aaes.py` (per-case functions) and `evaluation/metrics/stats.py` (paired tests).
Every function has a hand-computed example in its docstring and a test in `evaluation/tests/test_aaes_metrics.py`.
A rate whose denominator is 0 is undefined (`None`) and is left out of means.

**Actions.** The system action maps to a label behaviour: ANSWER → `answer`, CONDITIONAL →
`conditional_answer`, CLARIFY and CONFIRM → `clarify` (both ask the student), ABSTAIN → `abstain`.
Methods without AAES actions: an answered outcome → `answer`, a gate abstention → `abstain`.

| Metric | Definition |
|---|---|
| Action accuracy | predicted = `expected_behavior` |
| Acceptable-action rate | predicted ∈ `acceptable_behaviors` |
| 4×4 confusion, macro-F1 | rows expected, columns predicted; F1 per behaviour, averaged over behaviours that occur as expected or predicted |
| Clarification P/R | positive = `clarify`, on expected vs predicted |
| Unnecessary-clarification rate | of the cases where `clarify` is not acceptable, the share where the system clarified |
| Gate 2×2 | proceed = answer/conditional; sufficient = expected answer/conditional (`metrics/gate.py`) |

**Chunk classes.** A retrieved chunk (doc id + `source_spans`) is `gold` if it overlaps a `gold_evidence`
span, else `inapplicable` if it overlaps an `inapplicable_evidence` span, else `outdated` if it overlaps an
`outdated_evidence` span, else `other`. Overlap = same doc and a shared character.

| Metric | Definition (per case) |
|---|---|
| Applicable-Recall@k | share of gold spans overlapped by at least one top-k chunk; `None` without gold spans |
| Inapplicable-Intrusion@k | share of the top-k chunks that are `inapplicable`; `None` without inapplicable spans |
| AER (applicability error) | answered cases with inapplicable spans: 1 if a **cited** chunk is `inapplicable`, else 0 |
| Outdated-answer rate | answered cases with outdated spans: 1 if a cited chunk is `outdated`, else 0 |
| Unknown-caveat rate | answered cases: 1 if the trace flag `unknown_condition_evidence` is true |

Required-fact coverage and conditional completeness need an LLM judge; it is validated on 60 dev cases
against human labels before use (Appendix F) and is not part of this module.

**Statistics.** Paired bootstrap 95% CI of the mean difference (10,000 resamples, `stats.paired_compare`),
paired sign-flip permutation p-value (10,000), Holm correction over the three pre-registered comparisons.
