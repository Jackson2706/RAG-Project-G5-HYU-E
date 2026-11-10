> Note (2026-11-10): `qa_annotations.jsonl` was removed (PLAYBOOK A15): all 44 entries were still `pending`.
> `sample_questions.jsonl` (14 author-written questions on the sample documents) is kept; the online gate uses it.

# Answer annotations (for generation quality)

BEIR tells us which **documents** are relevant to a query. It does not give reference **answers**,
so answer correctness, completeness, grounding and citation support can only be measured on cases a
person has annotated. Until then those metrics are reported as **N/A**.

`qa_annotations.jsonl` has one line per generation case (the same cases both backbones answer).
Every entry starts as `"annotation_status": "pending"`. The question, query ID and the BEIR gold
document IDs are pre-filled; everything else is for you.

## How to annotate one case

1. Run the generation suite once: `python -m evaluation.runner --suite generation`.
   The answers are in `evaluation/results/<run-id>/raw/generation/cases/`.
2. Open the case's evidence (the `contexts.jsonl` file in the same folder) and read it.
3. Fill in:
   - `reference_answer`: a short correct answer **based on the gold documents** (or `null` if the
     right behaviour is to abstain).
   - `required_facts`: the facts a complete answer must contain, one short string each.
   - `expected_behavior`: `"answer"` or `"abstain"`.
   - `claims` (per model answer, optional): a list of `{"model": "...", "claim": "...",
     "supported": true/false, "cited": true/false, "citation_supports": true/false}` for every
     material claim of that model's answer.
   - `annotator`: your name or initials; then set `annotation_status` to `"annotated"`.
4. Re-create the reports without re-running the models: `python -m evaluation.reports --run-id main`.

Rules: annotate from the documents, not from memory; never use a model to fill these fields
(an LLM judge may be added later as a *separate*, clearly labelled evaluation). Ask a second person
to check a sample of your annotations.

SciFact "questions" are scientific claims; ArguAna "questions" are arguments (the task is to find
the counter-argument), so a natural-language answer is not always meaningful — mark such cases
`"expected_behavior": "abstain"` or leave them pending.
