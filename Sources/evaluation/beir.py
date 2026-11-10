"""BEIR datasets: download (only when asked), checksum verification, loading, and conversion.

Files stay exactly as published (corpus.jsonl, queries.jsonl, qrels/<split>.tsv) in
evaluation/datasets/<name>/, which is not committed to Git. Original document and query IDs are kept.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.rag.schemas import ParsedDocument, Section

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
BASE_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"

# MD5 checksums as published in the BEIR README (github.com/beir-cellar/beir).
DATASETS = {
    "scifact": {"md5": "5f7d1de60b170fc8027bb7898e2efca1", "splits": ["train", "test"], "license": "CC BY-NC 2.0"},
    "nfcorpus": {"md5": "a89dba18a62ef92f7d323ec890a0d38d", "splits": ["train", "dev", "test"], "license": "CC BY-SA 4.0"},
    "arguana": {"md5": "8ad3e3c2a5867cdced806d6503f29b99", "splits": ["test"], "license": "CC BY-SA 4.0"},
}


def dataset_dir(name: str) -> Path:
    return DATASETS_DIR / name


def is_downloaded(name: str) -> bool:
    folder = dataset_dir(name)
    return (folder / "corpus.jsonl").exists() and (folder / "queries.jsonl").exists() and (folder / "SOURCE.json").exists()


def download(name: str) -> dict:
    """Download and unpack one dataset unless it is cached. Refuses an archive with the wrong checksum."""
    if name not in DATASETS:
        raise ValueError(f"Unknown BEIR dataset '{name}'. Known: {', '.join(DATASETS)}")
    folder = dataset_dir(name)
    if is_downloaded(name):
        return json.loads((folder / "SOURCE.json").read_text())
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    url, archive = f"{BASE_URL}/{name}.zip", DATASETS_DIR / f"{name}.zip"
    print(f"Downloading {url} …", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, open(archive, "wb") as out:
        shutil.copyfileobj(response, out)
    md5 = hashlib.md5(archive.read_bytes()).hexdigest()
    if md5 != DATASETS[name]["md5"]:
        archive.unlink()
        raise RuntimeError(f"{name}.zip checksum {md5} does not match the published {DATASETS[name]['md5']}; nothing was unpacked.")
    with zipfile.ZipFile(archive) as z:
        z.extractall(DATASETS_DIR)  # the archive contains a folder named <name>/
    archive.unlink()
    source = {"dataset": name, "url": url, "md5": md5, "md5_verified": True, "downloaded_at": datetime.now(UTC).isoformat(),
              "license": DATASETS[name]["license"], "splits": DATASETS[name]["splits"]}  # fmt: skip
    (folder / "SOURCE.json").write_text(json.dumps(source, indent=2))
    return source


def load(name: str, split: str = "test") -> tuple[dict[str, dict], dict[str, str], dict[str, dict[str, int]]]:
    """(corpus {doc_id: {"title", "text"}}, queries {query_id: text} for the split's judged queries, qrels {query_id: {doc_id: relevance}})."""
    folder = dataset_dir(name)
    if not is_downloaded(name):
        raise FileNotFoundError(f"BEIR '{name}' is not downloaded. Run: python -m evaluation.runner --download {name}")
    qrels_file = folder / "qrels" / f"{split}.tsv"
    if not qrels_file.exists():
        raise FileNotFoundError(f"BEIR '{name}' has no '{split}' split (available: {', '.join(DATASETS[name]['splits'])})")
    corpus = {}
    with open(folder / "corpus.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            corpus[str(d["_id"])] = {"title": d.get("title") or "", "text": d.get("text") or ""}
    qrels: dict[str, dict[str, int]] = {}
    with open(qrels_file, encoding="utf-8") as f:
        next(f)  # header: query-id corpus-id score
        for line in f:
            qid, did, score = line.rstrip("\n").split("\t")
            qrels.setdefault(qid, {})[did] = int(score)
    queries = {}
    with open(folder / "queries.jsonl", encoding="utf-8") as f:
        for line in f:
            q = json.loads(line)
            if str(q["_id"]) in qrels:
                queries[str(q["_id"])] = q["text"]
    return corpus, queries, qrels


def source_uri(dataset: str, doc_id: str) -> str:
    """The URI under which a BEIR document is indexed; its doc_id (make_doc_id) is derived from it."""
    return f"beir://{dataset}/{doc_id}"


def beir_id(source_uri_value: str) -> str:
    return source_uri_value.split("/", 3)[3]


def to_parsed_documents(dataset: str, corpus: dict[str, dict]) -> list[ParsedDocument]:
    """BEIR records → ParsedDocument (what the app's parser produces for a file).

    The title is the first line of the text (BEIR's usual "title + text" input), and there is one
    section: BEIR documents have no headings. So every chunker sees the same text.
    """
    return [ParsedDocument(path=Path(f"beir/{dataset}/{doc_id}"), source_uri=source_uri(dataset, doc_id), file_type="beir",
                           title=d["title"] or doc_id,
                           sections=[Section(heading=None, text=f"{d['title']}\n\n{d['text']}" if d["title"] else d["text"])])
            for doc_id, d in corpus.items()]  # fmt: skip


def documents_from_chunks(ranked_doc_ids: list[str], depth: int) -> list[str]:
    """Chunk ranking → document ranking: each document at the rank of its FIRST (best) chunk, duplicates dropped."""
    seen, ranking = set(), []
    for doc_id in ranked_doc_ids:
        if doc_id not in seen:
            seen.add(doc_id)
            ranking.append(doc_id)
            if len(ranking) == depth:
                break
    return ranking
