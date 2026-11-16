"""Deck v4 Task 3, step 1: seed passages for the new question set (dev-2 / test-3). Offline, read-only, no LLM.

Run from Sources/:  python scripts/deck_v4_seeds.py
-> Report/slides/deck_v4/questions/seeds.jsonl (pairs of similar passages whose tags differ by campus, degree level,
   academic status, visa or TOPIK; plus single passages that apply to everyone, for the plain controls)
   and Report/slides/deck_v4/questions/seed_exclusions.json (counts only).

Passages that overlap the gold or inapplicable evidence of any dev, test-1 or test-2 case are never seeds. The labels
are read through hyu_suite.load_cases (the runner's reader); only chunk ids leave it, never a question or a label.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from itertools import zip_longest as _zip_longest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402

from app.config import REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v4" / "questions"
INDEX = "hyu_20261110_97dc1269_r5"
SPLIT_ATTRS = ("degree_level", "academic_status", "visa", "topik_level", "student_type", "year", "english_track")
N_PAIRS, N_CONTROLS, SIM = 190, 80, 0.78
PRIORITY = ("campus", "topik_level", "visa", "degree_level", "student_type", "year", "english_track", "academic_status")


def used_chunks(chunks: list[dict]) -> set[str]:
    """Chunk ids whose spans overlap evidence of any existing labelled case (dev, test, test2)."""
    to_snapshot = hyu_suite.snapshot_doc_ids("hyu-20261110-97dc1269")
    spans: dict[str, list[tuple[int, int]]] = {}
    for split in ("dev", "test", "test2"):
        for case in hyu_suite.load_cases(split):
            for e in [*case.get("gold_evidence", []), *(case.get("inapplicable_evidence") or []), *(case.get("outdated_evidence") or [])]:
                spans.setdefault(e["doc_id"], []).append((e["char_start"], e["char_end"]))
    used = set()
    for c in chunks:
        for a, b in spans.get(to_snapshot.get(c["doc_id"], c["doc_id"]), []):
            if any(s < b and a < e for s, e in c.get("source_spans") or []):
                used.add(c["chunk_id"])
    return used


def tags(c: dict) -> dict:
    a = c.get("applicability") or {}
    return {"campus": a.get("campus") or [], "constraints": a.get("constraints") or {}, "any_of": a.get("any_of") or [], "status": c.get("condition_status")}


def differs(a: dict, b: dict) -> list[str]:
    """Attributes on which two passages' tags apply to different students."""
    out = ["campus"] if set(a["campus"]) != set(b["campus"]) and len(a["campus"]) == 1 and len(b["campus"]) == 1 else []
    for attr in SPLIT_ATTRS:
        va, vb = a["constraints"].get(attr), b["constraints"].get(attr)
        if va and vb and not set(va) & set(vb):
            out.append(attr)
    return out


