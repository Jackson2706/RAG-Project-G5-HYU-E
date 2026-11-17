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
from datetime import UTC, datetime
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


def _label_items(rows: list[dict]) -> list[dict]:
    """Attach the pre-screened source passages to candidate rows without exposing writer labels."""
    chunks = _chunks()
    docs = {d["doc_id"]: d for d in Database.connect(get_settings()).for_index(INDEX).documents.find({}, {"_id": 0, "doc_id": 1, "title": 1, "source_uri": 1})}
    seeds = {s["seed"]: s for s in load_jsonl(Q / "seeds.jsonl")}
    bundles = {b["bundle"]: b for b in load_jsonl(Q / "bundles.jsonl")}
    items = []
    for r in rows:
        src = seeds.get(r.get("seed")) or bundles.get(r.get("bundle")) or {}
        ids = [p["chunk_id"] for p in src.get("passages", [])] + [p["chunk_id"] for page in src.get("pages", []) for p in page["passages"]]
        ids += [c for c in r.get("evidence_chunk_ids") or [] if c in chunks and c not in ids]
        passages = [{"chunk_id": c, "title": docs.get(chunks[c]["doc_id"], {}).get("title"), "url": docs.get(chunks[c]["doc_id"], {}).get("source_uri"),
                     "section": chunks[c].get("section"), "text": chunks[c]["text"]} for c in ids if c in chunks]  # fmt: skip
        items.append({"case_id": r["case_id"], "question": r["question"], "session_history": r["session_history"], "gold_profile": r["gold_profile"],
                      "passages": passages})  # fmt: skip
    return items


def inputs() -> int:
    """One labelling item per candidate: question, history, persona and the passages the writer had."""
    items = _label_items(load_jsonl(Q / "candidates.jsonl"))
    rng = random.Random(3)
    rng.shuffle(items)
    (Q / "label_input.jsonl").write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print("items", len(items))
    return 0


