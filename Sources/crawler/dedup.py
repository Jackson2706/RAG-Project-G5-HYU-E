"""Exact and near-duplicate handling for extracted documents."""

from __future__ import annotations

import hashlib
import re
import uuid


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _winner_key(record: dict[str, object]) -> tuple[str, str]:
    return (str(record.get("post_date") or "9999-99-99"), str(record["doc_id"]))


def merge_exact(records: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for record in records:
        groups.setdefault(normalized_text(str(record["text"])), []).append(record)
    merged = []
    for group in groups.values():
        winner = min(group, key=_winner_key)
        aliases = list(winner.get("aliases", []))
        for record in group:
            if record is winner:
                continue
            aliases.append({
                "doc_id": record["doc_id"],
                "source_uri": record["source_uri"],
                "site": record["site"],
                "campus": record["campus"],
            })
            aliases.extend(record.get("aliases", []))
        winner["aliases"] = sorted(aliases, key=lambda value: str(value["doc_id"]))
        merged.append(winner)
    return merged


def _shingles(text: str) -> set[str]:
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    if not words:
        return set()
    if len(words) < 5:
        return {" ".join(words)}
    return {" ".join(words[index:index + 5]) for index in range(len(words) - 4)}


def minhash(text: str, hashes: int = 128) -> tuple[int, ...]:
    shingles = _shingles(text)
    if not shingles:
        return tuple(0 for _ in range(hashes))
    values = []
    for index in range(hashes):
        salt = index.to_bytes(2, "big")
        values.append(min(
            int.from_bytes(hashlib.blake2b(salt + shingle.encode("utf-8"), digest_size=8).digest(), "big")
            for shingle in shingles
        ))
    return tuple(values)


def estimated_jaccard(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a == b for a, b in zip(left, right)) / len(left)


def _version_markers(text: str) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    years = frozenset(re.findall(r"\b20\d{2}\b", text))
    semesters = frozenset(
        value.lower()
        for value in re.findall(r"\b20\d{2}-[12]\b|\b(?:Spring|Fall|Summer|Winter)\b", text, re.IGNORECASE)
    )
    amounts = frozenset(
        match.group(0).lower().replace(" ", "")
        for match in re.finditer(
            r"\bKRW\s*\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s*(?:won|KRW|%)|\b\d+,000\b",
            text,
            re.IGNORECASE,
        )
    )
    return years, semesters, amounts


def has_version_difference(left: str, right: str) -> bool:
    return any(a != b for a, b in zip(_version_markers(left), _version_markers(right)))


def _record_date(record: dict[str, object]) -> str:
    return str(record.get("post_date") or record.get("effective_date") or "0000-00-00")


def deduplicate(records: list[dict[str, object]]) -> list[dict[str, object]]:
    records = merge_exact(records)
    signatures = [minhash(str(record["text"])) for record in records]
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    # shortcut: O(n²) pairwise MinHash is fine below about 3,000 documents; add LSH if the corpus grows.
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if estimated_jaccard(signatures[left], signatures[right]) < 0.9:
                continue
            left_text, right_text = str(records[left]["text"]), str(records[right]["text"])
            if has_version_difference(left_text, right_text):
                union(left, right)
            else:
                for source, other in ((left, right), (right, left)):
                    warnings = list(records[source].get("warnings", []))
                    warning = f"near_duplicate:{records[other]['doc_id']}"
                    if warning not in warnings:
                        warnings.append(warning)
                    records[source]["warnings"] = sorted(warnings)

    families: dict[int, list[int]] = {}
    for index in range(len(records)):
        root = find(index)
        if root != index or any(find(other) == root and other != index for other in range(len(records))):
            families.setdefault(root, []).append(index)
    for members in families.values():
        smallest_id = min(str(records[index]["doc_id"]) for index in members)
        family_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "family:" + smallest_id))
        newest = max(members, key=lambda index: (_record_date(records[index]), str(records[index]["doc_id"])))
        for index in members:
            records[index]["version_family_id"] = family_id
            records[index]["superseded_by"] = None if index == newest else records[newest]["doc_id"]

    return sorted(records, key=lambda record: str(record["doc_id"]))

