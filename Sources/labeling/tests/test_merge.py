"""G4 merge + verification pipeline (labeling/merge.py). Written by Claude Code."""

from __future__ import annotations

import pytest

from labeling.merge import _human, apply_verification, main, merge, read_csv, verification_rows


def label(case_id, **kw):
    base = {"case_id": case_id, "answerability": "answerable", "expected_behavior": "answer", "acceptable_behaviors": ["answer"],
            "branch_attributes": [], "notes": "", "gold_profile": {"campus": "seoul"}, "question": "q?", "stated_profile": {},
            "required_facts": ["f"], "gold_evidence": [{"doc_id": "d", "char_start": 2, "char_end": 6}]}
    return {**base, **kw}


QUOTA = {c: {"slice": s, "origin": "agent_draft"} for c, s in (("a", "unconditional"), ("b", "conditional"), ("c", "negative"))}


def test_merge_takes_final_values_accepted_proposals_and_marks_pending_rows():
    sheet = [
        {"case_id": "a", "final_answerability": "partial", "final_expected_behavior": "abstain",
         "final_acceptable_behaviors": "abstain, answer", "adjudicator": "JD"},
        {"case_id": "b", "proposed_branch_attributes": '["campus"]', "accept_proposal": "Yes", "adjudicator": "human:JD"},
        {"case_id": "c", "proposed_answerability": "unanswerable"},  # proposal not accepted, no adjudicator
    ]
    cases, pending = merge([label("a"), label("b"), label("c")], QUOTA, sheet)
    a, b, c = cases
    assert (a["answerability"], a["expected_behavior"], a["acceptable_behaviors"]) == ("partial", "abstain", ["abstain", "answer"])
    assert a["adjudicated_by"] == "human:JD" and a["origin"] == "agent_draft_human_edited" and a["slice"] == "unconditional"
    assert b["branch_attributes"] == ["campus"] and b["adjudicated_by"] == "human:JD"
    assert c["answerability"] == "answerable" and "adjudicated_by" not in c and pending == ["c"]


def test_merge_stamps_rows_off_the_sheet_only_when_the_human_accepts_them():
    cases, _ = merge([label("a")], QUOTA, [])
    assert "adjudicated_by" not in cases[0]
    cases, _ = merge([label("a")], QUOTA, [], accept_rest="JD")
    assert cases[0]["adjudicated_by"] == "human:JD" and cases[0]["origin"] == "agent_draft"
    with pytest.raises(ValueError, match="without a primary label"):
        merge([label("a")], QUOTA, [{"case_id": "zz"}])


def _cases(n=60):
    slices = ["unconditional"] * 30 + ["conditional"] * 10 + ["temporal"] * 10 + ["negative"] * 5 + ["multi_session"] * 5
    return [label(f"T{i:03d}", slice=s) for i, s in enumerate(slices[:n])]


def test_verification_rows_cover_every_test_case_under_a33():
    docs = {"d": {"text": "0123456789", "campus": "seoul"}}
    sheets = verification_rows(_cases(), docs)
    rows = [r for rs in sheets.values() for r in rs]
    hard = [r for r in rows if r["slice"] != "unconditional"]
    spot = [r for r in rows if r["slice"] == "unconditional"]
    from labeling.freeze import split
    _, test = split(_cases(), 50, 13)
    assert len(hard) == sum(c["slice"] != "unconditional" for c in test)
    assert len(spot) == sum(c["slice"] == "unconditional" for c in test)  # A33: SPOT_SHARE = 1.0
    assert [r["slice"] for r in sheets["1_conditional.csv"]] == ["conditional"] * len(sheets["1_conditional.csv"])
    assert "⟦2345⟧" in rows[0]["gold_evidence"]


def test_apply_verification_fixes_fields_records_initials_and_lists_unverified():
    cases = _cases()
    rows = [r for rs in verification_rows(cases, {"d": {"text": "0123456789"}}).values() for r in rs]
    rows[0].update(verifier="JD", fix_expected_behavior="clarify", evidence_supports_facts="no", fix_note="span misses fact 2")
    out, unverified = apply_verification(cases, rows)
    fixed = next(c for c in out if c["case_id"] == rows[0]["case_id"])
    assert fixed["expected_behavior"] == "clarify" and fixed["acceptable_behaviors"] == ["clarify"]  # "answer" is no longer acceptable
    assert fixed["verified_by"] == "human:JD" and fixed["evidence_supports_facts"] is False and "span misses" in fixed["notes"]
    assert len(unverified) == len(rows) - 1
    dev_id = next(c["case_id"] for c in cases if c["case_id"] not in {r["case_id"] for r in rows} and c["slice"] != "unconditional")
    with pytest.raises(ValueError, match="not selected from the test split"):
        apply_verification(cases, [{"case_id": dev_id, "verifier": "JD"}])


def test_sheet_typos_and_agent_names_raise_instead_of_dropping_the_decision():
    with pytest.raises(ValueError, match="accept_proposal must be yes, no or empty"):
        merge([label("a")], QUOTA, [{"case_id": "a", "accept_proposal": "y", "adjudicator": "JD"}])
    for bad in ("codex", "human:", "1x", "human:claude"):
        with pytest.raises(ValueError, match="not a human"):
            _human(bad)
    rows = [r for rs in verification_rows(_cases(), {"d": {"text": "0123456789"}}).values() for r in rs]
    rows[0].update(verifier="JD", evidence_supports_facts="y")
    with pytest.raises(ValueError, match="evidence_supports_facts"):
        apply_verification(_cases(), rows)


