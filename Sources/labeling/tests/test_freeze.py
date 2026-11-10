"""Split and freeze (Gate G4). Written by Claude Code before the implementation (T12).

Contract of labeling/freeze.py:
    split(cases, dev_size, seed=13) -> (dev, test)
        stratified by (slice, gold_profile.campus); deterministic for a seed; exact dev_size;
        each stratum's dev count is within 1 of its proportional share.
    freeze(labels_path, out_dir, dev_size, seed=13) -> dict
        writes dev.jsonl, test.jsonl (read-only, 0o444) and FROZEN.sha256; refuses to re-freeze;
        refuses unless every case is human-adjudicated (adjudicated_by starts with "human:").
    verify(out_dir) -> bool     True only if both files still match FROZEN.sha256.
"""

import json
import stat
from collections import Counter

import pytest

from labeling import freeze

SLICES = {"unconditional": 35, "conditional": 25, "temporal": 10, "negative": 20, "multi_session": 10}


def make_cases(n_per_slice=SLICES):
    cases, k = [], 0
    for slice_name, count in n_per_slice.items():
        for i in range(count):
            campus = "erica" if i % 3 == 0 else "seoul"
            cases.append({"case_id": f"hyu-{k:04d}", "slice": slice_name, "gold_profile": {"campus": campus},
                          "adjudicated_by": "human:JK", "question": f"q{k}"})  # fmt: skip
            k += 1
    return cases


def stratum(case):
    return case["slice"], case["gold_profile"]["campus"]


def test_split_is_exact_disjoint_and_deterministic():
    cases = make_cases()
    dev, test = freeze.split(cases, dev_size=28, seed=13)
    assert len(dev) == 28 and len(test) == 72
    ids_dev, ids_test = {c["case_id"] for c in dev}, {c["case_id"] for c in test}
    assert not ids_dev & ids_test and ids_dev | ids_test == {c["case_id"] for c in cases}
    again_dev, _ = freeze.split(list(reversed(cases)), dev_size=28, seed=13)  # input order must not matter
    assert {c["case_id"] for c in again_dev} == ids_dev
    other_dev, _ = freeze.split(cases, dev_size=28, seed=14)
    assert {c["case_id"] for c in other_dev} != ids_dev


def test_split_is_stratified_by_slice_and_campus():
    cases = make_cases()
    dev, _ = freeze.split(cases, dev_size=28, seed=13)
    total, in_dev = Counter(map(stratum, cases)), Counter(map(stratum, dev))
    for key, n in total.items():
        assert abs(in_dev[key] - n * 28 / len(cases)) <= 1, key


def test_freeze_writes_hashes_read_only_test_and_refuses_twice(tmp_path):
    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(c) for c in make_cases()) + "\n")
    out = tmp_path / "frozen"
    report = freeze.freeze(labels, out, dev_size=28)
    assert (out / "dev.jsonl").exists() and (out / "test.jsonl").exists()
    assert not (out / "test.jsonl").stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    sha_lines = (out / "FROZEN.sha256").read_text().split("\n")
    assert any(line.endswith("test.jsonl") for line in sha_lines) and any(line.endswith("dev.jsonl") for line in sha_lines)
    assert report["dev"] == 28 and report["test"] == 72 and report["seed"] == 13
    assert all(json.loads(line)["split"] == "test" for line in (out / "test.jsonl").read_text().splitlines())
    assert freeze.verify(out)
    with pytest.raises(FileExistsError):
        freeze.freeze(labels, out, dev_size=28)


def test_verify_detects_a_changed_file(tmp_path):
    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(c) for c in make_cases()) + "\n")
    out = tmp_path / "frozen"
    freeze.freeze(labels, out, dev_size=28)
    dev = out / "dev.jsonl"
    dev.write_text(dev.read_text().replace("q", "Q", 1))
    assert not freeze.verify(out)


def test_freeze_refuses_cases_without_human_adjudication(tmp_path):
    cases = make_cases()
    cases[5]["adjudicated_by"] = "codex:gpt"
    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(c) for c in cases) + "\n")
    with pytest.raises(ValueError, match=cases[5]["case_id"]):
        freeze.freeze(labels, tmp_path / "frozen", dev_size=28)
    assert not (tmp_path / "frozen" / "FROZEN.sha256").exists()
