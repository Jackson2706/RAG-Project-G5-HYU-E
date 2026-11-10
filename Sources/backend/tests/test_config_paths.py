"""Focused checks for the two-folder repository layout."""

from app.config import DATA_DIR, PROJECT_ROOT, REPORT_DIR, REPO_ROOT, RESULTS_DIR, resolve_stored_path


def test_default_directories():
    assert REPORT_DIR == REPO_ROOT / "Report"
    assert DATA_DIR == PROJECT_ROOT / "data" == REPO_ROOT / "Sources" / "data"
    assert RESULTS_DIR == REPORT_DIR / "results"


def test_stored_data_path_uses_data_directory():
    assert resolve_stored_path("data/HYU/x") == DATA_DIR / "HYU/x"


def test_stored_results_path_uses_results_directory():
    assert resolve_stored_path("results/r/a") == RESULTS_DIR / "r/a"


def test_other_stored_relative_path_uses_repository_root():
    assert resolve_stored_path("evaluation/x") == REPO_ROOT / "evaluation/x"


def test_stored_absolute_path_is_unchanged(tmp_path):
    path = tmp_path / "annotations.jsonl"
    assert resolve_stored_path(path) == path