def test_deleted_and_duplicated_sheet_rows():
    rows = [r for rs in verification_rows(_cases(), {"d": {"text": "0123456789"}}).values() for r in rs]
    for r in rows:
        r["verifier"] = "JD"
    _, unverified = apply_verification(_cases(), rows[1:])  # the human deleted the first row
    assert unverified == [rows[0]["case_id"]]
    with pytest.raises(ValueError, match="twice"):
        apply_verification(_cases(), rows + rows[:1])


def test_read_csv_handles_an_excel_bom_padding_and_blank_rows(tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("\ufeffcase_id,verifier\n T001 , JD \n,\nT002\n", encoding="utf-8")
    assert read_csv(path) == [{"case_id": "T001", "verifier": "JD"}, {"case_id": "T002", "verifier": ""}]


def test_verified_ids_are_test_ids_of_the_real_freeze(tmp_path):
    from labeling.freeze import freeze

    cases = [{**c, "adjudicated_by": "human:JD", "verified_by": "human:JD"} for c in _cases()]
    selected = {r["case_id"] for rs in verification_rows(cases, {"d": {"text": "0123456789"}}).values() for r in rs}
    labels = tmp_path / "all.jsonl"
    labels.write_text("".join(__import__("json").dumps(c) + "\n" for c in cases))
    freeze(labels, tmp_path / "out", dev_size=50, seed=13)
    test_ids = {__import__("json").loads(line)["case_id"] for line in (tmp_path / "out" / "test.jsonl").read_text().splitlines()}
    assert selected <= test_ids


def test_sheets_refuses_pending_adjudication_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr("labeling.merge.load_snapshot_rows", lambda _: [{"doc_id": "d", "text": "0123456789"}])
    merged = tmp_path / "merged.jsonl"
    merged.write_text("".join(__import__("json").dumps(c) + "\n" for c in _cases()))
    with pytest.raises(ValueError, match="adjudicate first"):
        main(["sheets", str(merged), "--out", str(tmp_path / "v")])
    merged.write_text("".join(__import__("json").dumps({**c, "adjudicated_by": "human:JD"}) + "\n" for c in _cases()))
    assert main(["sheets", str(merged), "--out", str(tmp_path / "v")]) == 0
    with pytest.raises(FileExistsError):
        main(["sheets", str(merged), "--out", str(tmp_path / "v")])


AGENT = "claude-code:claude-opus-5-5"


def test_agent_adjudicator_exclude_and_origin_a33():
    sheet = [{"case_id": "a", "final_expected_behavior": "abstain", "adjudicator": AGENT},
             {"case_id": "b", "final_answerability": "EXCLUDE", "final_evidence_note": "no span supports fact 1", "adjudicator": AGENT}]
    cases, pending = merge([label("a"), label("b"), label("c")], QUOTA, sheet, accept_rest=AGENT)
    a, b, c = cases
    assert a["adjudicated_by"] == AGENT and a["origin"] == "agent_edited" and a["expected_behavior"] == "abstain"
    assert b["exclude"] == "adjudication: no span supports fact 1" and b["answerability"] == "answerable"
    assert c["adjudicated_by"] == AGENT and pending == []
    with pytest.raises(ValueError, match="not a human"):
        merge([label("a")], QUOTA, [{"case_id": "a", "adjudicator": "claude-code:gpt"}])


def test_violations_are_verified_in_dev_too_and_unresolved_cases_are_excluded():
    cases = _cases()
    from labeling.freeze import split
    dev, _ = split(cases, 50, 13)
    extra = {dev[0]["case_id"]: ["answer_unstated_branch: campus"]}
    rows = [r for rs in verification_rows(cases, {"d": {"text": "0123456789"}}, extra).values() for r in rs]
    flagged = next(r for r in rows if r["case_id"] == dev[0]["case_id"])
    assert flagged["split"] == "dev" and "campus" in flagged["check_violations"]
    rows[0].update(verifier=AGENT, fix_answerability="EXCLUDE", fix_note="evidence is for 2025")
    rows[1].update(verifier=AGENT, fix_expected_behavior="abstain", fix_stale_update="yes")
    out, unverified = apply_verification(cases, rows, extra, exclude_unverified=True)
    by = {c["case_id"]: c for c in out}
    assert by[rows[0]["case_id"]]["exclude"] == "verification: evidence is for 2025"
    assert by[rows[1]["case_id"]]["origin"] == "agent_edited" and by[rows[1]["case_id"]]["verified_by"] == AGENT
    assert by[rows[1]["case_id"]]["stale_update"] is True and "session_history" in rows[1]
    assert len(unverified) == len(rows) - 2 and all("unresolved" in by[c]["exclude"] for c in unverified)


def test_no_self_review_and_no_agent_names_as_initials():
    sonnet = "claude-code:claude-sonnet-5-5"
    with pytest.raises(ValueError, match="primary annotator"):
        merge([label("a", annotator=sonnet)], QUOTA, [], accept_rest=sonnet)
    for bad in ("claude-opus-5-5", "opus-5-5", "gpt5", "sonnetX", "claude-code:", "claude-code:gpt"):
        with pytest.raises(ValueError, match="not a human"):
            _human(bad) if not bad.startswith("claude-code") else merge([label("a")], QUOTA, [], accept_rest=bad)