def main() -> int:
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    db = Database.connect(settings).for_index(INDEX)
    docs = {d["doc_id"]: d for d in db.documents.find({}, {"_id": 0, "doc_id": 1, "title": 1, "source_uri": 1})}
    chunks = [c for c in db.chunks.find({}, {"_id": 0, "embedding": 0}) if len(c.get("text") or "") > 200]
    used = used_chunks(chunks)
    free = [c for c in chunks if c["chunk_id"] not in used and "<" not in c["text"][:50]]
    model = SentenceTransformer(settings.embedding_model, revision=settings.embedding_revision, device="cpu")
    vec = model.encode([c["text"] for c in free], normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    sims = vec @ vec.T
    pairs = []
    for i in range(len(free)):
        for j in np.where(sims[i, i + 1:] >= SIM)[0] + i + 1:
            d = differs(tags(free[i]), tags(free[j]))
            if d and free[i]["condition_status"] == free[j]["condition_status"] == "conditioned":
                pairs.append((float(sims[i, j]), i, int(j), d))
    rng = random.Random(2026)
    rng.shuffle(pairs)
    buckets: dict[str, list] = {}  # round-robin over the attribute that splits a pair, so academic status does not crowd out the rest
    for p in sorted(pairs, key=lambda p: -p[0]):
        buckets.setdefault(next(a for a in PRIORITY if a in p[3]), []).append(p)
    order = [p for group in _zip_longest(*(buckets.get(a, []) for a in PRIORITY)) for p in group if p]
    seen_docs, seen_chunks, seeds = Counter(), Counter(), []
    for sim, i, j, d in order:  # at most 2 seeds per document pair, each passage used at most twice
        key = tuple(sorted((free[i]["doc_id"], free[j]["doc_id"])))
        if seen_docs[key] >= 2 or seen_chunks[i] >= 2 or seen_chunks[j] >= 2 or len(seeds) >= N_PAIRS:
            continue
        seen_docs[key] += 1
        seen_chunks[i] += 1
        seen_chunks[j] += 1
        seeds.append({"seed": f"P{len(seeds) + 1:03d}", "kind": "student_dependent", "differs_on": d, "similarity": round(sim, 3),
                      "passages": [_passage(free[k], docs) for k in (i, j)]})  # fmt: skip
    plain = [c for c in free if c["condition_status"] == "unconditioned" or (set(tags(c)["campus"]) == {"seoul", "erica"} and not tags(c)["constraints"])]
    rng.shuffle(plain)
    for c in plain[:N_CONTROLS]:
        seeds.append({"seed": f"C{len([s for s in seeds if s['kind'] == 'control']) + 1:03d}", "kind": "control", "differs_on": [], "passages": [_passage(c, docs)]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "seeds.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in seeds), encoding="utf-8")
    info = {"chunks_over_200_chars": len(chunks), "excluded_overlap_existing_cases": len(used), "free": len(free), "pairs_found": len(pairs),
            "student_dependent_seeds": sum(s["kind"] == "student_dependent" for s in seeds), "control_seeds": sum(s["kind"] == "control" for s in seeds),
            "differs_on": Counter(a for s in seeds for a in s["differs_on"]), "similarity_threshold": SIM}  # fmt: skip
    (OUT / "seed_exclusions.json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps(info, indent=1))
    return 0


def _passage(c: dict, docs: dict) -> dict:
    d = docs.get(c["doc_id"], {})
    return {"chunk_id": c["chunk_id"], "title": d.get("title"), "url": d.get("source_uri"), "section": c.get("section"), "tags": tags(c), "text": c["text"]}


def bundles() -> int:
    """Second seed type (the pair seeds were mostly noise): topic bundles. Each ERICA page with the most similar Seoul page
    (mean passage embedding), plus every page whose own passages are tagged for different groups. Writers may write
    several questions per bundle. Same exclusions as the pairs. -> questions/bundles.jsonl
    Run: python scripts/deck_v4_seeds.py bundles"""
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    db = Database.connect(settings).for_index(INDEX)
    docs = {d["doc_id"]: d for d in db.documents.find({}, {"_id": 0, "doc_id": 1, "title": 1, "source_uri": 1})}
    chunks = [c for c in db.chunks.find({}, {"_id": 0, "embedding": 0}) if len(c.get("text") or "") > 200 and "<" not in c["text"][:50]]
    used = used_chunks(chunks)
    by: dict[str, list[dict]] = {}
    for c in chunks:
        if c["chunk_id"] not in used:
            by.setdefault(c["doc_id"], []).append(c)
    model = SentenceTransformer(settings.embedding_model, revision=settings.embedding_revision, device="cpu")
    ids = sorted(by)
    vec = np.array([model.encode([c["text"] for c in by[d]], normalize_embeddings=True).mean(0) for d in ids])
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    campus = {d: set(tags(by[d][0])["campus"]) for d in ids}
    erica = [i for i, d in enumerate(ids) if campus[ids[i]] == {"erica"}]
    seoul = [i for i, d in enumerate(ids) if campus[ids[i]] == {"seoul"}]
    out = []
    for i in erica:
        j = max(seoul, key=lambda k: float(vec[i] @ vec[k]))
        out.append({"bundle": f"B{len(out) + 1:03d}", "kind": "campus_pair", "similarity": round(float(vec[i] @ vec[j]), 3),
                    "pages": [_page(ids[i], by, docs), _page(ids[j], by, docs)]})  # fmt: skip
    for d in ids:
        cond = [c for c in by[d] if c["condition_status"] == "conditioned"]
        if any(differs(tags(a), tags(b)) for n, a in enumerate(cond) for b in cond[n + 1:]):
            out.append({"bundle": f"B{len(out) + 1:03d}", "kind": "within_page", "pages": [_page(d, by, docs)]})
    (OUT / "bundles.jsonl").write_text("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in out), encoding="utf-8")
    print(len(out), "bundles:", Counter(b["kind"] for b in out))
    return 0


def _page(doc_id: str, by: dict, docs: dict) -> dict:
    d = docs.get(doc_id, {})
    passages, size = [], 0
    for c in sorted(by[doc_id], key=lambda c: int(c.get("chunk_index", 0))):
        if size > 6000:
            break
        passages.append({"chunk_id": c["chunk_id"], "section": c.get("section"), "tags": tags(c), "text": c["text"]})
        size += len(c["text"])
    return {"title": d.get("title"), "url": d.get("source_uri"), "passages": passages}


if __name__ == "__main__":
    assert differs({"campus": ["seoul"], "constraints": {}}, {"campus": ["erica"], "constraints": {}}) == ["campus"]
    raise SystemExit(bundles() if sys.argv[1:] == ["bundles"] else main())
