# Controlled fixtures (not benchmarks)

`hyu_metadata_queries.jsonl` tests **where** metadata filtering is applied (Prefiltering vs
Postfiltering) on the five synthetic HYU sample documents in `Sources/backend/sample_data/`.

- `question` and `relevant` reuse the labels of `Sources/data/HYU/labels/legacy/sample_questions.jsonl` (written by the
  project authors for the synthetic documents — not independent human judgments).
- `criteria` are the conditions a student states (e.g. "I study at ERICA").
- Whether a document is **eligible** is NOT written here: the runner computes it from each document's
  declared metadata with the same predicate code the pipeline uses (`FilterCriteria.to_filter()`,
  default policy: unknown values and campus-wide documents stay eligible).
  So `relevant ∩ eligible` is the target; when it is empty the correct result is "no eligible evidence".

Results on this fixture show filter *behaviour* (ineligible results, starvation); they are not
evidence about real Hanyang University documents.
