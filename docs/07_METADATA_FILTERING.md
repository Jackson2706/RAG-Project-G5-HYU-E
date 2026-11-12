# Metadata filtering

Prefiltering and postfiltering use the same eligibility predicate. Prefiltering limits the search before dense or BM25 ranking. Postfiltering removes ineligible candidates after retrieval and does not refill the list; fewer than Top K may remain. Both can be enabled together.

## Use the application

1. Index the prepared corpus: `conda run -n RAG python scripts/ingest.py --path data/filter_ready`. This replaces the current index. Existing indexes already ingested from this folder carry the metadata; no new embedding format is required.
2. In Configuration, choose **R9 — Metadata prefiltering** or **R10 — Metadata postfiltering**.
3. Under **Query Understanding → Stated criteria**, fill only the fields you need. These explicit controls supply the filter; the question text does not automatically add constraints.
4. Under the chosen filter stage, turn **Keep documents with unknown values** off for strict matching. Leave **Campus-wide documents count** and **Include shared department/college rules** on to retain applicable explicit `ALL` rules.
5. Ask a question and inspect the Execution trace: criteria, applied predicate, candidates, and postfilter rejection reasons are visible.

For example, ask “What scholarships are listed for new international undergraduates?” with Campus `SEOUL`, Academic level `undergraduate`, Student category `international`, Topic `scholarships`, Academic year `2027`, Term `spring`. Leave Department and College empty for general admission scholarships. To explore a major's courses, use Campus `SEOUL`, Academic level `undergraduate`, Department `architecture`, Topic `courses`; leave Academic year empty because the majors guide has no reliable academic year.

## Fields and rules

Supported fields: campus, academic_level, student_category, department, college, topic, academic_year, term, document_type, degree_level, available_degree_levels, admission_route, effective_date, and legacy audience. The generic configuration UI and chat API's existing `stages` object both accept these fields under `query_understanding.params`.

- Conditions on different fields are ANDed. Comma-separated values within a field are ORed, case-insensitively; for example `scholarships, tuition`. Empty fields add no condition.
- Use exact canonical department/college keys from `data/filter_ready.vocabulary.json` and `data/filter_ready.web_2026-11-12.vocabulary.json`; display names and synonyms are not inferred. Topics can differ across related evidence, so a narrow topic filter can reduce recall.
- Missing metadata is unknown. Strict filtering excludes it; the unknown-values toggle keeps it only when desired. English language does not imply international student status.
- Explicit campus `ALL` qualifies for any campus when the campus-wide toggle is enabled. Explicit department/college `ALL` qualifies for that scope when the shared-scope toggle is enabled. A missing department on a college-wide rule is not a universal rule. Add a college criterion when you need to constrain a specific college; strict department filtering can exclude broader college guidance.
- Academic level and student category are separate. Use `academic_level=undergraduate` and `student_category=international`, not `audience=international`, for the prepared corpus. Audience remains available for older synthetic fixtures.
- Year means the explicitly stated academic/admission cycle. Retrieval date is not an academic year or effective date. Spring 2027 admission tuition can reference Fall 2026 rates; filtering by cycle does not change the quoted rate period.
- `degree_level=combined` includes rows discussing an unavailable combined program. Use `available_degree_levels=combined` only when asking for programs explicitly offered. This positive-availability filter requires an explicit matching value even when unknown values are otherwise allowed; missing and empty availability lists never count as an offered degree.
- Topic, department and degree filters constrain retrieval; they do not guarantee an answer. An empty eligible set is allowed; filters are not silently relaxed.

For API usage, send your normal `/api/chat` request with a stages configuration such as:

```json
{
  "question": "Which scholarships are listed for international undergraduates?",
  "stages": {
    "query_understanding": {
      "method": "stated_criteria",
      "params": {"campus": "SEOUL", "academic_level": "undergraduate", "student_category": "international", "topic": "scholarships", "academic_year": "2027", "term": "spring"}
    },
    "metadata_prefiltering": {
      "method": "qdrant_prefilter",
      "params": {"include_unknown": false, "include_campus_wide": true, "include_shared_scope": true}
    }
  }
}
```

Replace `metadata_prefiltering`/`qdrant_prefilter` with `metadata_postfiltering`/`candidate_postfilter` to use the same conditions after retrieval.
