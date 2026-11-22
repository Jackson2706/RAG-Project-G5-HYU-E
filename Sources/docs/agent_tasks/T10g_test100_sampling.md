# T10g — Test-100 sample: attribute-cue strata, design-weighted estimates, three-way report
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2b, PLAYBOOK A24)

Goal: The G2b test sample (~100 chunks, none of the 250 used before) must hold ≥ 15 expected occurrences each
of degree_level, student_type and visa. Oversampling biases plain scores, so every estimate is weighted by
the inverse inclusion probability of its stratum. Code and tests only.

Read first: AGENTS.md; PLAYBOOK A20, A23, A24; `Sources/labeling/auto_audit.py` (after T10d/T10f) and
`T10f.result.md`; `audit_tags.py` (`wilson_interval`: reuse).

Allowed write paths: `Sources/labeling/auto_audit.py`, new tests in `Sources/labeling/tests/`,
`Sources/docs/aaes_spec.md` (Tag audit section only), `Sources/docs/agent_tasks/T10g.result.md`.

Do not touch: the backend, `Report/`, `Sources/data/`, existing tests.

Spec:
1. **Cue strata (independent of the tagger).** Fixed regexes on the chunk text + title + heading path, never on
   predicted tags:
   - `cue_visa`: a visa code (`D\s*-\s*\d`, `F-\d`, "visa");
   - `cue_student_type`: exchange, visiting, "degree program", "language (program|training|school)",
     "non-degree";
   - `cue_degree`: bachelor, undergraduate, master, doctoral, Ph.D, graduate.
   A chunk's stratum = (bucket, the first cue that matches in the order visa → student_type → degree, or
   `none`).
2. **`sample --design cue --n 100 --min-cue visa=20 --min-cue student_type=20 --min-cue degree=20 --exclude M1
   --exclude M2`.** Allocate the minimums first (proportional to bucket inside each cue stratum, ≥ 30% ERICA
   where available), then fill to n proportionally over the remaining strata. Store every chunk's stratum, and
   each stratum's population N_h and sample size n_h, in `sample_meta.json`. Seeded; no overlap with excluded
   samples (assert it).
3. **Design-weighted scoring** when `sample_meta.json` has a design. Each chunk's weight is w = N_h / n_h.
   TP/FP/FN, coverage, the resolved/strict recall, precision and the unknown share are weighted sums. Wilson
   intervals use the Kish effective sample size n_eff = (Σw)² / Σw² of the contributing units. The md report
   prints weighted and unweighted values. Old (bucket-weighted) samples keep their current method.
4. **Applicant-chunk errors.** For degree_level, report how many FP and FN units (unweighted counts and the
   weighted share) fall in chunks whose predicted `academic_status` contains `applicant`.
5. **Three-way report.** `report --side-by-side` accepts 2 or more folders with labels
   (`--label dev-150 --label dev-100 --label test-100`) and marks the last one as the gate sample.
6. **Expected-occurrence check.** `sample` prints, per cue, the sampled count; the result note states how this
   relates to the ≥ 15 expected occurrences (a cue is a proxy, not a guarantee).

Tests that must pass (offline, mongomock, synthetic r5-like index): minimums met and seeded; no excluded chunk
sampled; a hand-computed 2-stratum weighted precision/recall with n_eff in the docstring; applicant-chunk error
count; a 3-folder report; existing suites `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`
and `cd Sources/backend && pytest -q`.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met; `T10g.result.md` has the exact command sequence for the test-100
(sample → blind reference → compare → blind review → finalize → three-way report).
