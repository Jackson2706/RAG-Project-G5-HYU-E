"""Tests for repository path configuration."""

import importlib

import app.config as config


def test_repository_paths_have_defaults_and_environment_overrides(monkeypatch, tmp_path):
    names = ("HYU_DATA_DIR", "HYU_RESULTS_DIR", "HYU_REPORT_DIR")
    try:
        with monkeypatch.context() as env:
            for name in names:
                env.delenv(name, raising=False)
            importlib.reload(config)
            assert config.PROJECT_ROOT == config.BACKEND_DIR.parent
            assert config.REPO_ROOT == config.PROJECT_ROOT.parent
            assert config.REPORT_DIR == config.REPO_ROOT / "Report"
            assert config.DATA_DIR == config.PROJECT_ROOT / "data"
            assert config.RESULTS_DIR == config.REPORT_DIR / "results"
            assert config.Settings().data_dir == config.DATA_DIR

            report_dir = tmp_path / "custom_report"
            env.setenv("HYU_REPORT_DIR", str(report_dir))
            importlib.reload(config)
            assert config.REPORT_DIR == report_dir
            assert config.DATA_DIR == config.PROJECT_ROOT / "data"  # data stays in Sources/
            assert config.RESULTS_DIR == report_dir / "results"

            overrides = {name: tmp_path / name.lower() for name in names}
            for name, path in overrides.items():
                env.setenv(name, str(path))
            importlib.reload(config)
            assert config.DATA_DIR == overrides["HYU_DATA_DIR"]
            assert config.RESULTS_DIR == overrides["HYU_RESULTS_DIR"]
            assert config.REPORT_DIR == overrides["HYU_REPORT_DIR"]
            assert config.Settings().data_dir == overrides["HYU_DATA_DIR"]
    finally:
        importlib.reload(config)