def buffer_inputs(tag: str = "") -> int:
    """Create a separate blind input so adding the dependent buffer cannot invalidate the original annotation hashes."""
    rows = [{**r, "case_id": r["qid"], "kind": "student_dependent"}
            for r in load_jsonl(Q / "drafts" / f"dependent_buffer{tag}_out.jsonl") if not r.get("skip")]  # fmt: skip
    if len(rows) != len({r["case_id"] for r in rows}):
        raise SystemExit("dependent buffer case ids must be unique")
    (Q / f"candidates_buffer{tag}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    items = _label_items(rows)
    random.Random(4).shuffle(items)
    (Q / f"label_input_buffer{tag}.jsonl").write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print("buffer items", len(items))
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


def agree(a_name: str = "labels_A.jsonl", b_name: str = "labels_B.jsonl", tag: str = "") -> int:
    """Compare two independent files; optional names keep provisional local labels separate from final labels."""
    a = {r["case_id"]: r for r in load_jsonl(Q / a_name)}
    b = {r["case_id"]: r for r in load_jsonl(Q / b_name)}
    ids = sorted(set(a) & set(b))
    if not ids:
        raise SystemExit("the label files have no case ids in common")
    ta, tb = [a[i]["expected_behavior"] for i in ids], [b[i]["expected_behavior"] for i in ids]
    da, db = [dependent(a[i]) for i in ids], [dependent(b[i]) for i in ids]
    attrs = [set(a[i].get("branch_attributes") or []) == set(b[i].get("branch_attributes") or []) for i in ids]
    info = {"files": {"A": a_name, "B": b_name}, "annotators": {"A": sorted({r.get("annotator", "missing") for r in a.values()}),
                                                                     "B": sorted({r.get("annotator", "missing") for r in b.values()})},
            "origins": {"A": sorted({r.get("origin", "missing") for r in a.values()}), "B": sorted({r.get("origin", "missing") for r in b.values()})},
            "cases": len(ids), "missing_in_A": sorted(set(b) - set(a)), "missing_in_B": sorted(set(a) - set(b)),
            "reply_type_agreement": round(sum(x == y for x, y in zip(ta, tb, strict=True)) / len(ids), 3), "reply_type_kappa": kappa(ta, tb),
            "student_dependent_agreement": round(sum(x == y for x, y in zip(da, db, strict=True)) / len(ids), 3), "student_dependent_kappa": kappa(da, db),
            "branch_attributes_exact_agreement": round(sum(attrs) / len(ids), 3),
            "confusion_A_by_B": {f"{x}|{y}": n for (x, y), n in sorted(Counter(zip(ta, tb)).items())}}  # fmt: skip
    dis = [{"case_id": i, "A": a[i], "B": b[i]} for i in ids if a[i]["expected_behavior"] != b[i]["expected_behavior"]
           or set(a[i].get("branch_attributes") or []) != set(b[i].get("branch_attributes") or [])]  # fmt: skip
    suffix = f"_{tag}" if tag else ""
    (Q / f"agreement{suffix}.json").write_text(json.dumps(info, indent=1) + "\n")
    (Q / f"disagreements{suffix}.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dis), encoding="utf-8")
    print(json.dumps(info, indent=1), "\ndisagreements", len(dis))
    return 0


def assemble(a_name: str, b_name: str, adjudicated_name: str, tag: str = "") -> int:
    """Combine exact decision consensus with third-model resolutions, preserving which path produced each row."""
    a = {r["case_id"]: r for r in load_jsonl(Q / a_name)}
    b = {r["case_id"]: r for r in load_jsonl(Q / b_name)}
    adjudicated = {r["case_id"]: r for r in load_jsonl(Q / adjudicated_name)}
    if set(a) != set(b):
        raise SystemExit("the independent label files must cover the same case ids")
    disagreements = {i for i in a if a[i]["expected_behavior"] != b[i]["expected_behavior"]
                     or set(a[i].get("branch_attributes") or []) != set(b[i].get("branch_attributes") or [])}  # fmt: skip
    if set(adjudicated) != disagreements:
        raise SystemExit(f"adjudication coverage mismatch: missing={sorted(disagreements - set(adjudicated))}, extra={sorted(set(adjudicated) - disagreements)}")
    rows = []
    for case_id in sorted(a):
        if case_id in adjudicated:
            resolved = adjudicated[case_id]
            rows.append({**resolved, "annotator": a[case_id].get("annotator", ""), "origin": "agent_edited",
                         "adjudicated_by": resolved.get("adjudicated_by") or resolved.get("annotator", ""),
                         "decision_provenance": "third_model_adjudication"})  # fmt: skip
        else:
            rows.append({**a[case_id], "consensus_with": b[case_id].get("annotator", ""),
                         "decision_provenance": "independent_consensus"})  # fmt: skip
    suffix = f"_{tag}" if tag else ""
    output = Q / f"adjudicated{suffix}.jsonl"
    output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    info = {"files": {"A": a_name, "B": b_name, "adjudicated_disagreements": adjudicated_name},
            "rows": len(rows), "consensus": len(rows) - len(adjudicated), "third_model_adjudication": len(adjudicated),
            "expected_behavior": Counter(r["expected_behavior"] for r in rows),
            "student_dependent": sum(dependent(r) for r in rows), "excluded": sum(bool(r.get("exclude")) for r in rows),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "created_at": datetime.now(UTC).isoformat()}  # fmt: skip
    (Q / f"adjudicated{suffix}.meta.json").write_text(json.dumps(info, indent=1, default=dict) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=1, default=dict))
    return 0


def _spans(ref, chunks: dict, to_snapshot: dict) -> list[dict]:
    """A chunk id -> its snapshot span; a {doc_id, char_start, char_end} span passes through."""
    if isinstance(ref, dict):
        return [{"doc_id": ref["doc_id"], "char_start": int(ref["char_start"]), "char_end": int(ref["char_end"])}]
    c = chunks.get(ref)
    if not c or not c.get("source_spans"):
        return []
    return [{"doc_id": to_snapshot.get(c["doc_id"], c["doc_id"]), "char_start": c["source_spans"][0][0], "char_end": c["source_spans"][-1][1]}]


def _resolved_cases() -> list[dict]:
    """Convert the three independently labelled pools to the evaluator case schema."""
    chunks = _chunks()
    to_snapshot = hyu_suite.snapshot_doc_ids(SNAPSHOT)
    pools = (("candidates.jsonl", "adjudicated.jsonl"), ("candidates_buffer.jsonl", "adjudicated_buffer.jsonl"),
             ("candidates_buffer2.jsonl", "adjudicated_buffer2.jsonl"))
    cand = {r["case_id"]: r for candidate_file, _ in pools for r in load_jsonl(Q / candidate_file)}
    cases = []
    for candidate_file, label_file in pools:
        for lab in load_jsonl(Q / label_file):
            if lab.get("exclude"):
                continue
            c = cand[lab["case_id"]]
            gold = [{**s, "applies_to_gold_profile": True} for ref in lab.get("gold_evidence") or [] for s in _spans(ref, chunks, to_snapshot)]
            bad = [{**s, "why": "other group"} for ref in lab.get("inapplicable_evidence") or [] for s in _spans(ref, chunks, to_snapshot)]
            acceptable = list(dict.fromkeys([lab["expected_behavior"], *(lab.get("acceptable_behaviors") or [])]))
            is_dependent = dependent(lab)
            national = "visa" in (lab.get("branch_attributes") or []) or bool(re.search(
                r"\b(?:visa|immigration|alien registration|national health insurance|NHI)\b", c["question"], re.I))
            cases.append({"case_id": c["case_id"], "case_version": "1.0", "question": c["question"],
                          "session_history": [{"role": "user", "text": t.get("content", t.get("text", "")) if isinstance(t, dict) else t}
                                              for t in c["session_history"]], "gold_profile": c["gold_profile"],
                          "stated_profile": lab.get("stated_profile") or {}, "branch_attributes": lab.get("branch_attributes") or [],
                          "expected_behavior": lab["expected_behavior"], "acceptable_behaviors": acceptable, "required_facts": lab["required_facts"],
                          "gold_evidence": gold, "inapplicable_evidence": bad, "outdated_evidence": [], "answerability": lab.get("answerability", "answerable"),
                          "slice": "conditional" if is_dependent else "unconditional", "student_dependent": is_dependent,
                          "form": c["form"], "snapshot_id": SNAPSHOT, "condition_scope": "national" if national else "campus",
                          "reference_answer": "; ".join(lab["required_facts"]), "notes": lab.get("notes", ""),
                          "annotator": lab.get("annotator", ""), "origin": lab.get("origin", "agent_draft"),
                          "adjudicated_by": lab.get("adjudicated_by", ""), "decision_provenance": lab.get("decision_provenance", "")})  # fmt: skip
            if not cases[-1]["adjudicated_by"]:
                del cases[-1]["adjudicated_by"]
    return cases


def _stratified_take(rows: list[dict], count: int, fields: tuple[str, ...], seed: int) -> tuple[list[dict], list[dict]]:
    """Take an exact, proportional, deterministic sample. Hand check: 3+2 rows, take 3 -> exactly 3."""
    if count > len(rows):
        raise SystemExit(f"need {count} rows, only {len(rows)} available")
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(tuple(row[field] for field in fields), []).append(row)
    quotas = {key: len(group) * count / len(rows) for key, group in groups.items()}
    sizes = {key: int(quota) for key, quota in quotas.items()}
    for key in sorted(groups, key=lambda k: (-(quotas[k] - sizes[k]), k))[:count - sum(sizes.values())]:
        sizes[key] += 1
    rng = random.Random(seed)
    selected, reserve = [], []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda row: row["case_id"])
        rng.shuffle(group)
        selected += group[:sizes[key]]
        reserve += group[sizes[key]:]
    return selected, reserve


