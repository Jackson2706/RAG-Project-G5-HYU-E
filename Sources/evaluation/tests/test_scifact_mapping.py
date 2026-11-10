"""Offline checks for the BEIR-to-original SciFact mapping report."""

import json
import shutil
from pathlib import Path

import pytest

from evaluation import beir, scifact_mapping, scifact_original

FIXTURES = Path(__file__).parent / "fixtures" / "benchmarks"


def _install_fixture(tmp_path, monkeypatch):
    original = tmp_path / "scifact_original"
    shutil.copytree(FIXTURES / "scifact_original", original)
    rows = (original / "claims_train.jsonl").read_text(encoding="utf-8").splitlines()
    (original / "claims_dev.jsonl").write_text("\n".join(rows[:3]) + "\n", encoding="utf-8")
    (original / "SOURCE.json").write_text(json.dumps({"md5": "original-md5"}), encoding="utf-8")

    beir_root = tmp_path / "beir"
    folder = beir_root / "scifact"
    (folder / "qrels").mkdir(parents=True)
    (folder / "corpus.jsonl").write_text(
        "\n".join(json.dumps({"_id": str(doc_id), "title": "", "text": "x"}) for doc_id in (10, 30, 90)) + "\n",
        encoding="utf-8",
    )
    queries = [
        {"_id": "1", "text": "  Alpha   is supported.  "},
        {"_id": "3", "text": "Gamma differs."},
        {"_id": "999", "text": "Missing original claim."},
    ]
    (folder / "queries.jsonl").write_text("\n".join(map(json.dumps, queries)) + "\n", encoding="utf-8")
    (folder / "qrels" / "test.tsv").write_text(
        "query-id\tcorpus-id\tscore\n1\t10\t1\n3\t30\t1\n999\t90\t1\n",
        encoding="utf-8",
    )
    (folder / "SOURCE.json").write_text(json.dumps({"md5": "beir-md5"}), encoding="utf-8")

    monkeypatch.setattr(beir, "DATASETS_DIR", beir_root)
    monkeypatch.setattr(scifact_original, "FOLDER", original)


def test_mapping_report_counts_and_outputs(tmp_path, monkeypatch, capsys):
    _install_fixture(tmp_path, monkeypatch)

    expected = {
        "beir_split": "test",
        "orig_split": "dev",
        "source_checksums": {"beir_md5": "beir-md5", "scifact_original_md5": "original-md5"},
        "n_beir_queries": 3,
        "n_orig_claims": 3,
        "n_id_matched": 2,
        "unmatched_ids": ["999"],
        "n_text_equal": 1,
        "text_mismatch_examples": [{"id": "3", "beir": "Gamma differs.", "orig": "Gamma has no evidence."}],
        "label_counts": {"SUPPORT": 1, "CONTRADICT": 0, "NEI": 1, "MIXED": 0},
        "qrels_vs_evidence": {"equal": 1, "superset": 1, "subset": 0, "other": 0},
        "n_nei_with_qrels": 1,
        "n_qrels_equal_cited": 2,
        "orig_claims_missing_from_beir": 1,
        "orig_claims_missing_from_beir_by_label": {"SUPPORT": 0, "CONTRADICT": 1, "NEI": 0, "MIXED": 0},
    }
    assert scifact_mapping.build_report() == expected

    out = tmp_path / "output"
    assert scifact_mapping.main(["--out", str(out)]) == 0
    assert json.loads((out / "mapping.json").read_text(encoding="utf-8")) == expected
    markdown = (out / "mapping.md").read_text(encoding="utf-8")
    assert "| Qrels vs evidence: superset | 1 |" in markdown
    assert "| `3` | Gamma differs. | Gamma has no evidence. |" in markdown
    assert "| BEIR queries | 3 |" in capsys.readouterr().out


def test_missing_dataset_exits_two_with_download_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(beir, "DATASETS_DIR", tmp_path)

    with pytest.raises(SystemExit) as error:
        scifact_mapping.main([])

    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert scifact_mapping.DOWNLOAD_COMMAND in stderr
    assert "Traceback" not in stderr
