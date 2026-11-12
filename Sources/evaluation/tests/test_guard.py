"""Test-run guard (AGENTS.md Evaluation rules; PLAYBOOK Appendix G). Written by Claude Code before the code."""

import subprocess

import pytest

from evaluation.guard import GuardError, check_run, record_test_run
from labeling.freeze import freeze


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A clean git repo with frozen labels (2 dev, 2 test)."""
    labels = tmp_path / "labels"
    labels.mkdir()
    rows = [{"case_id": f"C{i}", "slice": "unconditional", "gold_profile": {"campus": "seoul"}, "adjudicated_by": "human:XX"} for i in range(4)]
    (tmp_path / "all.jsonl").write_text("".join(__import__("json").dumps(r) + "\n" for r in rows))
    freeze(tmp_path / "all.jsonl", labels, dev_size=2)
    git(tmp_path, "init", "-q")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return tmp_path


def test_dev_runs_need_only_intact_labels(repo):
    (repo / "scratch.txt").write_text("dirty tree is fine for dev")
    check_run("dev", confirm_frozen=False, labels_dir=repo / "labels", repo_root=repo)


def test_test_run_refuses_without_confirm_frozen(repo):
    with pytest.raises(GuardError, match="--confirm-frozen"):
        check_run("test", confirm_frozen=False, labels_dir=repo / "labels", repo_root=repo)


def test_test_run_refuses_a_dirty_tree(repo):
    (repo / "scratch.txt").write_text("x")
    with pytest.raises(GuardError, match="clean git tree"):
        check_run("test", confirm_frozen=True, labels_dir=repo / "labels", repo_root=repo)


def test_any_run_refuses_changed_labels(repo):
    test_file = repo / "labels" / "test.jsonl"
    test_file.chmod(0o644)
    test_file.write_text(test_file.read_text() + "\n")
    with pytest.raises(GuardError, match="FROZEN.sha256"):
        check_run("dev", confirm_frozen=False, labels_dir=repo / "labels", repo_root=repo)


def test_clean_confirmed_test_run_passes_and_is_recorded_once(repo):
    check_run("test", confirm_frozen=True, labels_dir=repo / "labels", repo_root=repo)
    log = repo / "TEST_RUNS.md"
    record_test_run(log, run_id="test-final", git_sha="abc123", presets=["A0_AAES", "B0"], reason="G6")
    text = log.read_text()
    assert text.startswith("# Test runs") and "| test-final | abc123 | A0_AAES, B0 | G6 |" in text
    with pytest.raises(GuardError, match="already recorded"):
        record_test_run(log, run_id="test-final", git_sha="abc123", presets=["A0_AAES"], reason="again")
