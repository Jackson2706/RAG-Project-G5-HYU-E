"""G7 / A34 check: the numbers in Report/report/draft.md equal the result files.

Table 1 = evaluator v1 (hyu_test_slices.csv), Table 2 = evaluator v2 (hyu_test_v2_slices.csv + posthoc_branch_detection.csv),
the comparisons table (both evaluators), the slice rates and the exploratory numbers (posthoc.md, dev files).
Run from the repo root: python3 Report/notes/check_report_numbers.py  (prints 'mismatches 0')."""
import csv
import json
from collections import Counter

R = "Report/results/"
BRANCH_EXP = ("conditional_answer", "clarify")
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
d3 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "dev-03/hyu_dev_v2_slices.csv")) if r["slice"] == "all"}
for preset, value in [("A0b", "0.596"), ("A0", "0.362"), ("B0", "0.638"), ("R16", "0.681")]:
    check(close(value, d3[preset]["acceptable_rate"]), "dev-03", preset)
check(close("0.000", d3["A0b"]["unnecessary_clarification_rate"]) and close("0.425", d3["A0"]["unnecessary_clarification_rate"]), "dev-03 unnecessary")
b3 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "dev-03/posthoc_branch_detection.csv")) if r["evaluator"] == "v2"}
check((b3["A0b"]["tp"], b3["A0"]["tp"], b3["A0"]["expected_branching"]) == ("0", "5", "7"), "dev-03 branch recall")
post = open(R + "test-final/posthoc.md").read()
check("A0 10, A3 11, both 10, A0 only 0, A3 only 1 (A3 only: T14-224)" in post, "A0 subset of A3")
check("discordant: A0 only 9, R16 only 1; two-sided exact p = 0.0215" in post and "p = 0.0215" in draft, "McNemar")
check(branch["A3"]["tp"] == "11" and branch["A3"]["predicted_branching"] == "86", "A3 11/86")
a0b = open(R + "dev-03/posthoc.md").read().split("## A0b on")[1]
check(a0b.count("| ABSTAIN |") == 3 and a0b.count("| ANSWER |") == 4, "A0b 3 abstain / 4 answer")
for q, rows in (("T14-032", 7), ("T14-120", 5)):
    check(next(d for d in dev if d["qid"] == q)["branches"] == rows, "A0 replay rows", q)
a0b_v2 = {r["qid"]: r for r in csv.DictReader(open(R + "dev-03/hyu_dev_v2_per_case.csv")) if r["preset"].startswith("A0b") and r["expected"] in BRANCH_EXP}
check(sum(r["predicted"] == "abstain" for r in a0b_v2.values()) == 4 and sum(r["predicted"] == "answer" for r in a0b_v2.values()) == 3, "A0b v2 4/3")
a0b_v1 = {r["qid"]: r for r in csv.DictReader(open(R + "dev-03/hyu_dev_per_case.csv")) if r["preset"].startswith("A0b")}
check(a0b_v1["T14-044"]["predicted"] == "answer" and a0b_v2["T14-044"]["predicted"] == "abstain", "T14-044 v1 answer, v2 abstain")
# Section 9 (course mapping) numbers.
beir = {(r["dataset"], r["experiment"].split("_")[0]): r for r in csv.DictReader(open(R + "2026-11-01_main/retrieval_comparison.csv")) if r["protocol"] == "B"}
for ds, r1, b0 in (("scifact", .651, .716), ("nfcorpus", .300, .346), ("arguana", .452, .598)):
    check(abs(float(beir[(ds, "R1")]["nDCG@10"]) - r1) < 6e-4 and abs(float(beir[(ds, "B0")]["nDCG@10"]) - b0) < 6e-4, "BEIR nDCG", ds)
drop = Counter(r["dataset"] for r in csv.DictReader(open(R + "2026-11-01_main/failure_analysis.csv"))
               if r["experiment"] == "B0_BASIC_DENSE_RAG" and r["protocol"] == "B" and r["primary"] == "dropped_by_selection")
for ds, queries, pct in (("scifact", 300, 13), ("nfcorpus", 323, 14), ("arguana", 1406, 35)):
    check(round(100 * drop[ds] / queries) == pct, "dropped by selection", ds)
