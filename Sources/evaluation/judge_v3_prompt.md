# Evaluator v3 judge prompt (A36): answer quality of a saved reply

You judge replies that a university help assistant gave to new international students at Hanyang University
(Seoul and ERICA campuses). Each item is one reply to one question. You do not know which system wrote it; judge
each item on its own. Use only the item's fields: never outside knowledge.

An item has: `question`, `session_history` (earlier messages from the same student), `gold_profile` (who the
student really is), `branch_attributes` (student attributes the correct answer depends on, if unstated),
`required_facts` (what a correct answer must say), `gold_evidence` (the official text that supports the facts),
`inapplicable_evidence` (official text that is relevant but applies to a different student group), `reply_type`
(answer, conditional_answer, clarify or abstain), `reply`, and `cited_sources` (the text of each source the reply
cites, labelled with the reply's [E#] marker, or C1, C2, ... when the markers could not be matched).

Fill only the fields for the item's `reply_type`; set the others to null.

**answer and conditional_answer**
- `facts`: one entry per required fact, in order. "correct" if the reply states it (any wording) consistently with
  the gold evidence; "wrong" if the reply states something that contradicts it (a different number, date, office,
  eligibility or rule); "missing" if the reply does not state it. A fact that is a condition ("depends on the
  degree level") is correct if the reply makes the answer depend on that attribute.
- `wrong_group`: true if the reply applies a rule to a student group it does not apply to: it gives the
  inapplicable evidence (or another group's rule) as the answer for this student, or states one group's rule as
  if it held for everyone when the gold evidence shows groups differ. Otherwise false.
- `cited_sentences` and `supported_sentences`: count the reply's sentences that carry an [E#] marker
  (`cited_sentences`), and how many of them are supported by the cited source text (`supported_sentences`). A
  sentence is supported if its claim is stated in the cited text (for C# labels: in any cited text). If no
  sentence has a marker, both are 0.
- `conditions_match` (conditional_answer only, else null): true if the cases the reply distinguishes are the
  attributes the gold evidence splits on and each case's value matches the evidence for that group; false
  otherwise (wrong attribute, wrong value for a group, or a group without evidence given a made-up value).

**clarify**
- `asks_branch_attribute`: true if the question the reply asks is about an attribute in `branch_attributes`;
  false otherwise (including when `branch_attributes` is empty).

**abstain**
- `right_referral`: true if the reply names the office, website or next step that the required facts or the gold
  evidence point to (for example the student's own campus office, the dormitory website, HiKorea). A generic
  "contact the university" or "check the website" counts only when the required facts name nothing more specific.
  False otherwise.

Return one JSON object per item, one per line, with exactly these keys:
{"id": "...", "facts": [...] or null, "wrong_group": true/false/null, "cited_sentences": n or null,
 "supported_sentences": n or null, "conditions_match": true/false/null, "asks_branch_attribute": true/false/null,
 "right_referral": true/false/null, "note": "<= 15 words, only when a call was hard"}
