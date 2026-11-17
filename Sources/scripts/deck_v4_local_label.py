"""Provisional local annotation for deck-v4 dev2/test3 when independent cloud labelers are unavailable.

Run from Sources/ with one model at a time on the 16 GB Mac:

  HYU_LLM_CACHE=../.run/llm_cache conda run -n RAG python scripts/deck_v4_local_label.py \
    --model qwen3.5:4b --annotator local:qwen3.5:4b --output ../Report/slides/deck_v4/questions/labels_local_qwen.jsonl --resume

This reads only the blind input and writes one model's labels. A second, different model must use a different output.
The results remain provisional until fresh adjudication, verification, and the human spot check described in
Report/slides/deck_v4/questions/METHODOLOGY.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import REPO_ROOT, get_settings  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.applicability import VOCABULARY  # noqa: E402

INPUT = REPO_ROOT / "Report" / "slides" / "deck_v4" / "questions" / "label_input.jsonl"
RAW_DIR = REPO_ROOT / ".run" / "deck4-label"
PROMPT_VERSION = "dev2-test3-local-v1"
TYPES = {"answer", "conditional_answer", "clarify", "abstain"}
ANSWERABILITY = {"answerable", "partial", "unanswerable", "external_only", "korean_only", "unanswerable_unreadable"}
SYSTEM = """You label HYU Compass questions from official English passages. Work independently and use only the supplied case.

Choose expected_behavior in this order:
1. No official English evidence for every required fact: abstain. partial means at least one fact is supported; partial still abstains. Old dates, fees, quotas, or schedules do not answer a current-term (2026-2) question. Stable rules from the newest page may answer.
2. Otherwise answer unless the evidence gives different answer values for an unstated allowed student attribute.
3. Two or fewer distinct answer values: conditional_answer. More than two, or different procedures: clarify one attribute.
Only these branch attributes are allowed: campus, degree_level, year, student_type, visa, topik_level, english_track, academic_status, korean_standard. A branch must be demonstrated by different supplied evidence. GPA, nationality, attendance, dates, and program-specific criteria are caveats, not branch attributes.
If campus is unknown and campus-scoped evidence differs, campus is a branch; a missing campus branch may be a referral. Immigration and national health-insurance rules are national even when hosted by one campus. If the student's campus is stated and only the other campus applies, abstain and refer to their campus office.
stated_profile contains only facts stated in the question or earlier turns, using the allowed vocabulary. Do not copy the hidden gold_profile into stated_profile. Applicant is stated only when the question is about applying or says so.
Use only supplied chunk ids in gold_evidence and inapplicable_evidence. Gold supports the answer, including every stated conditional branch. Inapplicable evidence is relevant but for another group. required_facts has 1-4 short facts; an abstention names what is missing and the next office or official route. acceptable_behaviors includes expected_behavior.

