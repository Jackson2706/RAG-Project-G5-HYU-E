"""Deck v4 Task 4, stage A: each AAES+ step alone (component tests). Dev, dev-2 and new component sets only.

Run from Sources/ (conda env RAG; set HYU_LLM_CACHE=../.run/llm_cache to replay identical LLM requests):
  python scripts/deck_v4_aaes_plus.py step1-build     # dev questions + reply templates + adjudicated new messages -> component/step1.jsonl
  python scripts/deck_v4_aaes_plus.py freeze          # SHA-256 of every component set -> component/FROZEN.sha256 (before any extractor runs)
  python scripts/deck_v4_aaes_plus.py step1           # rules / llm / both on step1.jsonl -> component/step1_results.jsonl + component.json
  python scripts/deck_v4_aaes_plus.py step2-build     # 300 (question, profile, passage) triples from A0 retrieval on dev + dev-2
  python scripts/deck_v4_aaes_plus.py step2           # rules / llm / both labels vs the adjudicated triples
  python scripts/deck_v4_aaes_plus.py step34          # steps 3 and 4 alone on dev + dev-2 (stops before generation)

Every block runs with the same models as the evaluation: qwen3.5:4b, temperature 0, seed 42, thinking off, 4,096 context.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluation import hyu_suite  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.applicability import VOCABULARY  # noqa: E402
from app.rag.registry import create_block  # noqa: E402
from app.rag.schemas import Services  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v4" / "aaes_plus"
COMP = OUT / "component"
AUX = {"model": "qwen3.5:4b", "temperature": 0.0, "max_tokens": 256}
MODES = ("rules", "llm", "both")


def services() -> Services:
    settings = get_settings().model_copy(update={"embedding_device": "auto"})
    return Services(db=Database.connect(settings).for_index(settings.hyu_index_id), ollama=OllamaClient(settings.ollama_base_url, timeout=settings.ollama_timeout),
                    settings=settings)  # fmt: skip


def known_of(profile: dict) -> dict[str, str]:
    """Attributes the student stated or that are remembered: {attribute: value} (first value)."""
    return {a: e["values"][0] for a, e in profile.items() if e["status"] in ("stated", "remembered", "stale") and e["values"]}


# ------------------------------------------------------------------------------------------------ step 1


def step1_build() -> int:
    """150 messages: the 47 dev questions (gold = their stated_profile), 13 Task-2 reply templates, 90 adjudicated new messages."""
    from deck_v4_followup import reply_for

    rows = []
    for c in hyu_suite.load_cases("dev"):
        rows.append({"mid": c["case_id"], "source": "dev", "message": c["question"], "history": hyu_suite.history_of(c),
                     "gold": {a: (v[0] if isinstance(v, list) else v) for a, v in (c.get("stated_profile") or {}).items() if v}, "hard_case": "dev"})  # fmt: skip
    templates = [("campus", "seoul"), ("campus", "erica"), ("degree_level", "master"), ("degree_level", "undergraduate"), ("year", "2"),
                 ("student_type", "exchange"), ("visa", "D-4"), ("topik_level", "none"), ("topik_level", "3"), ("english_track", "yes"),
                 ("academic_status", "completed_coursework"), ("academic_status", "leave_of_absence"), ("korean_standard", "pass")]  # fmt: skip
    for n, (a, v) in enumerate(templates, 1):
        rows.append({"mid": f"R{n:02d}", "source": "reply_template", "message": reply_for(a, {a: v}), "history": [], "gold": {a: v}, "hard_case": "template"})
    for r in load_jsonl(COMP / "step1_adjudicated.jsonl"):
        rows.append({**r, "source": "new"})
    (COMP / "step1.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(len(rows), Counter(r["source"] for r in rows))
    return 0


def freeze() -> int:
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in sorted(COMP.glob("step*.jsonl")) if "draft" not in p.name and "results" not in p.name
             and "label" not in p.name]  # fmt: skip
    (COMP / "FROZEN.sha256").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def check_frozen(name: str) -> None:
    expected = dict(line.split("  ")[::-1] for line in (COMP / "FROZEN.sha256").read_text().splitlines())
    if hashlib.sha256((COMP / name).read_bytes()).hexdigest() != expected.get(name):
        raise SystemExit(f"{name} is not frozen (or changed after freezing): run freeze first")


def prf(tp: int, fp: int, fn: int) -> dict:
    """>>> prf(8, 2, 2) -> {'precision': 0.8, 'recall': 0.8, 'f1': 0.8}"""
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": round(p, 3) if p is not None else None, "recall": round(r, 3) if r is not None else None, "f1": round(f, 3) if f is not None else None}


async def step1() -> int:
    check_frozen("step1.jsonl")
    svc = services()
    rows = load_jsonl(COMP / "step1.jsonl")
    results = []
    for mode in MODES:
        block = create_block("query_understanding", "profile_understanding", {"mode": mode, **AUX}, svc)
        for r in rows:
            block.trace_details = {}
            start = time.perf_counter()
            analysis = await block.analyze(r["message"], r["history"])
            ms = round((time.perf_counter() - start) * 1000, 1)
            results.append({"mid": r["mid"], "mode": mode, "pred": known_of(analysis.profile), "gold": r["gold"], "hard_case": r["hard_case"], "ms": ms,
                            "fallbacks": block.trace_details.get("fallbacks", {}), "llm_raw": (block.trace_details.get("llm_raw") or [""])[0][:300]})  # fmt: skip
        print(mode, "done", flush=True)
    (COMP / "step1_results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    summary = {}
    for mode in MODES:
        rs = [r for r in results if r["mode"] == mode]
        per = {}
        for a in VOCABULARY:
            tp = sum(r["gold"].get(a) is not None and r["pred"].get(a) == r["gold"].get(a) for r in rs)
            fp = sum(r["pred"].get(a) is not None and r["pred"].get(a) != r["gold"].get(a) for r in rs)
            fn = sum(r["gold"].get(a) is not None and r["pred"].get(a) != r["gold"].get(a) for r in rs)
            per[a] = {**prf(tp, fp, fn), "gold": sum(a in r["gold"] for r in rs)}
        all_tp = sum(1 for r in rs for a, v in r["gold"].items() if r["pred"].get(a) == v)
        all_fp = sum(1 for r in rs for a, v in r["pred"].items() if r["gold"].get(a) != v)
        all_fn = sum(1 for r in rs for a, v in r["gold"].items() if r["pred"].get(a) != v)
        hard = defaultdict(list)
        for r in rs:
            hard[r["hard_case"]].append(r["pred"] == r["gold"])
        summary[mode] = {"messages": len(rs), "micro": prf(all_tp, all_fp, all_fn), "per_attribute": per,
                         "exact_profile_match": round(sum(r["pred"] == r["gold"] for r in rs) / len(rs), 3),
                         "invented_values": sum(1 for r in rs for a in r["pred"] if a not in r["gold"]),
                         "exact_match_by_hard_case": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(hard.items())},
                         "ms_per_message": round(sum(r["ms"] for r in rs) / len(rs), 1),
                         "fallback_items": sum(sum(r["fallbacks"].values()) for r in rs)}  # fmt: skip
    _update_component({"step1": summary})
    print(json.dumps({m: {k: v for k, v in s.items() if k != "per_attribute"} for m, s in summary.items()}, indent=1))
    return 0


def _update_component(part: dict) -> None:
    path = OUT / "component.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(part)
    path.write_text(json.dumps(data, indent=1) + "\n")


# ------------------------------------------------------------------------------------------------ step 2

RULE_NAME = {"unconditioned": "everyone", "compatible": "this_student", "conflicting": "other_students", "open": "depends", "unknown": "unknown"}


def _cases() -> list[dict]:
    return hyu_suite.load_cases("dev") + hyu_suite.load_cases("dev2")


async def step2_build() -> int:
    """300 triples: top-6 passages after the cross-encoder (A0 retrieval, rules profile) on dev + dev-2, about a third with unknown tags."""
    from app.rag.pipeline import run_rag
    from app.rag.presets import preset_config

    svc, rows = services(), []
    for case in _cases():
        config = preset_config("A0_AAES")
        trace = await run_rag(hyu_suite.question_for(case, config), config, svc, stop_after="reranking", save_trace=False, history=hyu_suite.history_of(case))
        stages = {st["stage_id"]: st for st in trace["stages"]}
        known = known_of(stages["query_understanding"]["output"]["profile"])
        for rank, e in enumerate(stages["reranking"]["output"][:6], 1):
            app = e.get("applicability") or {}
            rows.append({"tid": f"{case['case_id']}#{rank}", "case_id": case["case_id"], "question": case["question"], "history": hyu_suite.history_of(case),
                         "known": known, "chunk_id": e["chunk_id"], "title": e.get("title"), "text": e["text"][:1500],
                         "unknown_tags": app.get("condition_status") == "unknown"})  # fmt: skip
    rng = random.Random(42)
    unknown = [r for r in rows if r["unknown_tags"]]
    tagged = [r for r in rows if not r["unknown_tags"]]
    pick = rng.sample(unknown, min(100, len(unknown)))
    pick += rng.sample(tagged, 300 - len(pick))
    rng.shuffle(pick)
    (COMP / "step2.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pick), encoding="utf-8")
    blind = [{k: r[k] for k in ("tid", "question", "history", "known", "title", "text")} for r in pick]
    (COMP / "step2_label_input.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in blind), encoding="utf-8")
    print("triples", len(pick), "unknown-tag", sum(r["unknown_tags"] for r in pick), "of", len(rows))
    return 0


async def step2() -> int:
    """Labels for each triple by rules (tags + overlap), llm (batched per question, as in the reranker) and both, vs the adjudicated labels."""
    from types import SimpleNamespace

    from app.rag import aaes_llm
    from app.rag.aaes import label_chunk
    from app.rag.text import query_coverage

    check_frozen("step2.jsonl")
    check_frozen("step2_gold.jsonl")
    svc = services()
    gold = {g["tid"]: g for g in load_jsonl(COMP / "step2_gold.jsonl")}
    triples = load_jsonl(COMP / "step2.jsonl")
    chunks = {c["chunk_id"]: c for c in svc.db.chunks.find({"chunk_id": {"$in": [t["chunk_id"] for t in triples]}}, {"_id": 0, "embedding": 0})}
    by_case = defaultdict(list)
    for t in triples:
        by_case[t["case_id"]].append(t)
    results = []
    for case_id, ts in by_case.items():
        known = {a: [v] for a, v in ts[0]["known"].items()}
        block = SimpleNamespace(services=svc, params=AUX | {"max_tokens": 512}, trace_details={})
        ids = {f"P{i}": t for i, t in enumerate(ts, 1)}
        student = "; ".join(f"{a}: {', '.join(v)}" for a, v in known.items()) or "nothing known"
        user = f"Question: {ts[0]['question']}\nKnown about the student: {student}\n\n" + "\n\n".join(f"[{p}]\n{t['text'][:1200]}" for p, t in ids.items())
        start = time.perf_counter()
        parsed, _ = aaes_llm.parse_applies(await aaes_llm.call(block, aaes_llm.APPLIES, user), {p: t["text"] for p, t in ids.items()}, known)
        ms = (time.perf_counter() - start) * 1000 / len(ts)
        for p, t in ids.items():
            app = chunks[t["chunk_id"]].get("applicability") or {}
            cond = {k: app.get(k) for k in ("campus", "scope", "constraints", "any_of")}
            rule = RULE_NAME[label_chunk(cond, chunks[t["chunk_id"]].get("condition_status"), known)]
            overlap = query_coverage(t["question"], chunks[t["chunk_id"]]["text"]) >= 0.30
            llm = parsed.get(p)
            llm_label = RULE_NAME[llm["label"]] if llm else rule
            both = llm_label if rule == "unknown" else rule
            results.append({"tid": t["tid"], "unknown_tags": t["unknown_tags"], "gold": gold[t["tid"]], "ms_llm": round(ms, 1),
                            "rules": {"applies": rule, "relevant": overlap}, "llm": {"applies": llm_label, "relevant": llm["relevant"] if llm else overlap},
                            "both": {"applies": both, "relevant": overlap or bool(llm and llm["relevant"])}})  # fmt: skip
        print(case_id, flush=True)
    (COMP / "step2_results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    summary = {}
    for mode in MODES:
        part = {}
        for name, rs in (("all", results), ("unknown_tags", [r for r in results if r["unknown_tags"]]), ("tagged", [r for r in results if not r["unknown_tags"]])):
            part[name] = {"triples": len(rs), "applies_accuracy": round(sum(r[mode]["applies"] == r["gold"]["applies"] for r in rs) / len(rs), 3),
                          "relevant_accuracy": round(sum(r[mode]["relevant"] == r["gold"]["relevant"] for r in rs) / len(rs), 3),
                          "no_label": sum(r[mode]["applies"] == "unknown" for r in rs),
                          "confusion_gold_by_pred": dict(sorted(Counter(f"{r['gold']['applies']}|{r[mode]['applies']}" for r in rs).items()))}  # fmt: skip
        summary[mode] = part
    summary["llm_ms_per_triple"] = round(sum(r["ms_llm"] for r in results) / len(results), 1)
    _update_component({"step2": summary})
    print(json.dumps({m: {k: {x: y for x, y in v.items() if x != "confusion_gold_by_pred"} for k, v in s.items()} for m, s in summary.items() if m in MODES}, indent=1))
    return 0


# ------------------------------------------------------------------------------------------------ steps 3 and 4

TYPE = {"ANSWER": "answer", "CONDITIONAL": "conditional_answer", "CLARIFY": "clarify", "CONFIRM": "clarify", "ABSTAIN": "abstain"}
STEP34 = {"RRRR": "A0_AAES", "RRLR": "AP_RRLR", "RRBR": "AP_RRBR", "RRRL": "AP_RRRL", "RRRB": "AP_RRRB"}


async def step34() -> int:
    """Steps 3 and 4 alone on dev + dev-2 (steps 1-2 rules; stops after evidence sufficiency, so no answer is written)."""
    from app.rag.pipeline import run_rag
    from app.rag.presets import preset_config

    svc, rows = services(), []
    cases = _cases()
    for code, preset in STEP34.items():
        config = preset_config(preset)
        for case in cases:
            trace = await run_rag(hyu_suite.question_for(case, config), config, svc, stop_after="evidence_sufficiency", save_trace=False,
                                  history=hyu_suite.history_of(case))  # fmt: skip
            stage = next(st for st in trace["stages"] if st["stage_id"] == "evidence_sufficiency")
            sig = (stage.get("output") or {}).get("signals") or {}
            action = sig.get("action") or "ABSTAIN"
            chosen = sig.get("clarify_attribute") or ((sig.get("branch_attributes") or [None])[0] if action == "CONDITIONAL" else None)
            rows.append({"version": code, "case_id": case["case_id"], "split": case["split"], "expected": case["expected_behavior"],
                         "acceptable": case["acceptable_behaviors"], "labelled_details": case.get("branch_attributes") or [], "action": action,
                         "reason": sig.get("reason"), "chosen_detail": chosen, "llm_calls": (stage.get("details") or {}).get("llm_calls", 0),
                         "fallbacks": (stage.get("details") or {}).get("fallbacks", {})})  # fmt: skip
        print(code, "done", flush=True)
    (COMP / "step34_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    summary = {}
    for code in STEP34:
        rs = [r for r in rows if r["version"] == code]
        need = [r["expected"] in ("conditional_answer", "clarify") for r in rs]
        split = [r["action"] in ("CONDITIONAL", "CLARIFY", "CONFIRM") for r in rs]
        tp = sum(a and b for a, b in zip(need, split, strict=True))
        splits = [r for r in rs if r["chosen_detail"]]
        summary[code] = {"cases": len(rs), "needs_split": prf(tp, sum(b and not a for a, b in zip(need, split, strict=True)), sum(a and not b for a, b in zip(need, split, strict=True))),
                         "detail_matches_label": f"{sum(r['chosen_detail'] in r['labelled_details'] for r in splits)}/{len(splits)}",
                         "says_none_when_nothing_depends": f"{sum(not r['chosen_detail'] for r in rs if not r['labelled_details'])}/{sum(not r['labelled_details'] for r in rs)}",
                         "reply_type_correct": round(sum(TYPE[r['action']] == r['expected'] for r in rs) / len(rs), 3),
                         "reply_type_acceptable": round(sum(TYPE[r['action']] in r['acceptable'] for r in rs) / len(rs), 3),
                         "confusion_expected_by_predicted": dict(sorted(Counter(f"{r['expected']}|{TYPE[r['action']]}" for r in rs).items())),
                         "llm_calls_per_case": round(sum(r["llm_calls"] for r in rs) / len(rs), 2), "fallbacks": sum(sum(r["fallbacks"].values()) for r in rs)}  # fmt: skip
    _update_component({"step3_step4": summary})
    print(json.dumps({c: {k: v for k, v in s.items() if k != "confusion_expected_by_predicted"} for c, s in summary.items()}, indent=1))
    return 0


async def probe() -> int:
    """Short dev-only checks of the patched LLM boundaries; stops before answer generation."""
    from app.rag.pipeline import run_rag
    from app.rag.presets import preset_config

    svc = services()
    models = {m["name"]: m for m in await svc.ollama.list_models()}
    identity = await svc.ollama.model_identity(models[AUX["model"]])
    rows = []
    block = create_block("query_understanding", "profile_understanding", {"mode": "both", **AUX}, svc)
    for name, question in (("topik", "I don't have a TOPIK score. Can I still get a part-time permit?"),
                           ("hypothetical_identity", "If I were a master's student at ERICA, could I work more hours?")):
        block.trace_details = {}
        analysis = await block.analyze(question)
        rows.append({"name": name, "question": question, "profile": known_of(analysis.profile), "details": block.trace_details})

    dev = {c["case_id"]: c for c in hyu_suite.load_cases("dev")}
    scenarios = [("winter_school", "AP_RRBR", dev["T14-042"]["question"], []),
                 ("different_insurance_rules", "AP_BBBB", dev["T14-132"]["question"], []),
                 ("insurance_after_coursework", "AP_BBBB", "I finished my coursework. Which insurance applies to me?", [])]  # fmt: skip
    assert len({name for name, *_ in scenarios}) == len(scenarios)
    for name, preset, question, history in scenarios:
        trace = await run_rag(question, preset_config(preset), svc, stop_after="evidence_sufficiency", save_trace=False, history=history)
        stages = {stage["stage_id"]: stage for stage in trace["stages"]}
        rows.append({"name": name, "preset": preset, "question": question, "status": trace["status"], "error": trace.get("error"),
                     "profile": (stages.get("query_understanding", {}).get("output") or {}).get("profile"),
                     "reranking_details": stages.get("reranking", {}).get("details"),
                     "decision": stages.get("evidence_sufficiency", {}).get("output"),
                     "sufficiency_details": stages.get("evidence_sufficiency", {}).get("details")})  # fmt: skip
        print(name, trace["status"], trace.get("action"), flush=True)

    prior = load_jsonl(COMP / "step1_results.jsonl") if (COMP / "step1_results.jsonl").exists() else []
    invalid = next((r for r in prior if r.get("fallbacks")), None)
    result = {"scope": "dev and synthetic only; stopped after evidence sufficiency", "index_id": svc.db.index_id,
              "model": identity, "options": {"temperature": 0.0, "seed": 42, "thinking": "off", "num_ctx": 4096},
              "existing_actual_invalid_step1_item": invalid, "probes": rows}  # fmt: skip
    (OUT / "patch_probe.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    assert prf(8, 2, 2) == {"precision": 0.8, "recall": 0.8, "f1": 0.8}
    cmd = sys.argv[1]
    sync = {"step1-build": step1_build, "freeze": freeze}
    raise SystemExit(sync[cmd]() if cmd in sync else asyncio.run({"step1": step1, "step2-build": step2_build, "step2": step2, "step34": step34,
                                                                  "probe": probe}[cmd]()))  # fmt: skip
