# Draft evaluation data

- `sample_questions.jsonl`: 102 synthetic-fixture questions for `data/samples`.
- `filter_ready_questions.jsonl`: 683 draft questions with evidence and relevance mapped to surviving `data/filter_ready` units.
- `filter_ready_metadata_queries.jsonl`: 33 draft metadata inclusion/exclusion cases mapped to prepared units.
- `question_bank_summary.json`: counts, corpus declarations and file hashes.

Question IDs and original quotes were preserved. Section evidence maps to one or more prepared units; `source_uris` lists all mapped units and `source_section` records the original heading. Relevance was migrated mechanically, so human review is required. Older unanswerable labels can be invalid after adding web and undergraduate admission information. Do not use these drafts as reviewed gold labels or claim measured accuracy. Keep the default synthetic evaluation separate from the real-source index.
