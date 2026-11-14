"""G7 / A34 check: the numbers in Report/report/draft.md equal the result files.

Table 1 = evaluator v1 (hyu_test_slices.csv), Table 2 = evaluator v2 (hyu_test_v2_slices.csv + posthoc_branch_detection.csv),
the comparisons table (both evaluators), the slice rates and the exploratory numbers (posthoc.md, dev files).
Run from the repo root: python3 Report/notes/check_report_numbers.py  (prints 'mismatches 0')."""
import csv
import json

R = "Report/results/"
draft = open("Report/report/draft.md").read()
ROWS = {"B0 basic": "B0", "R5 hybrid": "R5", "R9-scope prefilter": "R9S", "R15 self": "R15", "R16 prompted": "R16", "G0 closed": "G0",
        "G1 gold": "G1", "**A0 AAES**": "A0", "A1 hard": "A1", "A2 oracle": "A2", "A3 always": "A3", "A4 question": "A4", "A6 no": "A6"}
bad = n = 0


def slices(name):
    return {(r["preset"].split("_")[0], r["slice"]): r for r in csv.DictReader(open(R + "test-final/" + name))}


def check(ok, *what):
    global bad, n
    n += 1
    if not ok:
        bad += 1
        print("MISMATCH", *what)


def close(value, ref):
    return ref == "N/A" if value == "n/a" else abs(float(value) - float(ref)) < 6e-4


def table(caption):
    """Rows of the markdown table that follows the caption line."""
    lines = draft[draft.index(caption):].splitlines()[1:]
    start = next(i for i, l in enumerate(lines) if l.startswith("|"))
    out = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        out.append([c.strip() for c in line.strip("|").split("|")])
    return out


v1, v2 = slices("hyu_test_slices.csv"), slices("hyu_test_v2_slices.csv")
branch = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "test-final/posthoc_branch_detection.csv")) if r["evaluator"] == "v2"}
COLS1 = ["answered_rate", "action_accuracy", "acceptable_rate", "macro_f1", "unnecessary_clarification_rate", "applicable_recall@5", "aer"]
COLS2 = ["answered_rate", "action_accuracy", "acceptable_rate", "macro_f1", "unnecessary_clarification_rate", "aer"]
for caption, ref, cols in (("**Table 1.", v1, COLS1), ("**Table 2.", v2, COLS2)):
    rows = table(caption)
    check(len(rows) == 13, caption, "rows", len(rows))
    for cells in rows:
        preset = ROWS[next(k for k in ROWS if cells[0].startswith(k.strip("*")) or cells[0] == k)]
        for col, cell in zip(cols, cells[1:]):
            check(close(cell.split()[0], ref[(preset, "all")][col]), caption, preset, col, cell)
        if caption == "**Table 2.":
            b = branch[preset]
            check(cells[7] == f"{b['tp']}/{b['expected_branching']}", "branch recall", preset, cells[7])
            prec = f"{b['tp']}/{b['predicted_branching']}" if b["predicted_branching"] != "0" else "n/a"
            check(cells[8] == prec, "branch precision", preset, cells[8])

for split_file, tag in (("hyu_test_comparisons_paired.csv", "v1"), ("hyu_test_v2_comparisons_paired.csv", "v2")):
    rows = list(csv.DictReader(open(R + "test-final/" + split_file)))
    f1 = next(r for r in rows if r["metric"] == "macro_f1")
    text = f"{float(f1['diff']):+.3f} [{float(f1['ci_low']):+.3f}, {float(f1['ci_high']):+.3f}], p = {float(f1['p']):.3f}, Holm {float(f1['p_holm']):.3f}"
    check(text.replace("-", "−") in draft, tag, "comparison 3", text)
    aer = next(r for r in rows if r["metric"] == "aer")
    check(aer["cases"] == "2" and float(aer["diff"]) == 0 and float(aer["p"]) == 1.0, tag, "comparison 1")

for preset, slice_, value in [("A0", "conditional", .333), ("A0", "negative", .292), ("A0", "unconditional", .217), ("A0", "temporal", .167),
                              ("A0", "multi_session", .167), ("B0", "conditional", .704), ("B0", "negative", .708),
                              ("B0", "unconditional", .717), ("B0", "temporal", .75), ("B0", "multi_session", .917)]:
    check(abs(float(v1[(preset, slice_)]["acceptable_rate"]) - value) < 6e-4, "slice", preset, slice_)