ann = [r for r in csv.DictReader(open(R + "2026-11-01_main/offline_comparison.csv")) if r["experiment"].startswith("ANN")]
check(len(ann) == 3 and all(r["ann_recall@10_vs_exact"] == "1.0" and 5 <= float(r["hnsw_search_ms_p50"]) <= 7 for r in ann), "ANN")
check(close("0.736", v1[("B0", "all")]["acceptable_rate"]) and close("0.661", v2[("B0", "all")]["acceptable_rate"]), "slide 43 B0")
b1 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "test-final/posthoc_branch_detection.csv")) if r["evaluator"] == "v1"}
check(b1["R16"]["tp"] == "0" and branch["R16"]["tp"] == "2", "slide 43 R16 0 -> 2")
check(len(json.load(open(R + "index_reports/hyu_20261110_97dc1269_r5.json"))["checks"]) == 15, "VERIFY 15 checks")
# Section 8 (revised method, dev) and test-2.
gate = json.load(open(R + "dev-04/ag_gate.json"))
check(gate["fired"] == 1 and gate["fired_cases"] == ["T14-015"] and gate["override_precision"] == 0.0 and gate["go"] is False, "AG gate")
check(close("0.617", gate["acceptable_AG_AAES_GUARD"]) and close("0.702", gate["acceptable_R16_PROMPTED_CONDITIONAL"])
      and close("0.362", gate["acceptable_A0_AAES"]) and len(gate["breaks"]) == 4, "AG acceptable")
d2 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "dev-02/hyu_dev_v2_slices.csv")) if r["slice"] == "all"}
check(close("0.681", d2["R15"]["acceptable_rate"]) and close("0.681", d2["R16"]["acceptable_rate"])
      and close("0.374", d2["R16"]["macro_f1"]) and close("0.356", d2["R15"]["macro_f1"]), "AG base choice")
def replies(path):
    return {r["qid"]: r["answer"] for r in map(json.loads, open(path)) if r["status"] == "completed"}
r3, r4 = (replies(R + f"{x}/raw/hyu/dev/R16_PROMPTED_CONDITIONAL__-.jsonl") for x in ("dev-03", "dev-04"))
check(sum(r3[q] != r4[q] for q in r3) == 25 and len(r3) == 47, "R16 run-to-run wording 25/47")
L = "Sources/data/HYU/labels/"
check(sum(1 for _ in open(L + "test2/drafts.jsonl")) == 121 and sum(1 for _ in open(L + "test2/selected.jsonl")) == 80
      and 80 - sum(1 for _ in open(L + "test2/excluded_test2.jsonl")) == 75, "test-2 sizes")  # test2.jsonl itself is never opened
t2 = open(L + "test2/agreement/agreement.md").read()
check("| answerability | Cohen's kappa | 0.773291" in t2 and "| expected_behavior | Cohen's kappa | 0.707674" in t2, "test-2 kappa")
hb = json.load(open(R + "test-final/history_bug.json"))["presets"]
check({k.split("_")[0]: v["generated_without_history"] for k, v in hb.items()} == {"A0": 9, "A1": 8, "A3": 2, "A4": 8, "A6": 9, "R9S": 12, "R15": 12}
      and all(v["multi_session"] == 12 for v in hb.values()), "history bug counts")
# Evaluator v3 (A36).
q3 = {r["preset"].split("_")[0]: r for r in csv.DictReader(open(R + "quality_v3/metrics_test.csv"))}
for preset, vals in {"B0": ("0.300", "0.117", "0.265", "0.573", "0.000", None, "0.340"), "R15": ("0.269", "0.133", "0.194", "0.561", "0.000", None, "0.333"),
                     "R16": ("0.258", "0.133", "0.224", "0.520", "0.000", None, "0.267"), "A0": ("0.119", "0.067", "0.125", "0.506", "0.267", "0.096", "0.724"),
                     "G0": ("0.079", "0.383", "0.200", None, "0.000", None, "0.742"), "G1": ("0.463", "0.033", "0.076", "0.880", "0.000", None, "0.491")}.items():
    for col, v in zip(("fact coverage", "wrong-fact rate", "wrong-group rate", "citation support", "correct conditions (branching)", "useful question", "right referral"), vals):
        check((q3[preset][col] in ("", "None")) if v is None else close(v, q3[preset][col]), "v3", preset, col)
check(close("0.417", q3["A0"]["answered (answer cases)"]) and close("0.633", q3["B0"]["answered (answer cases)"])
      and close("0.287", q3["A0"]["coverage when answered"]) and close("0.474", q3["B0"]["coverage when answered"]), "v3 answered")
