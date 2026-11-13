"""G7 check: every Table 1 value and slice rate in Report/report/draft.md equals Report/results/test-final/hyu_test_slices.csv.
Run from the repo root: python3 Report/notes/check_report_numbers.py  (prints 'mismatches 0')."""
import csv

sl = {(r["preset"].split("_")[0], r["slice"]): r for r in csv.DictReader(open("Report/results/test-final/hyu_test_slices.csv"))}
draft = open("Report/report/draft.md").read()
cols = ["answered_rate", "action_accuracy", "acceptable_rate", "macro_f1", "unnecessary_clarification_rate", "applicable_recall@5", "aer"]
rows = {"B0 basic": "B0", "R5 hybrid": "R5", "R9-scope prefilter": "R9S", "R15 self": "R15", "R16 prompted": "R16", "G0 closed": "G0",
        "G1 gold": "G1", "**A0 AAES**": "A0", "A1 hard": "A1", "A2 oracle": "A2", "A3 always": "A3", "A4 question": "A4", "A6 no": "A6"}
bad = n = 0
for line in draft.splitlines():
    for key, preset in rows.items():
        if line.startswith("| " + key) and "0." in line:
            for col, cell in zip(cols, [c.strip() for c in line.strip("|").split("|")][1:]):
                value, ref = cell.split()[0], sl[(preset, "all")][col]
                n += 1
                if not (ref == "N/A" if value == "n/a" else abs(float(value) - float(ref)) < 6e-4):
                    bad += 1
                    print("MISMATCH", preset, col, value, ref)
for preset, slice_, value in [("A0", "conditional", .333), ("A0", "negative", .292), ("A0", "unconditional", .217), ("A0", "temporal", .167),
                              ("A0", "multi_session", .167), ("B0", "conditional", .704), ("B0", "negative", .708),
                              ("B0", "unconditional", .717), ("B0", "temporal", .75), ("B0", "multi_session", .917)]:
    n += 1
    if abs(float(sl[(preset, slice_)]["acceptable_rate"]) - value) > 6e-4:
        bad += 1
        print("MISMATCH slice", preset, slice_)
print("checked", n, "mismatches", bad)
