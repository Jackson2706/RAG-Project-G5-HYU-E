# AAES offline applicability tagging

This document covers the offline step only. The tagger records who a chunk applies to before the
chunk is stored. Online profile matching, evidence selection, evidence sufficiency and answer policy
are outside this specification.

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
the index. `sample_meta.json` records the requested, capped, and achieved floor counts.

`sample --exclude META` removes the chunk IDs in each supplied metadata file before sampling and
records each file and count. `sample --reuse META` keeps the old chunk IDs without applying quotas
or floors, recalculates their buckets against the current index, and uses the current manifest
partition. Reuse checks every chunk text against the old blind input and then copies that file byte
for byte. The blind JSONL contains only the chunk ID, site, title, heading path, post date, and text.
Predicted conditions, buckets, methods, and status remain in `sample_meta.json`.

The reference annotator follows `Report/notes/tag_audit_rules.md` without seeing the system tags.
`compare` validates every v1 value and checks whitespace-normalized evidence quotes against the
chunk text before it reads the current predicted tags from MongoDB. It expands `any_of` sets into
their attribute values for TP, FP, and FN counts, and also reports chunk-level exact match for the
sets. Scores are split by rule/LLM family, bucket, and campus. Recall is reported both raw and
weighted by the full bucket partition, and every precision and recall estimate has a Wilson 95%
interval.

Disagreements are written with the two sides assigned to `a` and `b` by a seeded shuffle. The side
key is stored separately and is not provided to the reviewer. With `compare --carry-decisions DIR`,
a decision is copied when its chunk, attribute, and both value sets match a decided row in `DIR`.
Only unmatched rows are written to `disagreements.jsonl`. `finalize` combines the carried and new
decisions, maps them through the current side key, excludes ambiguous rows, and reports the carried
count. For an attribute with at least five occurrences, Gate G2 passes when precision is at least
0.8 and weighted recall is at least 0.7. The final report also records disagreement outcomes,
frequent out-of-vocabulary conditions, audience counts, and TOPIK-scope counts. The report states
that the automated reference is not human-validated and that Codex also wrote the tagging rules.

