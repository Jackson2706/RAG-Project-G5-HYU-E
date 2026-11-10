"""Offline tests for the SciFact-original and ConditionalQA benchmark adapters."""

import io
import json
import logging
import shutil
import tarfile
from pathlib import Path

import pytest

from evaluation import beir, conditionalqa, scifact_original

FIXTURES = Path(__file__).parent / "fixtures" / "benchmarks"


def test_scifact_claims_merge_rationales_and_assign_labels(tmp_path, monkeypatch):
    folder = tmp_path / "scifact_original"
    shutil.copytree(FIXTURES / "scifact_original", folder)
    monkeypatch.setattr(scifact_original, "FOLDER", folder)

    claims = scifact_original.load_claims("train")
    assert [claim["label"] for claim in claims] == ["SUPPORT", "CONTRADICT", "NEI", "MIXED"]
    assert claims[0] == {
        "id": 1,
        "claim": "Alpha is supported.",
        "cited_doc_ids": ["10"],
        "evidence": {"10": {"label": "SUPPORT", "sentences": [1, 2, 3]}},
        "label": "SUPPORT",
    }
    assert scifact_original.load_corpus()["10"] == {
        "title": "Alpha", "sentences": ["Zero.", "One.", "Two.", "Three."]}
    assert scifact_original.load_claims("dev")[0]["label"] == "NEI"
    assert scifact_original.load_claims("test") == [{
        "id": 6,
        "claim": "Zeta is an unlabeled test claim.",
        "cited_doc_ids": None,
        "evidence": None,
        "label": None,
    }]


def test_scifact_rejects_conflicting_labels_for_one_document(tmp_path, monkeypatch):
    monkeypatch.setattr(scifact_original, "FOLDER", tmp_path)
    row = {"id": 9, "claim": "Conflict", "cited_doc_ids": [1], "evidence": {"1": [
        {"label": "SUPPORT", "sentences": [0]}, {"label": "CONTRADICT", "sentences": [1]}]}}
    (tmp_path / "claims_train.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting evidence labels"):
        scifact_original.load_claims("train")


def test_scifact_tar_refuses_parent_path(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        data = b"bad"
        member = tarfile.TarInfo("../evil")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    with pytest.raises(ValueError, match="Unsafe archive member"):
        scifact_original._extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "evil").exists()


def test_scifact_tar_flattens_main_files_and_skips_folds(tmp_path):
    archive = tmp_path / "data.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in sorted(scifact_original.FILES):
            data = f"main:{name}".encode()
            member = tarfile.TarInfo(f"data/{name}")
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        fold_data = b"fold copy"
        fold = tarfile.TarInfo("data/cross_validation/fold_1/claims_train.jsonl")
        fold.size = len(fold_data)
        tar.addfile(fold, io.BytesIO(fold_data))

    folder = tmp_path / "out"
    scifact_original._extract_archive(archive, folder)
    assert (folder / "claims_train.jsonl").read_bytes() == b"main:claims_train.jsonl"
    assert sorted(path.name for path in folder.iterdir()) == sorted(scifact_original.FILES)


def test_scifact_wrong_md5_unpacks_nothing(tmp_path, monkeypatch):
    folder = tmp_path / "scifact_original"
    monkeypatch.setattr(scifact_original, "FOLDER", folder)

    def fake_fetch(url, part):
        part.write_bytes(b"not the published archive")

    monkeypatch.setattr(scifact_original, "_fetch", fake_fetch)
    with pytest.raises(RuntimeError, match="does not match the published"):
        scifact_original.download()
    assert not list(folder.glob("claims_*.jsonl"))
    assert not (folder / "data.tar.gz").exists()
    assert not (folder / "data.tar.gz.part").exists()


