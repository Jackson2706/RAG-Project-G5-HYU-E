"""Document loading: file discovery, media types, source identity and content hashing.

Identity vs. version (Lesson 3):
* ``doc_id`` = uuid5(source_uri) — the logical source; stable across edits.
* ``version_id`` = hash(source bytes, parser contract) — changes when bytes or parsing change.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NAMESPACE = uuid.UUID("5d0f3d1e-6a4b-4f43-9c1e-8a3b2f6c7d10")
MEDIA_TYPES = {
    ".pdf": ("pdf", "application/pdf"),
    ".txt": ("txt", "text/plain"),
    ".md": ("md", "text/markdown"),
    ".markdown": ("md", "text/markdown"),
    ".html": ("html", "text/html"),
    ".htm": ("html", "text/html"),
}
IGNORED_NAMES = {".DS_Store", ".gitkeep", "README.md"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    """SHA-256 of canonical JSON; used for config hashes and deterministic IDs."""
    return sha256_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))


def stable_uuid(label: str) -> str:
    return str(uuid.uuid5(NAMESPACE, label))


@dataclass(frozen=True)
class SourceFile:
    path: Path
    source_uri: str  # local://<path relative to data dir>
    file_type: str
    media_type: str
    size_bytes: int
    sha256: str

    @property
    def doc_id(self) -> str:
        return stable_uuid(self.source_uri)


@dataclass(frozen=True)
class LoadIssue:
    path: str
    error: str


def source_uri_for(path: Path, data_dir: Path) -> str:
    try:
        rel = path.resolve().relative_to(data_dir.resolve())
    except ValueError:
        rel = Path(path.name)
    return f"local://{rel.as_posix()}"


def discover_files(root: Path, data_dir: Path, params: dict[str, Any]) -> tuple[list[SourceFile], list[LoadIssue]]:
    """Return supported files under `root` in sorted order, plus explicit issues for everything rejected."""
    if not root.exists():
        raise FileNotFoundError(f"Corpus path does not exist: {root}")
    allowed = set(params.get("file_types", ["pdf", "txt", "md", "html"]))
    max_bytes = int(params.get("max_file_mb", 20)) * 1024 * 1024
    candidates = [root] if root.is_file() else sorted(root.rglob("*") if params.get("recursive", True) else root.glob("*"))
    files: list[SourceFile] = []
    issues: list[LoadIssue] = []
    for path in candidates:
        if not path.is_file() or path.name in IGNORED_NAMES or path.name.startswith("."):
            continue
        kind = MEDIA_TYPES.get(path.suffix.lower())
        if kind is None:
            issues.append(LoadIssue(str(path), f"unsupported file type '{path.suffix or '(none)'}'"))
            continue
        if kind[0] not in allowed:
            issues.append(LoadIssue(str(path), f"file type '{kind[0]}' excluded by configuration"))
            continue
        size = path.stat().st_size
        if size > max_bytes:
            issues.append(LoadIssue(str(path), f"file is {size / 1e6:.1f} MB, above the {max_bytes // (1024 * 1024)} MB limit"))
            continue
        if size == 0:
            issues.append(LoadIssue(str(path), "file is empty"))
            continue
        files.append(SourceFile(path=path, source_uri=source_uri_for(path, data_dir), file_type=kind[0],
                                media_type=kind[1], size_bytes=size, sha256=sha256_bytes(path.read_bytes())))  # fmt: skip
    return files, issues
