"""Build the adjudication sheet (PLAYBOOK A31 order, v1.3 rules A32).

Run from Sources/: python -m labeling.adjudication_sheet <out_dir> [flags.json] [proposals.json]
Proposals (flagged 01-03 rows only) go in proposed_* columns; the human fills final_* or writes "yes" in accept_proposal.
"""
import csv, glob, json, sys
from pathlib import Path

L = Path("data/HYU/labels")
DOCS = {}
for line in open("data/HYU/snapshots/hyu-20261110-97dc1269/documents.jsonl"):
    d = json.loads(line)
    DOCS[d["doc_id"]] = d


def load(pattern):
    rows = {}
    for f in sorted(glob.glob(str(L / pattern))):
        for line in open(f):
            r = json.loads(line)
            if "expected_behavior" in r:
                rows[r["case_id"]] = r
    return rows


def spans(evidence):
    out = []
    for e in evidence:
        d = DOCS.get(e["doc_id"])
        text = d["text"][e["char_start"]:e["char_end"]].replace("\n", " ") if d else "?"
        date = (d.get("post_date") or "") if d else ""
        out.append(f"[{e['doc_id'][:8]} {d['campus'] if d else ''} {date[:10]} {e['char_start']}-{e['char_end']}] {text[:400]}")
    return "\n".join(out)


OPEN = {"T14-113": "10.4.1, 10.4.5", "T14-026": "10.4.5", "T14-130": "11.6, 10.4.3, 10.4.4", "T14-203": "11.3",
        "T14-221": "11.4", "T14-120": "11.4", "T14-136": "11.1",
        **{c: "11.1" for c in ("T14-170", "T14-174", "T14-175", "T14-176", "T14-182", "T14-187")},
        **{c: "11.2" for c in ("T14-173", "T14-190", "T14-205", "T14-208")}}


def rule(a, b):
    rules = []
    if a["answerability"] != b["answerability"]:
        neg = {"partial", "unanswerable", "external_only"}
        old = a["outdated_evidence"] or b["outdated_evidence"]
        rules.append("10.1 term" if old else "")
        rules.append("10.3 negative precedence" if {a["answerability"], b["answerability"]} & {"external_only", "unanswerable"} else "9.1 facts counted")
    if sorted(a["branch_attributes"]) != sorted(b["branch_attributes"]):
        rules.append("10.2 branch needs a split")
    if a["expected_behavior"] != b["expected_behavior"] and not rules:
        rules.append("9.3 / 10.2 behaviour")
    return "; ".join(r for r in rules if r)


def label(r):
    return f"{r['answerability']} / {r['expected_behavior']} / branches {r['branch_attributes']} / acceptable {r['acceptable_behaviors']}"


COLS = ["section", "case_id", "question", "stated_profile", "rule", "v13_rule_or_open_question", "annotator_a", "label_a", "facts_a",
        "evidence_a", "notes_a", "annotator_b", "label_b", "facts_b", "evidence_b", "notes_b",
        "proposed_answerability", "proposed_expected_behavior", "proposed_acceptable_behaviors",
        "proposed_branch_attributes", "proposed_rule", "accept_proposal", "final_answerability", "final_expected_behavior", "final_acceptable_behaviors", "final_branch_attributes",
        "final_evidence_note", "adjudicator"]


def row(section, a, b=None, rule_text=None):
    r = {"section": section, "case_id": a["case_id"], "question": a["question"], "stated_profile": json.dumps(a["stated_profile"]),
         "rule": rule_text if rule_text is not None else rule(a, b), "v13_rule_or_open_question": OPEN.get(a["case_id"], ""),
         "annotator_a": a["annotator"], "label_a": label(a), "facts_a": "\n".join(a["required_facts"]),
         "evidence_a": spans(a["gold_evidence"]), "notes_a": a.get("notes", "")}
    if b:
        r |= {"annotator_b": b["annotator"], "label_b": label(b), "facts_b": "\n".join(b["required_facts"]),
              "evidence_b": spans(b["gold_evidence"]), "notes_b": b.get("notes", "")}
    return r


def differ(a, b):
    return (a["answerability"], a["expected_behavior"], sorted(a["branch_attributes"])) != \
           (b["answerability"], b["expected_behavior"], sorted(b["branch_attributes"]))


codex, claude, sonnet = load("annot_codex/batch_*.jsonl"), load("annot_claude/part_*.jsonl"), load("annot_sonnet/batch_*.jsonl")
rows = [row("1 known (Codex v1.1 vs Opus v1.1)", codex[c], claude[c]) for c in sorted(codex.keys() & claude.keys()) if differ(codex[c], claude[c])]
part2 = [c for c in sorted(sonnet.keys() & claude.keys()) if differ(sonnet[c], claude[c])]
rows += [row("2 part 2 (Sonnet v1.2 vs Opus v1.2)", sonnet[c], claude[c]) for c in part2]
flags = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else []
proposals = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
for f in flags:
    r = row("3 flagged Codex 01-03 (v1.2 check)", codex[f["case_id"]], rule_text="; ".join(f["flags"]))
    if f["case_id"] in proposals:
        ans, beh, acc, br, why = proposals[f["case_id"]]
        r |= {"proposed_answerability": ans, "proposed_expected_behavior": beh, "proposed_acceptable_behaviors": json.dumps(acc),
              "proposed_branch_attributes": json.dumps(br), "proposed_rule": why}
    rows.append(r)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
with open(out / "adjudication_sheet.csv", "w", newline="", encoding="utf-8") as h:
    w = csv.DictWriter(h, fieldnames=COLS); w.writeheader(); w.writerows(rows)
print({s: sum(r["section"] == s for r in rows) for s in dict.fromkeys(r["section"] for r in rows)})
