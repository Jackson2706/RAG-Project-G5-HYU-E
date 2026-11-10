# AAES offline applicability tagging

This document covers the offline step only. The tagger records who a chunk applies to before the
chunk is stored. Online profile matching, evidence selection, evidence sufficiency and answer policy
are outside this specification.

## Vocabulary v0

An absent attribute means that the chunk does not state a constraint for that attribute.

| Attribute | Allowed values |
|---|---|
| `campus` | `seoul`, `erica` |
| `degree_level` | `undergraduate`, `master`, `doctoral`, `language_program`, `non_degree` |
| `year` | `1`, `2`, `3`, `4` |
| `student_type` | `degree_seeking`, `exchange`, `visiting`, `language_program`, `short_term` |
| `visa` | `D-2`, `D-2-5`, `D-2-8`, `D-4`, `D-10`, `other` |
| `topik_level` | `none`, `1`, `2`, `3`, `4`, `5`, `6` |
| `english_track` | `yes`, `no` |
| `academic_status` | `enrolled`, `leave_of_absence`, `completed_coursework`, `graduating`, `admitted_not_enrolled` |
| effective term | `YYYY-1` or `YYYY-2`; this is an open-ended pattern, not an enumerated attribute |

The vocabulary and its order live only in `backend/app/rag/applicability.py`.

## Chunk condition

The full condition is stored with MongoDB chunk metadata. A compact copy of the filterable fields
is written to the Qdrant payload during ingestion.

```json
{
  "constraints": {"degree_level": ["undergraduate"], "year": ["1", "2"]},
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
`requirements` holds conditions outside the fixed vocabulary, such as GPA, attendance, money, or a
language standard. `superseded_by` comes from the frozen snapshot. Extraction methods are recorded
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
- `Year 1-2` expands to `1`, `2`, and `Year 3-4` expands to `3`, `4`. `Year: N/A` adds nothing.
- In a required-level table row, `X` means `none` through the level below the stated level; `O`
  means the stated level through `6`. “TOPIK level N or higher” also expands through `6`. A Korean
  language standard expressed only as pass or fail is a requirement, not a TOPIK level.
- Visa codes are read literally. `D-10-1` normalizes to `D-10`. For “transferring from X to Y,” the
  tag is the visa held now, `X`.
- Degree, exchange, visiting, language-program and short-term student wording maps to
  `student_type`. English-track or English-taught wording maps to `english_track` when explicit.
- Academic-status words map to the vocabulary. An exclusions list removes its listed statuses; if
  it excludes graduates, leave, extra semesters and completed students from current students, the
  remaining status is `enrolled`.
- GPA, attendance, monetary thresholds, Korean or English standards, and a required higher TOPIK
  score are short free-text requirements.
- An explicit `YYYY Spring/Fall Semester`, `YYYY-1/2`, or “applied from” date sets the effective
  term. Otherwise the post date supplies January–June as term 1 and July–December as term 2.
  Undated chunks have no effective term.
- `superseded_by` is copied from the snapshot without trying to infer newer versions.

## LLM fallback contract

The fallback runs only when enabled and the rules found no vocabulary constraint. The prompt asks
for JSON only, includes the complete v0 vocabulary, and requires an exact evidence quote for every
field. The auxiliary Ollama call uses `qwen3.5:4b` by default, temperature 0, thinking off, a fixed
seed and a bounded output.

The parser takes the first decodable JSON object even when the model wraps it in other text. It
keeps a field only when the attribute exists, all values belong to that attribute's vocabulary, and
the evidence quote is an exact substring of the chunk text. Unknown fields, invalid values, missing
quotes and invented quotes are dropped and explained in the block's `trace_details`. Missing JSON,
invalid JSON and LLM-call errors produce no fallback tags and never stop offline tagging.

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
    setting, and cache file path.

The cache key is the SHA-256 of the resolved model digest, `TAG_PROMPT_VERSION`, and the SHA-256 of
the chunk text, separated by newlines. The model and its digest are resolved before a cache lookup.
A missing digest or failed Ollama call counts as an LLM error and is not cached. With LLM fallback
disabled, the tagger does not resolve a model and records `llm.enabled` as false.

VERIFY checks the reconstructed span text and recounts tokens from the exact embedded string,
`section + "\n" + text` when a section exists. It also requires zero LLM errors. Rejected LLM
outputs remain in the report but do not block publication; an LLM error or any failed VERIFY check
leaves the index in `built` state.

## Tag audit

`python -m labeling.audit_tags sample` writes the fixed, seeded 50-chunk review sheet without
changing the index. A reviewer assigns every predicted value to `correct` or `wrong`, records true
values absent from the prediction in `missed`, and signs the row in `reviewer`. Values in each cell
are separated with `|`. `score` rejects an incomplete or out-of-vocabulary reviewed row before it
writes precision and recall by attribute, rule/LLM extraction family, tag bucket, and campus. Site
defaults and snapshot-derived fields belong to the deterministic rule family. `frequency` counts
all indexed values and requirement phrases; its zero-count vocabulary entries are candidates for
the Gate G2 vocabulary review, not automatic removals.

