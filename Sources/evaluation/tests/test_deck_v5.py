"""Offline deck analysis on synthetic labels and saved runs; no frozen labels or model calls."""

import csv
import hashlib
import json
import re

import pytest

from scripts import deck_v5 as deck

AAES, OURS, COND, GOLD = "A0_AAES", "AP_BOTH", "R16_PROMPTED_CONDITIONAL", "G1_ORACLE_CONTEXT"


def case(qid, expected="clarify", acceptable=None, **extra):
    return {"case_id": qid, "question": f"Question {qid}?", "snapshot_id": "synthetic",
            "expected_behavior": expected, "acceptable_behaviors": acceptable or [expected],
            "slice": "conditional" if expected in deck.BRANCHING else "plain",
            "required_facts": ["fact one", "fact two"], "gold_profile": {"campus": "seoul"},
            "branch_attributes": ["campus"], "gold_evidence": [{"doc_id": "D1", "char_start": 0, "char_end": 8}],
            "inapplicable_evidence": [{"doc_id": "D1", "char_start": 9, "char_end": 14}], **extra}


def rec(qid, **extra):
    return {"qid": qid, "status": "completed", "answer": f"Reply to {qid} [E2].", "llm_calls": 2, "total_ms": 2500,
            "behavior": "abstain", "cited": [{"doc_id": "D1", "source_spans": [[0, 8]]}], **extra}


def save_run(root, run_id, splits):
    """splits: split -> preset -> [(case, reply type, saved record)]."""
    labels, tasks = [], []
    for split, per in splits.items():
        folder = root / run_id / "raw" / "hyu" / split
        folder.mkdir(parents=True)
        for preset, rows in per.items():
            tasks.append(f"hyu/{split}/{preset}__-")
            deck.write_jsonl(folder / f"{preset}__-.jsonl", [r for _, _, r in rows])
            labels += [{"preset": preset, "qid": c["case_id"], "label": kind,
                        "reply_sha": deck.reply_action.reply_sha(r["answer"])} for c, kind, r in rows if kind is not None]
    deck.write_jsonl(root / run_id / "reply_actions_v2.jsonl", labels)
    deck.write_json(root / run_id / "run_manifest.json", {"tasks": tasks})