def test_conditionalqa_questions_and_html_sections(tmp_path, monkeypatch, caplog):
    folder = tmp_path / "conditionalqa"
    shutil.copytree(FIXTURES / "conditionalqa", folder)
    monkeypatch.setattr(conditionalqa, "FOLDER", folder)

    questions = conditionalqa.load_questions("train")
    assert questions[0]["answers"] == [{"answer": "Yes", "conditions": ["you are a full-time student"]}]
    assert questions[0]["evidences"] == ["<p>Full-time students can apply.</p>"]
    assert questions[1]["answers"] == [{"answer": "The service is open.", "conditions": []}]
    assert questions[2]["not_answerable"] is True

    with caplog.at_level(logging.INFO):
        test_questions = conditionalqa.load_questions("test")
    assert test_questions[0]["not_answerable"] is None
    assert test_questions[0]["answers"] is None
    assert test_questions[0]["evidences"] is None
    assert "test labels are not public" in caplog.text

    docs = conditionalqa.load_documents()
    parsed = conditionalqa.to_parsed_documents(docs)
    assert parsed[0].source_uri == "conditionalqa://https://example.test/benefit"
    assert parsed[0].file_type == "conditionalqa"
    assert [(section.heading, section.text) for section in parsed[0].sections] == [("A", "x"), ("B", "y")]


def test_conditionalqa_rejects_duplicate_document_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(conditionalqa, "FOLDER", tmp_path)
    rows = [
        {"title": "First", "url": "https://example.test/same", "contents": ["<p>One</p>"]},
        {"title": "Second", "url": "https://example.test/same", "contents": ["<p>Two</p>"]},
    ]
    (tmp_path / "documents.json").write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate ConditionalQA document URL"):
        conditionalqa.load_documents()