def prepare() -> int:
    """Select exactly 140 dependent + 60 plain cases and prepare two blind verifier batches before freezing."""
    cases = _resolved_cases()
    dependent_cases = [c for c in cases if c["student_dependent"]]
    plain_cases = [c for c in cases if not c["student_dependent"]]
    selected_dep, reserve_dep = _stratified_take(dependent_cases, 140, ("expected_behavior", "form"), 2026)
    selected_plain, reserve_plain = _stratified_take(plain_cases, 60, ("expected_behavior", "form"), 2027)
    selected = selected_dep + selected_plain
    dev2, test3 = _stratified_take(selected, 60, ("student_dependent", "expected_behavior", "form"), 2028)
    dev2 = [{**c, "split": "dev2"} for c in dev2]
    test3 = [{**c, "split": "test3"} for c in test3]
    for name, rows in (("prepared_dev2", dev2), ("prepared_test3", test3), ("selection_reserve", reserve_dep + reserve_plain)):
        (Q / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: r["case_id"])), encoding="utf-8")
    blind = {r["case_id"]: r for name in ("label_input.jsonl", "label_input_buffer.jsonl", "label_input_buffer2.jsonl") for r in load_jsonl(Q / name)}
    verification = [{"case": row, "passages": blind[row["case_id"]]["passages"]} for row in sorted(test3, key=lambda r: r["case_id"])]
    for number, batch in enumerate((verification[::2], verification[1::2]), 1):
        (Q / f"verification_input_{number}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in batch), encoding="utf-8")
    info = {"pool": len(cases), "pool_slice": Counter(c["slice"] for c in cases), "selected": len(selected),
            "selected_slice": Counter("student_dependent" if c["student_dependent"] else "plain" for c in selected), "dev2": len(dev2), "test3": len(test3),
            "dev2_slice": Counter("student_dependent" if c["student_dependent"] else "plain" for c in dev2),
            "test3_slice": Counter("student_dependent" if c["student_dependent"] else "plain" for c in test3),
            "reserve": len(reserve_dep) + len(reserve_plain), "verification_batches": [len(verification[::2]), len(verification[1::2])]}  # fmt: skip
    (Q / "selection.json").write_text(json.dumps(info, indent=1, default=dict) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=1, default=dict))
    return 0


