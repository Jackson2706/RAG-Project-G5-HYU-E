"""Test-run guard (AGENTS.md "Evaluation rules", PLAYBOOK Appendix G).

Every run checks that the frozen labels match FROZEN.sha256. A test run also needs --confirm-frozen and a clean
git tree, and is appended once to Report/results/TEST_RUNS.md.
"""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

from labeling.freeze import verify

HEADER = "# Test runs\n\nOne row per run on the frozen test split (AGENTS.md).\n\n| Date | Run id | Git SHA | Configs | Reason |\n|---|---|---|---|---|\n"


class GuardError(RuntimeError):
    pass


def check_run(split: str, confirm_frozen: bool, labels_dir: Path, repo_root: Path, may_be_dirty: tuple[str, ...] = ()) -> None:
    """Raise GuardError unless this run may start. may_be_dirty: repo-relative path prefixes a --resume may leave
    uncommitted (TEST_RUNS.md and the run's own results folder)."""
    if split not in ("dev", "test"):
        raise GuardError(f"unknown split {split!r}")
    if split == "test" and not confirm_frozen:
        raise GuardError("a test run needs --confirm-frozen")
    if not verify(labels_dir):
        raise GuardError(f"labels in {labels_dir} do not match FROZEN.sha256 (or are not frozen yet)")
    if split == "test":
        status = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"], capture_output=True, text=True, check=True)
        dirty = [line[3:] for line in status.stdout.splitlines() if line.strip()]
        if [p for p in dirty if not p.strip('"').startswith(may_be_dirty)] if may_be_dirty else dirty:
            raise GuardError("a test run needs a clean git tree (git status --porcelain is not empty)")


def record_test_run(log: Path, run_id: str, git_sha: str, presets: list[str], reason: str, resume: bool = False) -> None:
    """Append one row to TEST_RUNS.md for every test invocation. A new run id must be new; a resume must name a
    recorded run (and gets its own row with the current SHA)."""
    text = log.read_text(encoding="utf-8") if log.exists() else HEADER
    known = f"| {run_id} |" in text
    if known and not resume:
        raise GuardError(f"test run {run_id!r} is already recorded in {log}")
    if resume and not known:
        raise GuardError(f"--resume of test run {run_id!r}, which is not recorded in {log}")
    clean = lambda v: v.replace("|", "/").replace("\n", " ")  # noqa: E731  (a table cell)
    row = f"| {datetime.date.today().isoformat()} | {clean(run_id)} | {git_sha} | {clean(', '.join(presets))} | {clean(reason)}{' (resume)' if resume else ''} |\n"
    log.write_text(text + row, encoding="utf-8")