Return one JSON object only with: case_id, expected_behavior, acceptable_behaviors, branch_attributes, stated_profile, required_facts, gold_evidence, inapplicable_evidence, answerability, exclude, notes. exclude is true only for an unusable question. notes is at most 20 words."""


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw or "", re.S)
    try:
        value = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def normalize(value: dict | None, case: dict | None = None) -> tuple[dict | None, list[str]]:
    """Repair only common enum-placement mistakes; never invent substantive label content."""
    if value is None:
        return None, []
    changes = []
    misplaced = value.get("expected_behavior") if value.get("expected_behavior") in ANSWERABILITY else None
    if misplaced:
        value["answerability"] = misplaced
        value["expected_behavior"] = "answer" if misplaced == "answerable" else "abstain"
        changes.append("answerability_was_expected_behavior")
    elif isinstance(value.get("answerability"), bool):
        value["answerability"] = "answerable" if value["answerability"] else "unanswerable"
        changes.append("boolean_answerability")
    elif value.get("answerability") in TYPES:
        value["answerability"] = "answerable" if value.get("expected_behavior") != "abstain" else "unanswerable"
        changes.append("behavior_was_answerability")
    acceptable = value.get("acceptable_behaviors")
    if not isinstance(acceptable, list) or any(x not in TYPES for x in acceptable):
        value["acceptable_behaviors"] = [value.get("expected_behavior")] if value.get("expected_behavior") in TYPES else []
        changes.append("invalid_acceptable_behaviors")
    elif value.get("expected_behavior") in TYPES and value["expected_behavior"] not in acceptable:
        value["acceptable_behaviors"] = [value["expected_behavior"], *acceptable]
        changes.append("expected_added_to_acceptable")
    stated = value.get("stated_profile")
    if isinstance(stated, dict):
        kept = {a: v for a, v in stated.items() if a in VOCABULARY and v in VOCABULARY[a]}
        if kept != stated:
            value["stated_profile"] = kept
            changes.append("invalid_stated_values_removed")
    if case:
        allowed = {p["chunk_id"] for p in case["passages"]}
        for field in ("gold_evidence", "inapplicable_evidence"):
            evidence = value.get(field)
            if isinstance(evidence, list):
                kept = [chunk_id for chunk_id in evidence if isinstance(chunk_id, str) and chunk_id in allowed]
                if kept != evidence:
                    value[field] = kept
                    changes.append(f"invalid_{field}_removed")
    return value, changes


def validate(value: dict | None, case: dict) -> list[str]:
    if value is None:
        return ["unparseable"]
    errors = []
    if value.get("case_id") != case["case_id"]:
        errors.append("case_id")
    expected = value.get("expected_behavior")
    acceptable = value.get("acceptable_behaviors")
    if expected not in TYPES:
        errors.append("expected_behavior")
    if not isinstance(acceptable, list) or expected not in acceptable or any(x not in TYPES for x in acceptable):
        errors.append("acceptable_behaviors")
    branches = value.get("branch_attributes")
    if not isinstance(branches, list) or len(branches) != len(set(branches)) or any(x not in VOCABULARY for x in branches):
        errors.append("branch_attributes")
    stated = value.get("stated_profile")
    if not isinstance(stated, dict) or any(a not in VOCABULARY or v not in VOCABULARY.get(a, ()) for a, v in stated.items()):
        errors.append("stated_profile")
    facts = value.get("required_facts")
    if not isinstance(facts, list) or (not value.get("exclude") and not 1 <= len(facts) <= 4) or any(not isinstance(x, str) or not x.strip() for x in facts):
        errors.append("required_facts")
    allowed = {p["chunk_id"] for p in case["passages"]}
    for field in ("gold_evidence", "inapplicable_evidence"):
        evidence = value.get(field)
        if not isinstance(evidence, list) or any(not isinstance(x, str) or x not in allowed for x in evidence):
            errors.append(field)
    if isinstance(value.get("gold_evidence"), list) and isinstance(value.get("inapplicable_evidence"), list):
        if set(value["gold_evidence"]) & set(value["inapplicable_evidence"]):
            errors.append("evidence_overlap")
    if value.get("answerability") not in ANSWERABILITY:
        errors.append("answerability")
    if not isinstance(value.get("exclude"), bool):
        errors.append("exclude")
    if not isinstance(value.get("notes"), str) or len(str(value.get("notes", "")).split()) > 20:
        errors.append("notes")
    return errors


def user_prompt(case: dict) -> str:
    per_passage = max(700, min(2800, 9000 // max(1, len(case["passages"]))))
    passages = [{"chunk_id": p["chunk_id"], "title": p.get("title"), "section": p.get("section"), "text": p["text"][:per_passage]}
                for p in case["passages"]]  # fmt: skip
    payload = {"case_id": case["case_id"], "question": case["question"], "session_history": case.get("session_history") or [],
               "gold_profile_for_evidence_applicability_only": case.get("gold_profile") or {}, "passages": passages}  # fmt: skip
    return json.dumps(payload, ensure_ascii=False)


async def label(args) -> int:
    output = Path(args.output).resolve()
    if output.exists() and not args.resume:
        raise SystemExit(f"{output} exists; use --resume")
    cases = load_jsonl(INPUT)
    done_rows = load_jsonl(output) if output.exists() else []
    done = {row["case_id"] for row in done_rows}
    settings = get_settings()
    ollama = OllamaClient(settings.ollama_base_url, timeout=600)
    models = {m["name"]: m for m in await ollama.list_models()}
    if args.model not in models:
        raise SystemExit(f"model {args.model!r} is not installed")
    identity = await ollama.model_identity(models[args.model])
    options = {"temperature": 0.0, "num_predict": 1200, "num_ctx": 4096, "seed": 42}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{output.stem}.jsonl"
    failures = []
    for number, case in enumerate(cases, 1):
        if case["case_id"] in done:
            continue
        prompt = user_prompt(case)
        raw, usage = await ollama.complete(models[args.model], [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                            options, think="off", timeout=600)  # fmt: skip
        value, normalizations = normalize(parse(raw), case)
        errors = validate(value, case)
        attempts = 1
        if errors:
            repair = f"Your previous reply failed validation: {', '.join(errors)}. Return a corrected JSON object only.\n\nCASE:\n{prompt}\n\nPREVIOUS:\n{raw[:1200]}"
            raw2, usage2 = await ollama.complete(models[args.model], [{"role": "system", "content": SYSTEM}, {"role": "user", "content": repair}],
                                                 options, think="off", timeout=600)  # fmt: skip
            attempts = 2
            value, repaired = normalize(parse(raw2), case)
            normalizations.extend(repaired)
            errors = validate(value, case)
            raw = raw2
            usage = {"first": usage, "repair": usage2}
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"case_id": case["case_id"], "raw": raw, "errors": errors, "normalizations": normalizations,
                                     "attempts": attempts, "usage": usage}, ensure_ascii=False) + "\n")  # fmt: skip
        if errors:
            failures.append({"case_id": case["case_id"], "errors": errors})
            print(f"{number}/{len(cases)} {case['case_id']} INVALID {errors}", flush=True)
            continue
        value["annotator"], value["origin"] = args.annotator, "agent_draft"
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        done.add(case["case_id"])
        print(f"{number}/{len(cases)} {case['case_id']} {value['expected_behavior']} attempts={attempts}", flush=True)
    rows = load_jsonl(output) if output.exists() else []
    missing = sorted({c["case_id"] for c in cases} - {r["case_id"] for r in rows})
    meta = {"prompt_version": PROMPT_VERSION, "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
            "input_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(), "model": identity, "annotator": args.annotator,
            "options": {**options, "thinking": "off"}, "updated_at": datetime.now(UTC).isoformat(), "rows": len(rows),
            "expected_behavior": Counter(r["expected_behavior"] for r in rows), "missing": missing, "last_run_failures": failures}  # fmt: skip
    output.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1, default=dict) + "\n", encoding="utf-8")
    await ollama.http.aclose()
    print(json.dumps({"rows": len(rows), "missing": len(missing), "failures": len(failures), "counts": meta["expected_behavior"]}, default=dict))
    return 1 if missing else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--annotator", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    return asyncio.run(label(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