cmp3 = list(csv.DictReader(open(R + "quality_v3/comparisons.csv")))
for (c, m), (d, lo, hi) in {("A0 vs B0", "fact coverage"): (-0.181, -0.281, -0.085), ("A0 vs R16", "fact coverage"): (-0.139, -0.227, -0.057),
                            ("A0 vs B0", "right referral"): (0.385, 0.174, 0.586), ("A0 vs R16", "right referral"): (0.457, 0.244, 0.657),
                            ("A0 vs B0", "wrong-group rate"): (-0.140, -0.280, 0.001), ("PREREG 2:", "fact coverage"): (-0.185, -0.312, -0.065)}.items():
    r = next(x for x in cmp3 if x["metric"] == m and (x["comparison"] == c or (c.startswith("PREREG") and x["comparison"].startswith("PREREG"))))
    check(all(abs(float(r[k]) - v) < 6e-4 for k, v in (("diff", d), ("ci_low", lo), ("ci_high", hi))), "v3 comparison", c, m)
for preset, ref, base in (("B0", "0.283", 68), ("R15", "0.217", 67), ("R16", "0.174", 76), ("A0", "0.174", 40), ("G0", "0.283", 90), ("G1", "0.435", 66)):
    check(close(ref, q3[preset]["right referral (per abstain case)"]) and float(q3[preset]["answered replies (wrong-group base)"]) == base, "v3 per-case referral", preset)
r = next(x for x in cmp3 if x["comparison"] == "A0 vs B0" and x["metric"] == "right referral (per abstain case)")
check(abs(float(r["diff"]) + 0.109) < 6e-4 and abs(float(r["ci_low"]) + 0.250) < 6e-4 and abs(float(r["ci_high"]) - 0.025) < 6e-4, "v3 referral A0 vs B0")
check(close("0.669", v2[("G0", "all")]["acceptable_rate"]) and close("0.661", v2[("B0", "all")]["acceptable_rate"]), "G0 matched B0 on action")
v3val = json.load(open(R + "quality_v3/validation.json"))["kappa"]
for f, v in (("facts (per fact)", 0.859), ("wrong_group", 0.854), ("right_referral", 0.791), ("all cited sentences supported", 0.656)):
    check(abs(v3val[f]["kappa"] - v) < 6e-4, "v3 kappa", f)
g3_all = json.load(open(R + "quality_v3/validation.json"))["third_judge_gpt"]
check(g3_all["judge"] == "GPT-6.1 in ChatGPT, max thinking" and "GPT-6.1" in draft, "GPT judge name")
g3 = g3_all["fields"]
check(abs(g3["facts (per fact)"]["kappa"] - 0.679) < 6e-4 and abs(g3["facts (per fact)"]["agreement"] - 0.815) < 6e-4 and g3["facts (per fact)"]["pairs"] == 27
      and g3["right_referral"]["kappa"] == 0.0 and g3["right_referral"]["agreement"] == 0.75 and g3["right_referral"]["pairs"] == 4
      and all(g3[f]["agreement"] == 1.0 for f in ("wrong_group", "asks_branch_attribute", "conditions_match"))
      and [g3[f]["pairs"] for f in ("wrong_group", "asks_branch_attribute", "conditions_match")] == [13, 3, 2], "GPT third judge")
# Deck v5/v6 sections 11-13: each number is recomputed from its committed file and must appear in the draft.
D = "Report/slides/deck_v4/"


def says(text, *what):
    check(text in draft, *what, repr(text))


ab = {r["preset"]: r for r in csv.DictReader(open(D + "aaes_plus/dev_ablation.csv"))}
f3 = lambda x: f"{float(x):.3f}"  # noqa: E731
says(f"acceptable on {f3(ab['A0_AAES']['acceptable_rate'])} and keeps {ab['A0_AAES']['kept']} of the {ab['A0_AAES']['needed']} needed", "s11 A0")
for v in ("RBRR", "BBRB", "RLRR", "BBBB"):
    says(f"{v} {f3(ab['AP_' + v]['acceptable_rate'])} keeps {ab['AP_' + v]['kept']}", "s11", v)