def test_conditionalqa_download_records_and_enforces_sha256(tmp_path, monkeypatch):
    folder = tmp_path / "conditionalqa"
    monkeypatch.setattr(conditionalqa, "FOLDER", folder)
    fixture_folder = FIXTURES / "conditionalqa"
    payloads = {
        "train.json": (fixture_folder / "train.json").read_bytes(),
        "dev.json": (fixture_folder / "dev.json").read_bytes(),
        "test_no_answer.json": (fixture_folder / "test_no_answer.json").read_bytes(),
        "documents.json": (fixture_folder / "documents.json").read_bytes(),
    }

    def fake_fetch(url, part):
        part.write_bytes(payloads[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(conditionalqa, "_fetch", fake_fetch)
    source = conditionalqa.download()
    assert set(source["files"]) == set(conditionalqa.FILENAMES)
    assert all(not item["verified"] for item in source["files"].values())
    assert (folder / "SOURCE.md").exists()

    (folder / "train.json").unlink()
    payloads["train.json"] = b"changed upstream"
    with pytest.raises(RuntimeError, match="does not match recorded"):
        conditionalqa.download()
    assert not (folder / "train.json").exists() and not (folder / "train.json.part").exists()


def test_write_source_md_includes_licence_and_checksum(tmp_path):
    beir.write_source_md(tmp_path, {
        "dataset": "tiny",
        "url": "https://example.test/tiny.zip",
        "license": "CC BY 4.0",
        "md5": "abc123",
        "md5_verified": True,
        "downloaded_at": "2026-11-10",
        "splits": ["train"],
        "contents": "This folder holds a tiny fixture.",
    })
    text = (tmp_path / "SOURCE.md").read_text(encoding="utf-8")
    assert "Licence: CC BY 4.0" in text
    assert "MD5: `abc123`; verified against a published value: yes" in text


def test_beir_cached_download_backfills_source_md(tmp_path, monkeypatch):
    monkeypatch.setattr(beir, "DATASETS_DIR", tmp_path)
    folder = tmp_path / "scifact"
    folder.mkdir()
    (folder / "corpus.jsonl").write_text("{}\n", encoding="utf-8")
    (folder / "queries.jsonl").write_text("{}\n", encoding="utf-8")
    source = {
        "dataset": "scifact", "url": "https://example.test/scifact.zip",
        "md5": beir.DATASETS["scifact"]["md5"], "md5_verified": True,
        "downloaded_at": "2026-11-10", "license": "CC BY-NC 2.0", "splits": ["train", "test"]}
    (folder / "SOURCE.json").write_text(json.dumps(source), encoding="utf-8")

    assert beir.download("scifact") == source
    assert (folder / "SOURCE.md").exists()


@pytest.mark.parametrize(("dataset", "document_count", "query_count"), [
    ("scifact", 5_183, 300),
    ("nfcorpus", 3_633, 323),
    ("arguana", 8_674, 1_406),
])
def test_real_beir_data_smoke(dataset, document_count, query_count):
    folder = beir.dataset_dir(dataset)
    required = [folder / "corpus.jsonl", folder / "queries.jsonl", folder / "qrels" / "test.tsv", folder / "SOURCE.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip(f"real {dataset} data is absent: missing {', '.join(missing)}")

    corpus, queries, qrels = beir.load(dataset, "test")

    assert len(corpus) == document_count
    assert len(queries) == query_count
    assert len(qrels) == query_count
    assert all(isinstance(doc_id, str) and isinstance(doc["title"], str) and isinstance(doc["text"], str)
               for doc_id, doc in corpus.items())
    assert all(isinstance(query_id, str) and isinstance(query, str) for query_id, query in queries.items())
    assert all(isinstance(query_id, str) and all(isinstance(doc_id, str) and isinstance(score, int)
               for doc_id, score in scores.items()) for query_id, scores in qrels.items())


def test_real_scifact_original_data_smoke():
    required = [scifact_original.FOLDER / name for name in scifact_original.FILES]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip(f"real scifact_original data is absent: missing {', '.join(missing)}")

    train = scifact_original.load_claims("train")
    dev = scifact_original.load_claims("dev")
    test = scifact_original.load_claims("test")
    corpus = scifact_original.load_corpus()

    assert (len(train), len(dev), len(test), len(corpus)) == (809, 300, 300, 5_183)
    assert all(isinstance(claim["id"], int) and isinstance(claim["claim"], str) for claim in train + dev + test)
    assert all(isinstance(claim["cited_doc_ids"], list) and isinstance(claim["evidence"], dict)
               and claim["label"] in {"SUPPORT", "CONTRADICT", "NEI", "MIXED"} for claim in train + dev)
    assert all(claim["cited_doc_ids"] is None and claim["evidence"] is None and claim["label"] is None
               for claim in test)
    assert all(isinstance(doc_id, str) and isinstance(doc["title"], str)
               and isinstance(doc["sentences"], list) and all(isinstance(sentence, str) for sentence in doc["sentences"])
               for doc_id, doc in corpus.items())


def test_real_conditionalqa_data_smoke():
    required = [conditionalqa.FOLDER / name for name in conditionalqa.FILENAMES]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip(f"real conditionalqa data is absent: missing {', '.join(missing)}")

    train = conditionalqa.load_questions("train")
    dev = conditionalqa.load_questions("dev")
    test = conditionalqa.load_questions("test")
    documents = conditionalqa.load_documents()
    parsed = conditionalqa.to_parsed_documents(documents)

    assert (len(train), len(dev), len(test), len(documents)) == (2_338, 285, 804, 652)
    assert all(isinstance(row["id"], str) and isinstance(row["url"], str)
               and isinstance(row["scenario"], str) and isinstance(row["question"], str)
               for row in train + dev + test)
    assert all(isinstance(row["not_answerable"], bool) and isinstance(row["answers"], list)
               and isinstance(row["evidences"], list) for row in train + dev)
    assert all(row["not_answerable"] is None and row["answers"] is None and row["evidences"] is None
               for row in test)
    assert all(isinstance(url, str) and isinstance(doc["title"], str)
               and isinstance(doc["contents"], list) and all(isinstance(element, str) for element in doc["contents"])
               for url, doc in documents.items())
    assert len(parsed) == len(documents)
    assert all(len(document.sections) >= 1 for document in parsed)