def replacement_inputs() -> int:
    """Replace sole-verifier exclusions from the deterministic reserve without changing the 140/60 balance."""
    excluded = [row for name in ("verified_test3.jsonl", "verified_dev2_flags.jsonl") for row in load_jsonl(Q / name)
                if row.get("verification_action") == "exclude"]  # fmt: skip
    counts = Counter(row["split"] for row in excluded)
    reserve = [row for row in load_jsonl(Q / "selection_reserve.jsonl")
               if not row["student_dependent"] and row["expected_behavior"] == "answer" and row["answerability"] == "answerable"]  # fmt: skip
    selected, _ = _stratified_take(reserve, len(excluded), ("form",), 2029)
    dev, test = _stratified_take(selected, counts["dev2"], ("form",), 2030)
    replacements = [{**row, "split": split} for split, rows in (("dev2", dev), ("test3", test)) for row in rows]
    blind = {r["case_id"]: r for name in ("label_input.jsonl", "label_input_buffer.jsonl", "label_input_buffer2.jsonl") for r in load_jsonl(Q / name)}
    payload = [{"case": row, "passages": blind[row["case_id"]]["passages"]} for row in sorted(replacements, key=lambda r: r["case_id"])]
    (Q / "replacement_verification_input.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in payload), encoding="utf-8")
    info = {"excluded": len(excluded), "excluded_by_split": counts, "replacements": len(replacements),
            "replacement_by_split": Counter(r["split"] for r in replacements), "case_ids": [r["case_id"] for r in replacements]}  # fmt: skip
    (Q / "replacement_selection.json").write_text(json.dumps(info, indent=1, default=dict) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=1, default=dict))
    return 0