sel = json.load(open(D + "aaes_plus/selection.json"))
eligible = sorted((r for r in ab.values() if r["preset"].startswith("AP_") and int(r["kept"]) >= sel["minimum_kept"]), key=lambda r: -int(r["kept"]))
check(sel["choice"] == "AP_RRRL" and len(eligible) == 5 and max(eligible, key=lambda r: float(r["acceptable_rate"]))["preset"] == "AP_RRRL", "s11 selection")
says(f"at least {sel['minimum_kept']:.1f} of {sel['reference']['kept']}", "s11 minimum")
says(", ".join(f"{r['preset'][3:]} {r['kept']}" for r in eligible[:4]) + f", {eligible[4]['preset'][3:]} {eligible[4]['kept']} kept", "s11 eligible")
rr = ab["AP_RRRL"]
says(f"rate, {f3(rr['acceptable_rate'])}: rules", "s11 RRRL")
says(f"{float(rr['llm_calls_mean']):.2f} LLM calls", "s11 calls")
says(f"median {float(rr['fresh_seconds_median']):.2f} s on a fresh", "s11 s")
says(f"against {float(ab['A0_AAES']['fresh_seconds_median']):.2f} s for AAES and {float(ab['AP_BBBB']['fresh_seconds_median']):.2f} s for", "s11 s2")
pooled = {}
for r in csv.DictReader(open(D + "heldout/reply_types.csv")):
    if r["slice"] in ("all", "student_dependent"):
        a = pooled.setdefault((r["preset"], r["slice"]), [0, 0.0, 0.0])
        a[0] += int(r["cases"]); a[1] += float(r["acceptable_rate"]) * int(r["cases"]); a[2] += float(r["unneeded_rate"] or 0) * int(r["cases"])
acc = {k: f"{v[1] / v[0]:.3f}" for k, v in pooled.items()}
un = {k: f"{v[2] / v[0]:.3f}" for k, v in pooled.items()}
check(pooled[("AP_RRRL", "all")][0] == 215 and pooled[("AP_RRRL", "student_dependent")][0] == 70, "s12 sizes")
says(f"acceptable on {acc[('AP_RRRL', 'all')]} of all questions and {acc[('AP_RRRL', 'student_dependent')]} of the 70", "s12 ours")
says(f"(B0 {acc[('B0_BASIC_DENSE_RAG', 'all')]}, R15 {acc[('R15_SELF_QUERY', 'all')]}, R16 {acc[('R16_PROMPTED_CONDITIONAL', 'all')]}, "
     f"G1 {acc[('G1_ORACLE_CONTEXT', 'all')]}; BBBB {acc[('AP_BBBB', 'all')]})", "s12 baselines")
