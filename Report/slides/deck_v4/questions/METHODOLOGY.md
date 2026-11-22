# Dev2/test3 labeling methodology

## Candidate pool

The final pool had 328 questions. The original pool contributed 214. Two later buffers added 90 and 24 questions after the first adjudication showed that many writer-marked questions did not have an evidence-supported branch.

All three pools used pre-screened r5 passage bundles. The duplicate threshold was BGE cosine 0.92. For buffer 1, the maximum cosine was 0.915 against prior candidates and 0.910 within the buffer. For buffer 2, the corresponding maxima were 0.889 and 0.862. No buffer pair reached the threshold. Agents did not reopen test1 or test2 labels during these checks.

## Annotation and adjudication

`codex:gpt-6.1-sol` and `codex:gpt-6-astra` independently labeled each blind input. They saw the question, history, gold profile for applicability, and supplied official passages. They did not see writer types, another label file, system outputs, or results.

| Pool | Cases | Reply agreement | Reply kappa | Dependency agreement | Dependency kappa | Decision disputes |
|---|---:|---:|---:|---:|---:|---:|
| Original | 214 | 0.902 | 0.827 | 0.958 | 0.907 | 27 |
| Buffer 1 | 90 | 0.744 | 0.606 | 0.800 | 0.412 | 27 |
| Buffer 2 | 24 | 0.917 | 0.830 | 0.958 | 0.647 | 3 |

Fresh `codex:gpt-6.1-terra` subagents adjudicated the 57 decision disputes. Consensus rows kept the Sol label and recorded Astra as the agreeing annotator. Adjudicated rows kept Sol as the primary annotator and recorded Terra in `adjudicated_by`.

The resolved pool contained 149 dependent and 179 plain cases. Deterministic stratified selection chose 140 dependent and 60 plain cases before verification, then assigned 60 to dev2 and 140 to test3.

## Single-model verification and freeze

At the user's request, one verifier model was used. A fresh `codex:gpt-6-astra` context reviewed every selected test3 case and all 30 dev2 cases flagged by deterministic checks. It fixed 158 rows and excluded 12 unresolved cases. The same verifier checked 12 plain reserve replacements, all of which were retained.

Verification changed many unsupported conditional labels to answers or abstentions. The frozen set therefore has 87 evidence-supported dependent cases and 113 plain cases, below the requested 140/60 balance. Dev2 has 31 dependent and 29 plain cases. Test3 has 56 dependent and 84 plain cases. This shortfall is kept as a limitation instead of overriding the verifier or generating more near-duplicate questions.

No human checked these labels. They are LLM-annotated, LLM-adjudicated and LLM-verified under amendment A33. Claims from test3 must be described as relative comparisons on an LLM-labeled set.

The frozen files are:

- `Sources/data/HYU/labels/dev2.jsonl`: 60 cases, SHA-256 `431fcc0508a8dd200c7adbf9c9ecb3fd87ecdb8af1a9ef1343f5a913a22260ff`;
- `Sources/data/HYU/labels/test3.jsonl`: 140 cases, SHA-256 `30a0ccc9ce09d70ad63ddf8111b5f1caaecbb3d26f49728c6fcb3b87ad6787f5`;
- `Sources/data/HYU/labels/FROZEN_dev2_test3.sha256`: the freeze manifest;
- `Sources/data/HYU/labels/excluded_dev2_test3.jsonl`: the 12 verifier exclusions and reasons.

No RAG system read test3 before this freeze.