def finalize() -> int:
    """Verified prepared labels -> dev2/test3 files and SHA-256 freeze."""
    dev2 = load_jsonl(Q / "prepared_dev2.jsonl")
    verified_path = Q / "verified_test3.jsonl"
    dev_fixes_path = Q / "verified_dev2_flags.jsonl"
    if not verified_path.exists() or not dev_fixes_path.exists():
        raise SystemExit("single-verifier test3 and flagged-dev2 outputs are required before freeze")
    dev_fixes = {row["case_id"]: row for row in load_jsonl(dev_fixes_path)}
    flagged = {row["case_id"] for row in load_jsonl(Q / "violations_dev2.jsonl")}
    if set(dev_fixes) != flagged:
        raise SystemExit(f"dev2 verifier coverage mismatch: missing={sorted(flagged - set(dev_fixes))}, extra={sorted(set(dev_fixes) - flagged)}")
    excluded = [row for row in dev_fixes.values() if row.get("verification_action") == "exclude"]
    dev2 = [dev_fixes.get(row["case_id"], row) for row in dev2
            if dev_fixes.get(row["case_id"], row).get("verification_action") != "exclude"]  # fmt: skip
    verified_test3 = load_jsonl(verified_path)
    excluded += [row for row in verified_test3 if row.get("verification_action") == "exclude"]
    test3 = [row for row in verified_test3 if row.get("verification_action") != "exclude"]
    replacement_path = Q / "verified_replacements.jsonl"
    if not replacement_path.exists():
        raise SystemExit("sole-verifier replacement output is required before freeze")
    replacements = load_jsonl(replacement_path)
    if any(row.get("verification_action") == "exclude" for row in replacements):
        raise SystemExit("a replacement was excluded; select and verify another reserve case")
    dev2 += [row for row in replacements if row["split"] == "dev2"]
    test3 += [row for row in replacements if row["split"] == "test3"]
    if len(dev2) != 60 or len(test3) != 140:
        raise SystemExit(f"freeze requires dev2=60 and verified test3=140; got {len(dev2)} and {len(test3)}")
    for name, rows in (("dev2", dev2), ("test3", test3)):
        (LABELS / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: r["case_id"])), encoding="utf-8")
    (LABELS / "excluded_dev2_test3.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(excluded, key=lambda r: r["case_id"])), encoding="utf-8")
    lines = [f"{hashlib.sha256((LABELS / f'{n}.jsonl').read_bytes()).hexdigest()}  {n}.jsonl" for n in ("dev2", "test3")]
    (LABELS / "FROZEN_dev2_test3.sha256").write_text("\n".join(lines) + "\n")
    info = {n: {"cases": len(r), "slice": Counter(c["slice"] for c in r),
                "student_dependent": sum(dependent(c) for c in r), "plain": sum(not dependent(c) for c in r),
                "expected": Counter(c["expected_behavior"] for c in r)} for n, r in (("dev2", dev2), ("test3", test3))}  # fmt: skip
    info["excluded"] = {"cases": len(excluded), "path": "excluded_dev2_test3.jsonl"}
    (Q / "split.json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps(info, indent=1), "\n", "\n".join(lines))
    return 0


if __name__ == "__main__":
    assert kappa(["x", "y", "x"], ["x", "y", "x"]) == 1.0 and dependent({"expected_behavior": "answer", "branch_attributes": ["campus"]})
    command = sys.argv[1]
    if command in ("agree", "assemble"):
        raise SystemExit({"agree": agree, "assemble": assemble}[command](*sys.argv[2:]))
    if command == "buffer-inputs":
        raise SystemExit(buffer_inputs(*sys.argv[2:]))
    raise SystemExit({"merge": merge_candidates, "inputs": inputs, "prepare": prepare,
                      "replacement-inputs": replacement_inputs, "finalize": finalize}[command]())  # fmt: skip
