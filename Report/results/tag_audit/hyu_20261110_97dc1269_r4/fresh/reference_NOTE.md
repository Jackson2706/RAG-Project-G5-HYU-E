# Blind reference annotation note

I annotated the 100 chunks in input order. I used only each chunk's text, heading path, title, site, and post date. I did not inspect predicted tags or any other audit artifact. Campus came from the site unless the title or text identified ERICA, and dates were converted to an effective term using rule 11.

The hardest cases were alternatives and academic status. I applied rule 5b when TOPIK was the only vocabulary condition among several ways to qualify, leaving both `constraints` and `any_of` free of that condition and recording the full alternative as out of vocabulary. I used `any_of` only for an explicit "or" with at least two vocabulary-backed condition sets. For status, I kept scholarship audiences as enrolled without adding `academic_status` unless the wording met rule 8b. Admission-guide chunks received applicant status, acceptance sections received admitted-not-enrolled status, return-to-school notices received leave-of-absence status, and leave applications received enrolled status. Optional scores and point bonuses were recorded as preferences rather than constraints.

**Limitation:** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.