@pytest.fixture
def offline(tmp_path, monkeypatch):
    labels = {}
    monkeypatch.setattr(deck, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(deck, "OUT", tmp_path / "slides")
    monkeypatch.setattr(deck.hyu_suite, "load_cases", lambda split: labels[split])
    monkeypatch.setattr(deck.hyu_suite, "snapshot_dir", lambda _: tmp_path / "snapshot")
    (tmp_path / "snapshot").mkdir()
    deck.write_jsonl(tmp_path / "snapshot" / "documents.jsonl", [{"doc_id": "D1", "text": "fact one other group"}])

    def forbidden(*args, **kwargs):
        pytest.fail("offline analysis called an LLM")

    monkeypatch.setattr(deck.reply_action, "llm_label", forbidden)
    return labels


@pytest.mark.parametrize("expected,acceptable,kind,flags", [
    ("clarify", ["clarify", "conditional_answer"], "conditional_answer", (True, True, True, False, False)),
    ("conditional_answer", ["conditional_answer"], "answer", (False, True, False, False, False)),
    ("answer", ["answer"], "clarify", (False, False, False, True, False)),
    ("answer", ["answer", "conditional_answer"], "conditional_answer", (True, False, False, False, False)),
    ("abstain", ["abstain"], "conditional_answer", (False, False, False, True, False)),
    ("answer", ["answer"], "abstain", (False, False, False, False, True)),
    ("abstain", ["abstain"], "abstain", (True, False, False, False, False)),
])
def test_case_definitions(expected, acceptable, kind, flags):
    score = deck.case_score(case("C1", expected, acceptable), rec("C1"), kind)
    assert tuple(score[k] for k in ("acceptable", "needed", "kept", "unneeded", "wrong_referral")) == flags
    assert score["student_dependent"] == (expected in deck.BRANCHING)
    assert score["llm_calls"] == 2 and score["seconds"] == 2.5
    assert deck.student_dependent(case("C2", student_dependent=False)) is False
    assert deck.student_dependent(case("C3", "answer", student_dependent=True)) is True


def test_summary_hand_computed():
    """Four cases: two needed, one kept, one unneeded, one wrong referral -> 1/2, 1/4, 1/4."""
    rows = [deck.case_score(case(str(i), expected), rec(str(i)), predicted) for i, (expected, predicted) in enumerate([
        ("clarify", "clarify"), ("conditional_answer", "answer"), ("answer", "clarify"), ("answer", "abstain")])]
    result = deck.summarize(rows)
    assert result["cases"] == 4 and result["needed"] == 2 and result["kept"] == 1
    assert result["acceptable_rate"] == 0.25 and result["kept_rate"] == 0.5
    assert result["unneeded_rate"] == result["wrong_referral_rate"] == 0.25
    assert deck.summarize([])["kept_rate"] is None


def test_selection_gate_and_ties():
    def row(p, kept, acceptable, calls):
        return {"preset": p, "kept": kept, "acceptable_rate": acceptable, "llm_calls_mean": calls}

    rows = [row(AAES, 10, 0.6, 1), row("AP_FAIL", 7, 1.0, 0), row("AP_EXPENSIVE", 9, 0.9, 4),
            row("AP_CHEAP", 8, 0.9, 2), row("AP_LOW", 10, 0.8, 0)]
    selection = deck.select_version(rows)
    assert selection["choice"] == "AP_CHEAP" and selection["minimum_kept"] == 8
    assert not next(r for r in selection["candidates"] if r["preset"] == "AP_FAIL")["eligible"]
    assert deck.select_version(rows[:2])["choice"] is None
    with pytest.raises(ValueError, match="A0_AAES"):
        deck.select_version(rows[1:])


def test_ablation_combines_splits_times_and_selects(tmp_path, offline, capsys):
    offline.update(dev=[case("D1"), case("D2", "answer")], dev2=[case("E1")])
    for run_id, split in (("first", "dev"), ("second", "dev2")):
        save_run(deck.RESULTS_DIR, run_id, {split: {p: [(c, c["expected_behavior"], rec(c["case_id"])) for c in offline[split]]
                                                   for p in (AAES, OURS)}})
    timing = tmp_path / "timing.csv"
    timing.write_text(f"preset,seconds\n{OURS},4\n{OURS},8\n")
    assert deck.main(["ablation", "--runs", "first,second", "--timing", str(timing)]) == 0
    table = {r["preset"]: r for r in csv.DictReader((deck.OUT / "aaes_plus" / "dev_ablation.csv").open())}
    assert table[OURS]["cases"] == "3" and table[OURS]["fresh_seconds_median"] == "6.0"
    assert table[AAES]["fresh_seconds_median"] == ""
    assert table[OURS]["kept_rate"] == "1.0" and table[OURS]["llm_calls_mean"] == "2"
    assert deck.main(["select"]) == 0
    assert deck.main(["select"]) == 0  # source provenance survives repeated selection
    assert json.loads((deck.OUT / "aaes_plus" / "selection.json").read_text())["choice"] == OURS
    assert OURS in capsys.readouterr().out
    with pytest.raises(SystemExit):
        deck.main(["ablation", "--runs", "first", "--splits", "test3"])


def test_components_hand_computed_and_exports(offline):
    """8 cases: detail 2/3; split TP=3 FP=2 FN=1 -> P=3/5 R=3/4 F1=2/3; reply accuracy=4/8."""
    rows = [
        (case("D1"), "answer", rec("D1", action="ABSTAIN", aaes_plus={
            "clarify_attribute": "campus", "branch_attributes": ["degree_level"]})),
        (case("D2", "conditional_answer"), "conditional_answer", rec("D2", action="ANSWER", aaes_plus={
            "branch_attributes": ["visa", "campus"]})),
        (case("D3"), "clarify", rec("D3", action="ANSWER", aaes_plus={})),
        (case("E1", "answer", branch_attributes=[]), "answer", rec("E1", action="CLARIFY", aaes_plus={
            "clarify_attribute": "campus"})),
        (case("E2", "abstain"), "abstain", rec("E2", action="CONDITIONAL", aaes_plus={
            "clarify_attribute": "", "branch_attributes": []})),
        (case("E3", "conditional_answer", branch_attributes=["visa"]), "clarify", rec("E3", action="ABSTAIN", aaes_plus={
            "clarify_attribute": None, "branch_attributes": ["visa"]})),
        (case("E4", "answer", acceptable=["answer", "clarify"]), "clarify", rec("E4", action="ANSWER", aaes_plus={
            "branch_attributes": None})),
        (case("E5", "answer"), "abstain", rec("E5", action="ANSWER", aaes_plus=None)),
    ]
    presets = (AAES, OURS, "AP_OTHER")
    for run_id, split, selected in (("first", "dev", rows[:3]), ("second", "dev2", rows[3:])):
        offline[split] = [c for c, _, _ in selected]
        # Unrelated planned presets need no complete coverage for a component table.
        save_run(deck.RESULTS_DIR, run_id, {split: {**{p: selected for p in presets}, COND: [
            (selected[0][0], None, selected[0][2])]}})
    assert deck.main(["components", "--runs", "first,second"]) == 0
    folder = deck.OUT / "aaes_plus"
    table = json.loads((folder / "components_v5.json").read_text())
    assert [r["preset"] for r in table] == sorted(presets)
    expected_confusion = {(gold, predicted): 0 for gold in deck.reply_action.LABELS for predicted in deck.reply_action.LABELS}
    for c, kind, _ in rows:
        expected_confusion[(c["expected_behavior"], kind)] += 1
    for row in table:
        assert row["cases"] == 8
        assert row["step3_detail_cases"] == 3 and row["step3_detail_hits"] == 2
        assert row["step3_detail_hit_rate"] == pytest.approx(2 / 3)
        assert (row["step3_split_tp"], row["step3_split_fp"], row["step3_split_fn"]) == (3, 2, 1)
        assert row["step3_split_precision"] == pytest.approx(3 / 5)
        assert row["step3_split_recall"] == pytest.approx(3 / 4)
        assert row["step3_split_f1"] == pytest.approx(2 / 3)
        assert row["step4_correct"] == 4 and row["step4_accuracy"] == 0.5
        cells = {k: v for k, v in row.items() if k.startswith("step4_expected_")}
        assert cells == {f"step4_expected_{gold}__predicted_{predicted}": n
                         for (gold, predicted), n in expected_confusion.items()}
    with (folder / "components_v5.csv").open() as handle:
        assert list(csv.DictReader(handle)) == [{k: str(v) for k, v in row.items()} for row in table]
    before = (folder / "components_v5.json").read_bytes()
    assert deck.main(["components", "--runs", "first,second", "--splits", "dev,dev2"]) == 0
    assert (folder / "components_v5.json").read_bytes() == before


@pytest.mark.parametrize("expected,action,precision,recall,f1", [
    ("answer", "ANSWER", None, None, None),
    ("answer", "CLARIFY", 0, None, 0),
    ("clarify", "ANSWER", None, 0, 0),
])
def test_components_zero_denominators(offline, expected, action, precision, recall, f1):
    """No chosen detail -> null hit rate; FP-only or FN-only F1 is 0, all negatives -> null."""
    offline["dev"] = [case("D1", expected)]
    save_run(deck.RESULTS_DIR, "dev", {"dev": {p: [(offline["dev"][0], "answer", rec("D1", action=action))]
                                              for p in (AAES, OURS)}})
    assert deck.main(["components", "--runs", "dev", "--splits", "dev"]) == 0
    folder = deck.OUT / "aaes_plus"
    table = json.loads((folder / "components_v5.json").read_text())
    for row in table:
        assert row["step3_detail_cases"] == row["step3_detail_hits"] == 0
        assert row["step3_detail_hit_rate"] is None
        assert row["step3_split_precision"] == precision
        assert row["step3_split_recall"] == recall
        assert row["step3_split_f1"] == f1
    with (folder / "components_v5.csv").open() as handle:
        assert list(csv.DictReader(handle)) == [{k: "" if v is None else str(v) for k, v in r.items()} for r in table]


def test_components_rejects_heldout_before_loading(offline, capsys):
    # The fixture has no test labels: the dev-only guard must run before load_runs.
    with pytest.raises(SystemExit) as error:
        deck.main(["components", "--runs", "unused", "--splits", "dev,test"])
    assert error.value.code == 2
    assert "dev/dev2 only" in capsys.readouterr().err
    assert not deck.OUT.exists()


def test_components_requires_reference_and_every_planned_candidate(offline, capsys):
    offline["dev"] = [case("D1")]
    save_run(deck.RESULTS_DIR, "dev", {"dev": {OURS: [(offline["dev"][0], "clarify", rec("D1"))]}})
    deck.write_json(deck.RESULTS_DIR / "dev" / "status.json", {"hyu/dev/AP_MISSING__-": {"status": "PENDING"}})
    with pytest.raises(SystemExit) as error:
        deck.main(["components", "--runs", "dev", "--splits", "dev"])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert AAES in message and "AP_MISSING" in message and "dev/D1" in message
    assert not deck.OUT.exists()


@pytest.mark.parametrize("command_name", ["ablation", "components"])
@pytest.mark.parametrize("preset", [AAES, OURS])
@pytest.mark.parametrize("gap", ["partial", "failed", "missing_label", "stale_label", "missing_file", "no_labels"])
def test_selection_rejects_incomplete_coverage(offline, capsys, preset, gap, command_name):
    offline.update(dev=[case("D1"), case("D2")], dev2=[case("E1")])
    splits = {split: {p: [(c, "clarify", rec(c["case_id"])) for c in cases] for p in (AAES, OURS)}
              for split, cases in offline.items()}
    save_run(deck.RESULTS_DIR, "dev", splits)
    assert deck.main([command_name, "--runs", "dev"]) == 0
    selection_path = deck.OUT / "aaes_plus" / ("selection.json" if command_name == "ablation" else "components_v5.json")
    before = selection_path.read_bytes()
    csv_path = selection_path.with_name("dev_ablation.csv" if command_name == "ablation" else "components_v5.csv")
    before_csv = csv_path.read_bytes()
    raw_path = deck.RESULTS_DIR / "dev" / "raw" / "hyu" / "dev" / f"{preset}__-.jsonl"
    label_path = deck.RESULTS_DIR / "dev" / "reply_actions_v2.jsonl"
    if gap == "partial":
        deck.write_jsonl(raw_path, [rec("D1")])
        (raw_path.parent.parent / "dev2" / raw_path.name).unlink()  # just one completed AP case remains
    elif gap == "failed":
        deck.write_jsonl(raw_path, [rec("D1"), rec("D2", status="error")])
    elif gap == "missing_file":
        raw_path.unlink()
    elif gap == "no_labels":
        label_path.unlink()
    else:
        labels = deck.read_rows(label_path)
        if gap == "missing_label":
            labels = [r for r in labels if (r["preset"], r["qid"]) != (preset, "D2")]
        else:
            next(r for r in labels if (r["preset"], r["qid"]) == (preset, "D2"))["reply_sha"] = "stale"
        deck.write_jsonl(label_path, labels)
    capsys.readouterr()
    commands = [[command_name, "--runs", "dev"]]
    if command_name == "ablation":
        commands.append(["select"])
    for command in commands:
        with pytest.raises(SystemExit) as error:
            deck.main(command)
        assert error.value.code == 2
        message = capsys.readouterr().err
        assert preset in message and "dev/D2" in message
        if gap == "partial":
            assert "dev2/E1" in message
        assert selection_path.read_bytes() == before
        assert csv_path.read_bytes() == before_csv
    selection_path.unlink()
    csv_path.unlink()
    with pytest.raises(SystemExit):
        deck.main([command_name, "--runs", "dev"])
    assert not selection_path.exists()
    assert not csv_path.exists()


@pytest.mark.parametrize("change", ["partial_table", "missing_candidate", "no_provenance"])
def test_select_rejects_unverifiable_table(offline, capsys, change):
    offline["dev"] = [case("D1"), case("D2")]
    save_run(deck.RESULTS_DIR, "dev", {"dev": {p: [(c, "clarify", rec(c["case_id"])) for c in offline["dev"]]
                                              for p in (AAES, OURS)}})
    deck.main(["ablation", "--runs", "dev", "--splits", "dev"])
    selection_path = deck.OUT / "aaes_plus" / "selection.json"
    table_path = selection_path.with_name("dev_ablation.csv")
    if change == "no_provenance":
        deck.write_json(selection_path, {"choice": OURS})
    else:
        with table_path.open() as handle:
            rows = list(csv.DictReader(handle))
        if change == "partial_table":
            next(r for r in rows if r["preset"] == OURS)["cases"] = "1"
        else:
            rows = [r for r in rows if r["preset"] != OURS]
        deck.write_csv(table_path, rows)
    before = selection_path.read_bytes()
    with pytest.raises(SystemExit):
        deck.main(["select"])
    assert "rerun ablation" in capsys.readouterr().err
    assert selection_path.read_bytes() == before


def test_loader_uses_latest_completed_and_matching_v2_hash(offline):
    c = case("D1")
    offline["dev"] = [c]
    old, latest = rec("D1", answer="old"), rec("D1", answer="latest")
    save_run(deck.RESULTS_DIR, "dev", {"dev": {AAES: [(c, "abstain", old), (c, "clarify", latest),
                                                           (c, None, rec("D1", status="error"))]}})
    path = deck.RESULTS_DIR / "dev" / "reply_actions_v2.jsonl"
    rows = deck.read_rows(path)
    deck.write_jsonl(path, [*rows, rows[0]])  # a stale cache line must not override the latest reply's label
    cases, records, types = deck.load_runs(["dev"], ["dev"])
    assert records[AAES][("dev", "D1")] == latest
    assert types[AAES][("dev", "D1")] == "clarify"
    assert cases[("dev", "D1")] == c


def test_heldout_balances_every_preset_and_splits(offline):
    offline.update(test3=[case("T1"), case("T2", "answer")], test2=[case("U1"), case("U2", "answer")])
    splits = {}
    for split, cases in offline.items():
        splits[split] = {p: [(c, "clarify" if p == AAES and c["expected_behavior"] == "clarify" else "answer", rec(c["case_id"]))
                             for c in cases] for p in (AAES, OURS, COND, GOLD)}
    c = offline["test3"][1]
    splits["test3"][GOLD][1] = (c, None, rec(c["case_id"]))
    splits["test2"][GOLD] = splits["test2"][GOLD][:1]  # absent record as well as absent v2 label
    save_run(deck.RESULTS_DIR, "held", splits)
    assert deck.main(["heldout", "--run", "held", "--ours", OURS]) == 0
    report = json.loads((deck.OUT / "heldout" / "hypotheses.json").read_text())
    assert report["cases"] == 2 and report["cases_by_split"] == {"test3": 1, "test2": 1}
    assert {r["case_id"] for r in report["dropped_unbalanced"]} == {"T2", "U2"}
    assert all(r["missing_presets"] == [GOLD] for r in report["dropped_unbalanced"])
    h = report["hypotheses"]
    assert h["H1"]["difference"] == -1 and h["H1"]["ci_low"] == h["H1"]["ci_high"] == -1
    assert h["H2"]["decision"] == "not_demonstrated" and h["H2"]["difference"] == -1
    assert all("p_holm" in r for r in h.values())
    table = list(csv.DictReader((deck.OUT / "heldout" / "reply_types.csv").open()))
    assert {r["preset"] for r in table} == {AAES, OURS, COND, GOLD}
    assert {r["split"] for r in table} == {"test3", "test2"}
    assert all(r["cases"] == "1" for r in table)


@pytest.mark.parametrize("metadata", ["tasks", "sessions", "status"])
def test_loader_uses_planned_presets_for_requested_splits(offline, metadata):
    offline["test3"] = [case("T1")]
    save_run(deck.RESULTS_DIR, "held", {"test3": {OURS: [(offline["test3"][0], "answer", rec("T1"))]}})
    run = deck.RESULTS_DIR / "held"
    task = f"hyu/test3/{GOLD}__-"
    unrelated = ["hyu/dev/AP_DEV_ONLY__-", "retrieval/test3/R0__-"]
    if metadata == "status":
        (run / "run_manifest.json").unlink()
        deck.write_json(run / "status.json", {t: {"status": "PENDING"} for t in [task, *unrelated]})
    else:
        manifest = {"tasks": [task, *unrelated]} if metadata == "tasks" else {
            "tasks": unrelated, "sessions": [{"tasks": [task]}]}
        deck.write_json(run / "run_manifest.json", manifest)
    cases, records, _ = deck.load_runs(["held"], ["test3"])
    assert set(records) == {GOLD} and records[GOLD] == {}  # an unplanned raw file cannot define the balance set
    assert set(cases) == {("test3", "T1")}


def test_loader_requires_run_metadata(offline):
    offline["dev"] = [case("D1")]
    save_run(deck.RESULTS_DIR, "dev", {"dev": {OURS: [(offline["dev"][0], "clarify", rec("D1"))]}})
    (deck.RESULTS_DIR / "dev" / "run_manifest.json").unlink()
    with pytest.raises(ValueError, match="no planned HYU presets"):
        deck.load_runs(["dev"], ["dev"])


@pytest.mark.parametrize("command", ["heldout", "judge-items"])
@pytest.mark.parametrize("missing_split", ["test3", "all"])
def test_planned_preset_with_missing_raw_file_is_dropped_or_rejected(offline, capsys, command, missing_split):
    offline.update(test3=[case("T1", "answer")], test2=[case("U1", "answer")])
    splits = {split: {p: [(c, "answer", rec(c["case_id"])) for c in cases]
                      for p in (AAES, OURS, COND, GOLD)} for split, cases in offline.items()}
    save_run(deck.RESULTS_DIR, "held", splits)
    run = deck.RESULTS_DIR / "held"
    # A status-only planned preset must also balance judge exports that do not request it.
    planned = "B0_BASIC_DENSE_RAG"
    deck.write_json(run / "status.json", {f"hyu/{split}/{planned}__-": {"status": "PENDING"} for split in offline})
    if missing_split != "all":
        deck.write_jsonl(run / "raw" / "hyu" / "test2" / f"{planned}__-.jsonl", [rec("U1")])
        label_path = run / "reply_actions_v2.jsonl"
        deck.write_jsonl(label_path, [*deck.read_rows(label_path), {"preset": planned, "qid": "U1", "label": "answer",
                                                                 "reply_sha": deck.reply_action.reply_sha(rec("U1")["answer"])}])
    args = (["heldout", "--run", "held", "--ours", OURS] if command == "heldout" else
            ["judge-items", "--run", "held", "--presets", OURS])
    if missing_split == "all":
        with pytest.raises(SystemExit) as error:
            deck.main(args)
        assert error.value.code == 2
        message = capsys.readouterr().err
        assert planned in message and "no completed records" in message
        assert not (deck.OUT / "heldout").exists()
    else:
        assert deck.main(args) == 0
        folder = deck.OUT / "heldout"
        report_path = folder / "hypotheses.json" if command == "heldout" else folder / "judge" / "coverage.json"
        report = json.loads(report_path.read_text())
        assert report["cases"] == 1 and planned in report["presets"]
        assert report["dropped_unbalanced"] == [{"split": "test3", "case_id": "T1", "missing_presets": [planned]}]
        if command == "judge-items":
            keys = deck.read_rows(folder / "judge" / "key.jsonl")
            assert {k["case_id"] for k in keys} == {"U1"} and {k["preset"] for k in keys} == {OURS, GOLD}


def test_judge_items_drops_cases_without_matching_v2_labels(offline):
    offline["test3"] = [case("T1", "answer"), case("T2", "answer")]
    splits = {"test3": {p: [(c, "answer", rec(c["case_id"])) for c in offline["test3"]] for p in (OURS, GOLD)}}
    splits["test3"][GOLD][1] = (offline["test3"][1], None, rec("T2"))
    save_run(deck.RESULTS_DIR, "held", splits)
    deck.main(["judge-items", "--run", "held", "--splits", "test3", "--presets", OURS])
    folder = deck.OUT / "heldout" / "judge"
    report = json.loads((folder / "coverage.json").read_text())
    assert report["dropped_unbalanced"] == [{"split": "test3", "case_id": "T2", "missing_presets": [GOLD]}]
    assert {k["case_id"] for k in deck.read_rows(folder / "key.jsonl")} == {"T1"}


@pytest.mark.parametrize("lower,expected", [(0, "non_inferior"), (-0.099, "non_inferior"), (-0.1, "not_demonstrated"),
                                            (-0.2, "not_demonstrated"), (None, "insufficient_cases")])
def test_h2_uses_strict_ci_margin(lower, expected):
    """Identical kept vectors have exact CI [0, 0], satisfying > -0.10 even though equality p=1."""
    rows = {n: {"mcnemar_p": 1, "difference": 0, "ci_low": lower} for n in ("H1", "H2", "H3")}
    deck.decide_hypotheses(rows)
    assert rows["H2"]["decision"] == expected
    assert rows["H2"]["p_holm"] == 1


def test_paired_bootstrap_mcnemar_and_holm():
    result = deck.hypothesis([1] * 10, [0] * 10, "H1")
    assert result["difference"] == result["ci_low"] == result["ci_high"] == 1
    assert result["mcnemar_p"] == 1 / 1024
    rows = {n: dict(result) for n in ("H1", "H2", "H3")}
    deck.decide_hypotheses(rows)
    assert rows["H1"]["decision"] == rows["H3"]["decision"] == "superior"
    assert rows["H1"]["p_holm"] == 3 / 1024
    assert deck.mcnemar([0, 0], [1, 1], True)["mcnemar_p"] == 1
    assert deck.mcnemar([1, 0], [0, 1], True)["mcnemar_p"] == 0.75
    assert deck.mcnemar([1, 0, 0], [0, 1, 1], True)["mcnemar_p"] == 0.875
    assert deck.mcnemar([], [], True)["mcnemar_p"] == 1
    assert deck.hypothesis([1, 1], [1, 1], "H2")["ci_low"] == 0


def export_items(offline):
    offline.update(test3=[case("T1"), case("T2", "answer", session_history=[{"role": "user", "text": "I'm at Seoul."}])],
                   test2=[case("U1", "answer", student_dependent=False)])
    splits = {}
    for split, cases in offline.items():
        splits[split] = {p: [(c, "answer", rec(c["case_id"])) for c in cases] for p in (OURS, GOLD)}
    splits["test3"][OURS][0] = (offline["test3"][0], "clarify", rec("T1"))
    splits["test3"][OURS][1] = (offline["test3"][1], "conditional_answer", rec("T2", answer="Two cases [E1] [E2]."))
    save_run(deck.RESULTS_DIR, "judge", splits)
    deck.main(["judge-items", "--run", "judge", "--presets", f"{OURS},{GOLD}"])
    return deck.OUT / "heldout" / "judge"


def test_judge_fields_blind_keys_and_deterministic_shuffle(offline):
    folder = export_items(offline)
    before = (folder / "items.jsonl").read_bytes()
    items = deck.read_rows(folder / "items.jsonl")
    gold = deck.read_rows(folder / "items_gold.jsonl")
    keys = {k["id"]: k for k in deck.read_rows(folder / "key.jsonl")}
    prompt_fields = set(re.findall(r"`(\w+)`", deck.PROMPT.read_text().split("Fill only")[0]))
    for item in items + gold:
        assert set(item) == {"id", *prompt_fields}
        key = keys[item["id"]]
        original = next(c for c in offline[key["split"]] if c["case_id"] == key["case_id"])
        assert original["question"] == item["question"]
        assert item["gold_evidence"] == "fact one"
        assert item["id"].startswith("G" if key["preset"] == GOLD else "H")
    assert len(items) == 2 and len(gold) == 3
    conditional = next(i for i in items if i["reply_type"] == "conditional_answer")
    assert conditional["cited_sources"] == [{"label": "C1", "text": "fact one"}]
    assert conditional["session_history"] == ["I'm at Seoul."]
    answer = next(i for i in items if i["reply_type"] == "answer")
    assert answer["cited_sources"][0]["label"] == "E2"
    deck.main(["judge-items", "--run", "judge", "--presets", f"{OURS},{GOLD}"])
    assert (folder / "items.jsonl").read_bytes() == before


def judgments(folder, gold=False):
    items = deck.read_rows(folder / ("items_gold.jsonl" if gold else "items.jsonl"))
    rows = [{"id": i["id"], "facts": ["correct", "missing"], "wrong_group": False,
             "cited_sentences": 2, "supported_sentences": 1,
             "conditions_match": True if i["reply_type"] == "conditional_answer" else None,
             "asks_branch_attribute": None, "right_referral": None, "note": ""} for i in items]
    name = "judgments_gold_part" if gold else "judgments_part"
    deck.write_jsonl(folder / f"{name}1.jsonl", rows[:1])
    deck.write_jsonl(folder / f"{name}2.jsonl", rows[1:])
    return rows


def test_content_scores_intervals_hashes_and_gold_separation(offline):
    folder = export_items(offline)
    judgments(folder)
    judgments(folder, gold=True)
    deck.main(["score-content", "--dir", str(folder)])
    report = json.loads((folder / "content.json").read_text())
    overall = next(r for r in report["scores"] if r["slice"] == "all")
    assert overall["facts_covered"] == overall["citation_support"] == 0.5
    assert overall["facts_covered_ci_low"] == overall["facts_covered_ci_high"] == 0.5
    assert overall["wrong_fact_rate"] == overall["wrong_group_rate"] == 0
    assert overall["cases"] == 2 and overall["correct_facts"] == 2 and overall["required_facts"] == 4
    assert next(r for r in report["scores"] if r["slice"] == "student_dependent")["cases"] == 0
    assert report["prompt_sha256"] == hashlib.sha256(deck.PROMPT.read_bytes()).hexdigest()
    assert report["items_sha256"] == hashlib.sha256((folder / "items.jsonl").read_bytes()).hexdigest()
    assert report["judgments_sha256"] == hashlib.sha256((folder / "judgments.jsonl").read_bytes()).hexdigest()
    assert deck.main(["score-content", "--dir", str(folder), "--gold"]) == 0
    gold = json.loads((folder / "content_gold.json").read_text())
    assert {r["preset"] for r in gold["scores"]} == {GOLD}
    assert (folder / "content.json").read_text() == json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    assert len(deck.read_rows(folder / "judgments_gold.jsonl")) == 3
    assert deck.main(["score-content", "--dir", str(folder)]) == 0
    assert json.loads((folder / "content.json").read_text())["scores"] == report["scores"]


@pytest.mark.parametrize("corruption,message", [("missing", "coverage"), ("duplicate", "coverage"), ("extra_id", "coverage"),
                                                ("extra_key", "keys"), ("facts", "align"), ("bad_fact", "align")])
def test_content_rejects_invalid_judgments(offline, corruption, message):
    folder = export_items(offline)
    rows = judgments(folder)
    if corruption == "missing":
        rows.pop()
    elif corruption == "duplicate":
        rows.append(rows[0])
    elif corruption == "extra_id":
        rows.append({**rows[0], "id": "H9999"})
    elif corruption == "extra_key":
        rows[0]["surprise"] = True
    elif corruption == "facts":
        rows[0]["facts"] = ["correct"]
    else:
        rows[0]["facts"] = ["correct", "invented"]
    deck.write_jsonl(folder / "judgments_part1.jsonl", rows)
    deck.write_jsonl(folder / "judgments_part2.jsonl", [])
    with pytest.raises(SystemExit, match=message):
        deck.main(["score-content", "--dir", str(folder)])
    assert not (folder / "content.json").exists()
    assert not (folder / "judgments.jsonl").exists()


def test_content_metrics_use_cases_and_fact_sentence_denominators():
    """1/1 plus 1/3 facts -> 2/4; wrong facts and groups in one of two replies -> 1/2."""
    rows = [{"facts": ["correct"], "wrong_group": False, "cited_sentences": 0, "supported_sentences": 0},
            {"facts": ["correct", "wrong", "missing"], "wrong_group": True, "cited_sentences": 4, "supported_sentences": 3}]
    assert deck.content_stat(rows, "facts_covered") == 0.5
    assert deck.content_stat(rows, "wrong_fact_rate") == deck.content_stat(rows, "wrong_group_rate") == 0.5
    assert deck.content_stat(rows, "citation_support") == 0.75
    interval = deck.content_interval(rows, "citation_support")
    assert interval["citation_support_ci_low"] == interval["citation_support_ci_high"] == 0.75
    assert deck.content_stat(rows[:1], "citation_support") is None
