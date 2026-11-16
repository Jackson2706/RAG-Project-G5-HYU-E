"""Deck v4 Task 3: the new question set (dev-2 / test-3), from writer drafts to frozen labels. No system ever runs here.

Run from Sources/:
  python scripts/deck_v4_questions.py merge      # drafts/*_out_*.jsonl -> questions/candidates.jsonl (+ overlap check)
  python scripts/deck_v4_questions.py inputs     # -> questions/label_input.jsonl (question, history, persona, passages; no draft type)
  python scripts/deck_v4_questions.py agree      # labels_A.jsonl + labels_B.jsonl -> agreement.json + disagreements.jsonl
  python scripts/deck_v4_questions.py finalize   # adjudicated.jsonl -> Sources/data/HYU/labels/dev2.jsonl, test3.jsonl + FROZEN_dev2_test3.sha256

Overlap with dev, test-1 and test-2 is checked by text similarity (BGE cosine of the questions) and by source passage
(evidence chunks overlapping any existing case's evidence spans). Existing labels are read through hyu_suite.load_cases;
only scores and new-question ids are written, never an existing question.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import DATA_DIR, REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402

Q = REPORT_DIR / "slides" / "deck_v4" / "questions"
LABELS = DATA_DIR / "HYU" / "labels"
INDEX, SNAPSHOT = "hyu_20261110_97dc1269_r5", "hyu-20261110-97dc1269"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SIM_DUP = 0.92  # cosine at or above this to an existing or earlier new question = duplicate


def _chunks() -> dict[str, dict]:
    db = Database.connect(get_settings()).for_index(INDEX)
    return {c["chunk_id"]: c for c in db.chunks.find({}, {"_id": 0, "embedding": 0})}


def _history(h) -> list[str]:
    return [t if isinstance(t, str) else t.get("content") or t.get("text") or "" for t in h or []]


def merge_candidates() -> int:
    from sentence_transformers import SentenceTransformer

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from deck_v4_seeds import used_chunks

    rows = []
    for path in sorted((Q / "drafts").glob("*_out_*.jsonl")):
        for r in load_jsonl(path):
            if not r.get("skip") and r.get("question"):
                rows.append({**r, "session_history": _history(r.get("session_history")), "draft_file": path.name})
    chunks = _chunks()
    used = used_chunks(list(chunks.values()))
    settings = get_settings()
    model = SentenceTransformer(settings.embedding_model, revision=settings.embedding_revision, device="cpu")
    existing = [c["question"] for split in ("dev", "test", "test2") for c in hyu_suite.load_cases(split)]
    ev = model.encode(existing, normalize_embeddings=True)
    nv = model.encode([r["question"] for r in rows], normalize_embeddings=True)
    kept, report = [], Counter()
    for i, r in enumerate(rows):
        best_existing = float((ev @ nv[i]).max())
        best_new = max((float(nv[j] @ nv[i]) for j in kept), default=0.0)
        bad_chunks = [c for c in r.get("evidence_chunk_ids") or [] if c not in chunks]
        reason = ("similar_to_existing" if best_existing >= SIM_DUP else "duplicate_new" if best_new >= SIM_DUP
                  else "evidence_overlaps_existing" if set(r.get("evidence_chunk_ids") or []) & used
                  else "email" if EMAIL.search(r["question"] + " ".join(r["session_history"])) else None)  # fmt: skip
        r["max_sim_existing"], r["max_sim_new"], r["unknown_chunk_ids"] = round(best_existing, 3), round(best_new, 3), bad_chunks
        if reason:
            report[reason] += 1
            r["dropped"] = reason
        else:
            kept.append(i)
    out = [rows[i] for i in kept]
    for n, r in enumerate(out, 1):
        r["case_id"] = f"N{n:03d}"
        r["kind"] = "control" if r["form"] == "control" else "student_dependent"
    (Q / "candidates.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    info = {"drafted": len(rows), "kept": len(out), "dropped": dict(report), "kind": Counter(r["kind"] for r in out),
            "form": Counter(r["form"] for r in out), "dup_threshold": SIM_DUP,
            "max_similarity_to_existing": round(max(r["max_sim_existing"] for r in rows), 3),
            "evidence_chunk_ids_not_in_index": sum(bool(r["unknown_chunk_ids"]) for r in rows)}  # fmt: skip
    (Q / "overlap_check.json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps(info, indent=1))
    return 0


def inputs() -> int:
    """One labelling item per candidate: question, history, persona and the passages the writer had (pages of its seed or bundle)."""
    chunks = _chunks()
    docs = {d["doc_id"]: d for d in Database.connect(get_settings()).for_index(INDEX).documents.find({}, {"_id": 0, "doc_id": 1, "title": 1, "source_uri": 1})}
    seeds = {s["seed"]: s for s in load_jsonl(Q / "seeds.jsonl")}
    bundles = {b["bundle"]: b for b in load_jsonl(Q / "bundles.jsonl")}
    items = []
    for r in load_jsonl(Q / "candidates.jsonl"):
        src = seeds.get(r.get("seed")) or bundles.get(r.get("bundle")) or {}
        ids = [p["chunk_id"] for p in src.get("passages", [])] + [p["chunk_id"] for page in src.get("pages", []) for p in page["passages"]]
        ids += [c for c in r.get("evidence_chunk_ids") or [] if c in chunks and c not in ids]
        passages = [{"chunk_id": c, "title": docs.get(chunks[c]["doc_id"], {}).get("title"), "url": docs.get(chunks[c]["doc_id"], {}).get("source_uri"),
                     "section": chunks[c].get("section"), "text": chunks[c]["text"]} for c in ids if c in chunks]  # fmt: skip
        items.append({"case_id": r["case_id"], "question": r["question"], "session_history": r["session_history"], "gold_profile": r["gold_profile"],
                      "passages": passages})  # fmt: skip
    rng = random.Random(3)
    rng.shuffle(items)
    (Q / "label_input.jsonl").write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print("items", len(items))
    return 0


TYPES = ("answer", "conditional_answer", "clarify", "abstain")


def kappa(a: list, b: list) -> float:
    """Cohen's kappa. kappa(["x","y"], ["x","y"]) -> 1.0"""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n / n
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def dependent(label: dict) -> bool:
    return label["expected_behavior"] in ("conditional_answer", "clarify") or bool(label.get("branch_attributes"))