# Exploratory numbers (posthoc.md / posthoc csvs, dev diagnostics, validation, index counts).
by_exp = {(r["preset"].split("_")[0], r["expected"]): r for r in csv.DictReader(open(R + "test-final/posthoc_by_expected.csv")) if r["evaluator"] == "v2"}
for preset, expected, value, cases in [("A0", "conditional_answer", ".556", 9), ("A0", "clarify", ".833", 6), ("R16", "conditional_answer", ".222", 9),
                                       ("A0", "answer", ".167", 60), ("B0", "answer", ".667", 60), ("A0", "abstain", ".239", 46), ("B0", "abstain", ".870", 46)]:
    r = by_exp[(preset, expected)]
    check(close(value, r["acceptable_rate"]) and int(r["cases"]) == cases, "by expected", preset, expected)
check(all(by_exp[(p, "clarify")]["acceptable_rate"] == "0.000" for p in ("B0", "R5", "R9S", "R15", "R16")), "baselines clarify 0")
a0 = {r["count"]: int(r["value"]) for r in csv.DictReader(open(R + "test-final/posthoc_a0.csv"))}
for key, value in [("A0 CLARIFY", 52), ("A0 CLARIFY asks for campus", 35), ("A0 CLARIFY asks for degree level", 7),
                   ("A0 CLARIFY asks for academic status", 5), ("A0 CLARIFY asks for student type", 3), ("A0 CLARIFY asks for TOPIK level", 2),
                   ("A0 CLARIFY on cases labelled abstain", 27), ("cases labelled abstain", 46),
                   ("cases that need branching (labelled conditional_answer or clarify)", 15)]:
    check(a0[key] == value, "a0", key)
conf = {r["expected"]: r for r in csv.DictReader(open(R + "test-final/hyu_test_v2_actions_confusion.csv")) if r["preset"] == "A0_AAES" and r["slice"] == "all"}
check([conf["answer"][k] for k in ("answer", "conditional_answer", "clarify", "abstain")] == ["8", "17", "20", "15"], "confusion answer row")
check(conf["abstain"]["abstain"] == "11" and conf["abstain"]["clarify"] == "27", "confusion abstain row")
check(sum(int(conf[e]["conditional_answer"]) for e in conf) == 29, "A0 conditional 29")
dev = [json.loads(l) for l in open(R + "dev-02/a0_decisions_dev.jsonl")]
check(sum(d["action"] == d["saved_action"] for d in dev) == 47, "dev replay 47/47")
check(sum(d["action"] == "CLARIFY" and d["reason"] == "different_procedures" for d in dev) == 16, "dev different_procedures 16")
check(sum(d["action"] == "CLARIFY" and d["reason"] == "many_branches" for d in dev) == 5, "dev many_branches 5")
check(sum("campus" in (d["branch_attributes"] or []) for d in dev) == 25, "dev campus branched 25")
empty = [d for d in dev if d["campus_branch_without_evidence"]]
check(len(empty) == 20 and sum(d["action"] == "CLARIFY" for d in empty) == 14, "dev campus empty 20/14")
val = json.load(open(R + "dev-02/v2_validation_summary.json"))
check(val["n"] == 100 and abs(val["kappa"] - 0.899) < 6e-4 and abs(val["agreement"] - 0.93) < 1e-9, "validation")
dev_v1 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "dev-02/hyu_dev_slices.csv")) if r["slice"] == "all"}
check(close("0.362", dev_v1["A0"]["acceptable_rate"]) and close("0.574", dev_v1["B0"]["acceptable_rate"]), "dev v1 A0/B0")
tags = json.load(open(R + "index_reports/r5_campus_tags.json"))
check(tags["seoul_site_default"] + tags["erica_site_default"] == 1775 and tags["both_campuses_national_rule"] == 92, "campus tags")
check(v2[("G0", "all")]["acceptable_rate"].startswith("0.669"), "G0 v2 base rate")
print("checked", n, "mismatches", bad)