base = ("B0_BASIC_DENSE_RAG", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL", "G1_ORACLE_CONTEXT")
says(f"({min(acc[(b, 'student_dependent')] for b in base)}–{max(acc[(b, 'student_dependent')] for b in base)};\nBBBB {acc[('AP_BBBB', 'student_dependent')]})", "s12 dependent")
says(f"unneeded on {un[('AP_RRRL', 'all')]} (AAES {un[('A0_AAES', 'all')]}, BBBB {un[('AP_BBBB', 'all')]}, baselines "
     f"{min(un[(b, 'all')] for b in base)}–{max(un[(b, 'all')] for b in base)})", "s12 unneeded")
hyp = json.load(open(D + "heldout/hypotheses.json"))
for k, v in hyp["hypotheses"].items():
    says(f"| {k} |", "s12 row")
    says(f"| {v['cases']} | {v['ours']:.3f} | {v['baseline']:.3f} | {v['difference']:+.3f} [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}]".replace("-", "−")
         + f" | {v['p_holm']:.4f} | {v['decision'].replace('_', '-')} |", "s12", k)
sec = {(x["baseline_preset"], x["metric"]): x for x in hyp["secondary"]}
u = sec[("A0_AAES", "unneeded")]; w = sec[("A0_AAES", "wrong_referral")]; t = sec[("A0_AAES", "seconds")]
says(f"({u['difference']:+.3f} [{u['ci_low']:+.3f}, {u['ci_high']:+.3f}])".replace("-", "−"), "s12 unneeded diff")
says(f"({w['difference']:+.3f} [{w['ci_low']:+.3f}, {w['ci_high']:+.3f}])", "s12 referral diff")
says(f"median {t['ours_median']:.1f} s per question against {t['baseline_median']:.1f} s for AAES and\n{sec[('R16_PROMPTED_CONDITIONAL', 'seconds')]['baseline_median']:.1f} s for R16", "s12 seconds")
cs = {(r["preset"], r["slice"]): r for r in csv.DictReader(open(D + "heldout/judge/content_scores.csv"))}
o = cs[("AP_RRRL", "all")]
says(f"covers {f3(o['facts_covered'])} [{f3(o['facts_covered_ci_low'])}, {f3(o['facts_covered_ci_high'])}]", "s12 facts")
says(f"(AAES {f3(cs[('A0_AAES', 'all')]['facts_covered'])}, B0 {f3(cs[('B0_BASIC_DENSE_RAG', 'all')]['facts_covered'])}, R16\n{f3(cs[('R16_PROMPTED_CONDITIONAL', 'all')]['facts_covered'])})", "s12 facts others")
says(f"and {f3(o['wrong_fact_rate'])} of its replies contain a wrong fact (B0 {f3(cs[('B0_BASIC_DENSE_RAG', 'all')]['wrong_fact_rate'])}, R16 {f3(cs[('R16_PROMPTED_CONDITIONAL', 'all')]['wrong_fact_rate'])})", "s12 wrong fact")
says(f"questions {f3(cs[('AP_RRRL', 'student_dependent')]['wrong_group_rate'])} of\nits answers are for the wrong group, against {f3(cs[('B0_BASIC_DENSE_RAG', 'student_dependent')]['wrong_group_rate'])} for B0 and "
     f"{f3(cs[('R16_PROMPTED_CONDITIONAL', 'student_dependent')]['wrong_group_rate'])} for R16", "s12 wrong group")
says(f"AAES+ answers {o['cases']} questions, R16 {cs[('R16_PROMPTED_CONDITIONAL', 'all')]['cases']}", "s12 answered")
gd = {r["slice"]: r for r in csv.DictReader(open(D + "heldout/judge/content_scores_gold.csv"))}
says(f"(G1, {gd['all']['cases']} replies", "s12 gold n")
says(f"covers {f3(gd['all']['facts_covered'])} [{f3(gd['all']['facts_covered_ci_low'])}, {f3(gd['all']['facts_covered_ci_high'])}] of the facts with {f3(gd['all']['citation_support'])}", "s12 gold")
says(f"but {f3(gd['student_dependent']['wrong_group_rate'])} of its answers to student-dependent", "s12 gold wrong group")
says(f"With gold evidence it still covers only\n  {f3(gd['all']['facts_covered'])}", "s9 gold")
says(f"held-out questions {un[('AP_RRRL', 'all')]} of its replies ask", "s9 over-asking")
fu = {r["system"]: r for r in json.load(open(D + "followup/content_v5.json"))["systems"]}
pair = next(x for x in json.load(open(D + "followup/content_v5.json"))["paired"] if x["ours"] == "A0 reply_reask" and x["baseline"] == "B0 one turn")
says(f"cover {fu['A0 reply_only']['facts_covered']:.3f} of the required facts after {fu['A0 reply_only']['turns_mean']:.2f} user turns", "s13 before")
says(f"AAES covers\n{fu['A0 reply_reask']['facts_covered']:.3f} of the facts after {fu['A0 reply_reask']['turns_mean']:.2f} turns", "s13 reask")
says(f"({fu['B0 one turn']['facts_covered']:.3f}; paired difference {pair['diff_facts_covered']:+.3f}\n[{pair['ci95'][0]:+.3f}, {pair['ci95'][1]:+.3f}])".replace("-", "−"), "s13 paired")
v6 = json.load(open(D + "followup_v6/content.json"))
b = v6["phase4_A0_reply_only"][0]
says(f"| AAES, Task 2 (before) | {b['facts_covered']:.3f} | {b['wrong_fact']:.3f} | {b['wrong_group']:.3f} | {b['turns_mean']:.2f} | 10 of 39 |", "s13 row before")
for name, sysname in (("AAES with the fix", "A0 reply_only (v6 fix)"), ("AAES+ with the fix", "AP reply_only (v6 fix)")):
    r = next(x for x in v6["v6"] if x["system"] == sysname)
    says(f"| {name} | {r['facts_covered']:.3f} | {r['wrong_fact']:.3f} | {r['wrong_group']:.3f} | {r['turns_mean']:.2f} | {r['answered_after_one_reply']} of {r['asked_first']} |", "s13", name)
sc = [r for r in csv.DictReader(open(D + "followup/scores.csv")) if r["system"] == "A0 reply_only"]  # items.jsonl is not committed
check(sum(r["user_turns"] == "2" and r["reply_type"] in ("answer", "conditional_answer") for r in sc) == 10 and len(sc) == 39, "s13 answered after one reply (before)")
print("checked", n, "mismatches", bad)