def agree() -> int:
    a = {r["case_id"]: r for r in load_jsonl(Q / "labels_A.jsonl")}
    b = {r["case_id"]: r for r in load_jsonl(Q / "labels_B.jsonl")}
    ids = sorted(set(a) & set(b))
    ta, tb = [a[i]["expected_behavior"] for i in ids], [b[i]["expected_behavior"] for i in ids]
    da, db = [dependent(a[i]) for i in ids], [dependent(b[i]) for i in ids]
    attrs = [set(a[i].get("branch_attributes") or []) == set(b[i].get("branch_attributes") or []) for i in ids]
    info = {"cases": len(ids), "missing_in_A": sorted(set(b) - set(a)), "missing_in_B": sorted(set(a) - set(b)),
            "reply_type_agreement": round(sum(x == y for x, y in zip(ta, tb, strict=True)) / len(ids), 3), "reply_type_kappa": kappa(ta, tb),
            "student_dependent_agreement": round(sum(x == y for x, y in zip(da, db, strict=True)) / len(ids), 3), "student_dependent_kappa": kappa(da, db),
            "branch_attributes_exact_agreement": round(sum(attrs) / len(ids), 3),
            "confusion_A_by_B": {f"{x}|{y}": n for (x, y), n in sorted(Counter(zip(ta, tb)).items())}}  # fmt: skip
    dis = [{"case_id": i, "A": a[i], "B": b[i]} for i in ids if a[i]["expected_behavior"] != b[i]["expected_behavior"]
           or set(a[i].get("branch_attributes") or []) != set(b[i].get("branch_attributes") or [])]  # fmt: skip
    (Q / "agreement.json").write_text(json.dumps(info, indent=1) + "\n")
    (Q / "disagreements.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dis), encoding="utf-8")
    print(json.dumps(info, indent=1), "\ndisagreements", len(dis))
    return 0


def _spans(ref, chunks: dict, to_snapshot: dict) -> list[dict]:
    """A chunk id -> its snapshot span; a {doc_id, char_start, char_end} span passes through."""
    if isinstance(ref, dict):
        return [{"doc_id": ref["doc_id"], "char_start": int(ref["char_start"]), "char_end": int(ref["char_end"])}]
    c = chunks.get(ref)
    if not c or not c.get("source_spans"):
        return []
    return [{"doc_id": to_snapshot.get(c["doc_id"], c["doc_id"]), "char_start": c["source_spans"][0][0], "char_end": c["source_spans"][-1][1]}]


def finalize() -> int:
    """Adjudicated labels -> dev2 (60) and test3 (140), stratified by kind and expected type; frozen with SHA-256."""
    chunks = _chunks()
    to_snapshot = hyu_suite.snapshot_doc_ids(SNAPSHOT)
    cand = {r["case_id"]: r for r in load_jsonl(Q / "candidates.jsonl")}
    cases = []
    for lab in load_jsonl(Q / "adjudicated.jsonl"):
        if lab.get("exclude"):
            continue
        c = cand[lab["case_id"]]
        gold = [{**s, "applies_to_gold_profile": True} for ref in lab.get("gold_evidence") or [] for s in _spans(ref, chunks, to_snapshot)]
        bad = [{**s, "why": "other group"} for ref in lab.get("inapplicable_evidence") or [] for s in _spans(ref, chunks, to_snapshot)]
        acceptable = list(dict.fromkeys([lab["expected_behavior"], *(lab.get("acceptable_behaviors") or [])]))
        cases.append({"case_id": c["case_id"], "case_version": "1.0", "question": c["question"],
                      "session_history": [{"role": "user", "text": t} for t in c["session_history"]], "gold_profile": c["gold_profile"],
                      "stated_profile": lab.get("stated_profile") or {}, "branch_attributes": lab.get("branch_attributes") or [],
                      "expected_behavior": lab["expected_behavior"], "acceptable_behaviors": acceptable, "required_facts": lab["required_facts"],
                      "gold_evidence": gold, "inapplicable_evidence": bad, "outdated_evidence": [], "answerability": lab.get("answerability", "answerable"),
                      "slice": "student_dependent" if dependent(lab) else "plain", "form": c["form"], "snapshot_id": SNAPSHOT,
                      "annotator": "claude-code:opus-5.5 + claude-code:sonnet-5.5 (adjudicated)", "origin": "agent_draft",
                      "adjudicated_by": lab.get("adjudicated_by", "")})  # fmt: skip
    rng = random.Random(2026)
    dev2, test3 = [], []
    strata: dict[tuple, list] = {}
    for c in cases:
        strata.setdefault((c["slice"], c["expected_behavior"]), []).append(c)
    share = 60 / len(cases)
    for key in sorted(strata):
        group = sorted(strata[key], key=lambda c: c["case_id"])
        rng.shuffle(group)
        k = round(len(group) * share)
        dev2 += [{**c, "split": "dev2"} for c in group[:k]]
        test3 += [{**c, "split": "test3"} for c in group[k:]]
    for name, rows in (("dev2", dev2), ("test3", test3)):
        (LABELS / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: r["case_id"])), encoding="utf-8")
    lines = [f"{hashlib.sha256((LABELS / f'{n}.jsonl').read_bytes()).hexdigest()}  {n}.jsonl" for n in ("dev2", "test3")]
    (LABELS / "FROZEN_dev2_test3.sha256").write_text("\n".join(lines) + "\n")
    info = {n: {"cases": len(r), "slice": Counter(c["slice"] for c in r), "expected": Counter(c["expected_behavior"] for c in r)} for n, r in (("dev2", dev2), ("test3", test3))}
    (Q / "split.json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps(info, indent=1), "\n", "\n".join(lines))
    return 0


if __name__ == "__main__":
    assert kappa(["x", "y", "x"], ["x", "y", "x"]) == 1.0 and dependent({"expected_behavior": "answer", "branch_attributes": ["campus"]})
    raise SystemExit({"merge": merge_candidates, "inputs": inputs, "agree": agree, "finalize": finalize}[sys.argv[1]]())
