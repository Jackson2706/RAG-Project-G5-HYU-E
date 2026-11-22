"""Download and load the original SciFact claim-verification release."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app.config import DATA_DIR
from evaluation.beir import write_source_md

FOLDER = DATA_DIR / "benchmarks" / "scifact_original"
URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
EXPECTED_MD5 = "cb7da4d8609e30f2c7483b61aa447f7e"
FILES = {"claims_train.jsonl", "claims_dev.jsonl", "claims_test.jsonl", "corpus.jsonl"}
USER_AGENT = "hyu-compass-benchmarks/1.0"


def _hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, part: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as output:
            shutil.copyfileobj(response, output)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def _extract_archive(archive: Path, folder: Path) -> None:
    """Validate every archive path, then flatten only the four published data files."""
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            path = PurePosixPath(member.name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe archive member: {member.name}")

        selected = {}
        for member in members:
            path = PurePosixPath(member.name)
            name = path.name
            if path.parts == ("data", name) and name in FILES and member.isfile():
                if name in selected:
                    raise ValueError(f"Duplicate archive member: {name}")
                selected[name] = member
        missing = FILES - selected.keys()
        if missing:
            raise ValueError(f"SciFact archive is missing: {', '.join(sorted(missing))}")

        folder.mkdir(parents=True, exist_ok=True)
        for name, member in selected.items():
            part = folder / f"{name}.part"
            with tar.extractfile(member) as source, open(part, "wb") as output:
                shutil.copyfileobj(source, output)
            part.replace(folder / name)


def _is_downloaded() -> bool:
    return all((FOLDER / name).exists() for name in FILES) and (FOLDER / "SOURCE.json").exists()


def download() -> dict:
    """Download, verify, and unpack the four files used from the original SciFact release."""
    if _is_downloaded():
        source = json.loads((FOLDER / "SOURCE.json").read_text(encoding="utf-8"))
        write_source_md(FOLDER, source)
        return source

    FOLDER.mkdir(parents=True, exist_ok=True)
    archive = FOLDER / "data.tar.gz"
    part = FOLDER / "data.tar.gz.part"
    print(f"Downloading {URL} …", flush=True)
    _fetch(URL, part)
    md5 = _hash(part, "md5")
    if md5 != EXPECTED_MD5:
        part.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        raise RuntimeError(f"SciFact archive checksum {md5} does not match the published {EXPECTED_MD5}; nothing was unpacked.")
    sha256 = _hash(part, "sha256")
    part.replace(archive)
    try:
        _extract_archive(archive, FOLDER)
    finally:
        archive.unlink(missing_ok=True)

    source = {
        "dataset": "scifact_original",
        "url": URL,
        "license": "Claims and evidence annotations: CC BY 4.0; abstracts (S2ORC): ODC-By 1.0",
        "md5": md5,
        "md5_verified": True,
        "sha256": sha256,
        "sha256_verified": False,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "splits": ["train", "dev", "test"],
        "contents": "This folder holds the original SciFact claims with labels and rationales, plus its abstract corpus.",
    }
    (FOLDER / "SOURCE.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    write_source_md(FOLDER, source)
    return source


def load_claims(split: str) -> list[dict]:
    """Load claims, using string document IDs and None for unavailable test annotations."""
    if split not in ("train", "dev", "test"):
        raise ValueError("SciFact split must be 'train', 'dev', or 'test'")

    claims = []
    with open(FOLDER / f"claims_{split}.jsonl", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if split == "test":
                claims.append({
                    "id": int(row["id"]),
                    "claim": row["claim"],
                    "cited_doc_ids": None,
                    "evidence": None,
                    "label": None,
                })
                continue
            evidence = {}
            for raw_doc_id, rationales in row["evidence"].items():
                labels = {rationale["label"] for rationale in rationales}
                if len(labels) > 1:
                    raise ValueError(f"Claim {row['id']} document {raw_doc_id} has conflicting evidence labels")
                if labels:
                    evidence[str(raw_doc_id)] = {
                        "label": labels.pop(),
                        "sentences": sorted({int(sentence) for rationale in rationales for sentence in rationale["sentences"]}),
                    }
            labels = {item["label"] for item in evidence.values()}
            label = "NEI" if not labels else labels.pop() if len(labels) == 1 else "MIXED"
            claims.append({
                "id": int(row["id"]),
                "claim": row["claim"],
                "cited_doc_ids": [str(doc_id) for doc_id in row["cited_doc_ids"]],
                "evidence": evidence,
                "label": label,
            })
    return claims


def load_corpus() -> dict[str, dict]:
    """Load abstracts keyed by string document IDs, matching normalized cited IDs."""
    corpus = {}
    with open(FOLDER / "corpus.jsonl", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            corpus[str(row["doc_id"])] = {"title": row["title"], "sentences": list(row["abstract"])}
    return corpus
