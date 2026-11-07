"""The headless benchmark runner. No UI, no FastAPI: it calls the app's pipeline (run_rag) directly.

    python -m evaluation.runner --suite all --dry-run      # check every configuration, load nothing heavy
    python -m evaluation.runner --suite all --smoke        # 5 queries on a small corpus slice (fast check)
    python -m evaluation.runner --suite all                # everything that applies
    python -m evaluation.runner --suite retrieval --dataset scifact --experiment R2_HYBRID_RRF
    python -m evaluation.runner --suite all --resume       # continue an interrupted run
    python -m evaluation.runner --download scifact,nfcorpus,arguana

Each task (experiment × dataset × protocol) ends as COMPLETED, NOT_APPLICABLE, BLOCKED (a model or
service is missing) or FAILED (an error) — with the reason. Per-query results are appended to
evaluation/results/<run-id>/raw/ as they are produced, so an interrupted run can be resumed.
Metrics and reports are computed from those files by evaluation/reports.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from evaluation import ROOT, beir
from evaluation.indexes import ensure_folder_index, ensure_index, index_id
from evaluation.reports import load_jsonl, write_reports

from app.config import get_settings  # noqa: E402  (evaluation/__init__ puts backend/ on the path)
from app.database import Database
from app.ollama import OllamaClient, OllamaError
from app.rag.pipeline import answer_from_evidence, run_rag
from app.rag.presets import PRESETS_BY_ID, preset_config
from app.rag.registry import ConfigError, create_block
from app.rag.schemas import Evidence, FilterCriteria, Services

EVAL_DIR = ROOT / "evaluation"
CONFIG_DIR, RESULTS_DIR = EVAL_DIR / "configs", EVAL_DIR / "results"
SMOKE_QUERIES, SMOKE_EXTRA_DOCS = 5, 300
STOP_AFTER = "evidence_sufficiency"  # retrieval-only: never generate an answer for BEIR ranking metrics


@dataclass
class Task:
    suite: str  # offline | retrieval | fixture | generation
    experiment: str
    dataset: str
    protocol: str = "B"
    preset: str | None = None
    index_key: str | None = None
    overrides: dict = field(default_factory=dict)
    query_limit: int | None = None
    options: dict = field(default_factory=dict)
    status: str = "PENDING"
    reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.suite}/{self.dataset}/{self.experiment}__{self.protocol}"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# --------------------------------------------------------------------------------------------- planning


def build_plan(args, offline: dict, online: dict, generation: dict) -> list[Task]:
    suites = {"all": ["offline", "retrieval", "generation"], "offline": ["offline"], "retrieval": ["retrieval"],
              "generation": ["generation"]}[args.suite]  # fmt: skip
    wanted_datasets = set(args.dataset.split(",")) if args.dataset else None
    wanted_experiments = set(args.experiment.split(",")) if args.experiment else None
    tasks: list[Task] = []

    def keep(dataset: str, experiment: str) -> bool:
        return (wanted_datasets is None or dataset in wanted_datasets) and (wanted_experiments is None or experiment in wanted_experiments)

    if "offline" in suites:
        for ds in offline["datasets"]:
            for e in offline["experiments"]:
                if keep(ds, e["id"]):
                    tasks.append(Task("offline", e["id"], ds, e.get("protocol", "B"), e["preset"], e["index"],
                                      options={k: e[k] for k in ("latency_repeats", "store_chunks", "ann_reference") if k in e}))  # fmt: skip
    if "retrieval" in suites:
        for ds in online["datasets"]:
            for e in online["experiments"]:
                if not keep(ds, e["id"]):
                    continue
                if "not_applicable" in e:
                    tasks.append(Task("retrieval", e["id"], ds, "-", status="NOT_APPLICABLE", reason=e["not_applicable"]))
                    continue
                if "same_as" in e:
                    tasks.append(Task("retrieval", e["id"], ds, "-", status="SHARED", reason=f"identical configuration to {e['same_as']}; its results apply"))
                    continue
                for protocol in e.get("protocols", ["B"]):
                    limit = online["llm_query_limit"] if e.get("llm") else None
                    tasks.append(Task("retrieval", e["id"], ds, protocol, e["preset"], "whole_document" if protocol == "A" else online["index"],
                                      overrides=e.get("overrides", {}), query_limit=limit,
                                      options={"llm": e.get("llm", False), "branch_depth_factor": e.get("branch_depth_factor", 1.0)}))  # fmt: skip
        for exp in ("R0_DENSE", "R9_PREFILTERING", "R10_POSTFILTERING", "R12_SUFFICIENCY_GATE"):
            if keep("hyu_fixture", exp):
                tasks.append(Task("fixture", exp, "hyu_fixture", "-", exp, online["fixture"]["index"]))
    if "generation" in suites:
        for backbone in generation["backbones"]:
            if keep("cases", f"GEN_{backbone}") or (wanted_experiments and "GENERATION" in wanted_experiments):
                tasks.append(Task("generation", f"GEN_{backbone}", "cases", "-", generation["retrieval_preset"], options={"model": backbone}))
    return tasks


def depth_overrides(base: dict, task: Task, depth: dict, aux_model: str | None) -> dict:
    """Benchmark depths (e.g. 600 chunks so up to 100 distinct documents can be scored) and the frozen
    auxiliary LLM. Chat defaults (Top 5) are far too shallow for MAP@100 / Recall@100."""
    units = depth.get("units_protocol_a", depth["documents"]) if task.protocol == "A" else depth["chunks"]
    factor = task.options.get("branch_depth_factor", 1.0)
    o: dict[str, dict] = {}
    for stage in ("dense_retrieval", "lexical_retrieval"):
        if base[stage]["method"]:
            o[stage] = {"params": {"top_k": max(1, int(units * factor))}}
    if base["hybrid_fusion"]["method"]:
        o["hybrid_fusion"] = {"params": {"top_k": units}}
    if base["reranking"]["method"] in ("coverage", "cross_encoder"):
        o["reranking"] = {"params": {"rerank_depth": depth.get("rerank", 100)}}
    if aux_model:
        for stage in ("query_rewriting", "reranking"):
            method = base[stage]["method"]
            if method in ("llm_rewrite", "multi_query", "hyde", "rankgpt"):
                o[stage] = deep_merge(o.get(stage, {}), {"params": {"model": aux_model}})
    return deep_merge(o, task.overrides)


def retrieval_config(run: Run, task: Task) -> dict:
    """The validated configuration of an offline/retrieval task: its preset plus benchmark depths and the auxiliary LLM.
    The dry run checks exactly this configuration, so a READY task is the one that really runs."""
    depth = (run.offline if task.suite == "offline" else run.online)["depth"]
    aux = run.online.get("auxiliary_llm") if task.options.get("llm") else None
    return preset_config(task.preset, depth_overrides(preset_config(task.preset), task, depth, aux))


# --------------------------------------------------------------------------------------------- the run context


class Run:
    def __init__(self, args) -> None:
        self.args = args
        self.run_id = args.run_id or ("smoke" if args.smoke else "main")
        self.dir = RESULTS_DIR / self.run_id
        self.raw = self.dir / "raw"
        self.offline, self.online, self.generation = load_yaml("offline.yaml"), load_yaml("online.yaml"), load_yaml("generation.yaml")
        self.split = args.split or self.online["split"]
        self.settings = get_settings().model_copy(update={"embedding_device": "auto"})
        self.db = Database.connect(self.settings)
        self.ollama = OllamaClient(self.settings.ollama_base_url, timeout=self.settings.ollama_timeout)
        self.services = Services(db=self.db, ollama=self.ollama, settings=self.settings)
        self._datasets: dict[str, tuple] = {}
        self._built: set[str] = set()  # indexes already (re)built in this session (--force rebuilds each once)
        self.index_presets = {e["index"]: e["preset"] for e in self.offline["experiments"]}
        self.status_file = self.dir / "status.json"
        self.status = json.loads(self.status_file.read_text()) if self.status_file.exists() else {}

    # ---- datasets (a smoke run uses a small, fixed slice)
    def dataset(self, name: str) -> tuple[dict, dict, dict]:
        if name not in self._datasets:
            corpus, queries, qrels = beir.load(name, self.split)
            if self.args.smoke:
                keep_q = sorted(queries)[:SMOKE_QUERIES]
                judged = {d for q in keep_q for d in qrels[q]}
                extra = random.Random(13).sample(sorted(set(corpus) - judged), min(SMOKE_EXTRA_DOCS, len(corpus) - len(judged)))
                corpus = {d: corpus[d] for d in sorted(judged | set(extra)) if d in corpus}
                queries, qrels = {q: queries[q] for q in keep_q}, {q: qrels[q] for q in keep_q}
            self._datasets[name] = (corpus, queries, qrels)
        return self._datasets[name]

    def query_ids(self, name: str, limit: int | None) -> list[str]:
        qids = sorted(self.dataset(name)[1])
        if self.args.max_queries:
            limit = min(limit or self.args.max_queries, self.args.max_queries)
        return qids[:limit] if limit else qids

    def index_config(self, key: str) -> dict:
        return preset_config(self.index_presets[key])

    def index(self, dataset: str, key: str) -> Database:
        corpus = self.dataset(dataset)[0]
        idx = index_id(dataset, key, self.args.smoke)
        source = json.loads((beir.dataset_dir(dataset) / "SOURCE.json").read_text())
        db, _ = ensure_index(self.services, idx, self.index_config(key), beir.to_parsed_documents(dataset, corpus),
                             {"dataset": dataset, "documents": len(corpus), "source": source, "smoke_slice": self.args.smoke,
                              "parser": "evaluation/beir.py to_parsed_documents (title + text, one section)"},
                             force=self.args.force and key not in self._built)  # fmt: skip
        self._built.add(key)
        return db

    def raw_file(self, task: Task) -> Path:
        path = self.raw / task.suite / task.dataset / f"{task.experiment}__{task.protocol}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_status(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(self.status, indent=2))


def read_done(path: Path) -> set[str]:
    """Queries with a completed result. Failed queries are retried by --resume (the newer line wins in the reports)."""
    return {r["qid"] for r in load_jsonl(path) if r.get("status") == "completed"}


def append(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# --------------------------------------------------------------------------------------------- trace → record


def doc_ranking(items: list[dict] | None, doc_map: dict[str, str], depth: int) -> list[str]:
    return beir.documents_from_chunks([doc_map.get(i["doc_id"], i["doc_id"]) for i in items or []], depth)


def extract(trace: dict, doc_map: dict[str, str], depth: int, store_chunks: bool = False) -> dict:
    """What the reports need from one run_rag trace (rankings as ORIGINAL document IDs, timings, decisions)."""
    stages = {s["stage_id"]: s for s in trace["stages"]}

    def out(stage_id: str):
        s = stages.get(stage_id)
        return s["output"] if s and s["status"] == "completed" else None

    final = out("reranking") or out("metadata_enrichment") or []
    selected = out("evidence_selection") or []
    rec: dict[str, Any] = {
        "status": trace["status"], "error": trace["error"], "total_ms": trace.get("total_ms"),
        "ranking": doc_ranking(final, doc_map, depth + 5),  # +5: room for BEIR's removal of the query's own ID
        "units_ranked": len(final),
        "candidates": {name: doc_ranking((out(sid) or {}).get("candidates"), doc_map, depth + 5)
                       for name, sid in (("dense", "dense_retrieval"), ("lexical", "lexical_retrieval"), ("fused", "hybrid_fusion")) if out(sid)},
        "selected": doc_ranking(selected, doc_map, len(selected) or 1) if selected else [],
        "selected_units": len(selected), "selected_tokens": sum(e.get("token_count", 0) for e in selected),
        "timings": {sid: s["duration_ms"] for sid, s in stages.items() if s["status"] == "completed"},
        "stage_status": {sid: s["status"] for sid, s in stages.items()},
    }  # fmt: skip
    if dense := out("dense_retrieval"):
        rec["dense"] = {k: dense["details"].get(k) for k in ("embed_ms", "search_ms", "search_mode", "embedded") if k in dense["details"]}
        if store_chunks:
            rec["dense_chunks"] = [c["chunk_id"] for c in dense["candidates"][:depth]]
    if lexical := out("lexical_retrieval"):
        rec["lexical"] = {k: lexical["details"].get(k) for k in ("search_ms", "matching_chunks") if k in lexical["details"]}
    if rewrite := out("query_rewriting"):
        rec["rewrite"] = {"query": rewrite["query"], "alternatives": rewrite["alternatives"], "validation": rewrite["validation"],
                          "embedding_text": (rewrite.get("embedding_text") or "")[:400] or None,
                          "details": stages["query_rewriting"].get("details")}  # fmt: skip
    if stages.get("reranking", {}).get("details"):
        rec["rerank"] = stages["reranking"]["details"]
    if (gate := out("evidence_sufficiency")) is not None:
        rec["gate"] = gate
    return rec


# --------------------------------------------------------------------------------------------- task execution


async def run_retrieval_task(run: Run, task: Task) -> dict:
    corpus, queries, qrels = run.dataset(task.dataset)
    depth = (run.offline if task.suite == "offline" else run.online)["depth"]
    db = run.index(task.dataset, task.index_key)
    config = retrieval_config(run, task)
    doc_map = {d["doc_id"]: beir.beir_id(d["source_uri"]) for d in db.documents.find({}, {"_id": 0, "doc_id": 1, "source_uri": 1})}
    services = Services(db=db, ollama=run.ollama, settings=run.settings)
    path = run.raw_file(task)
    done = read_done(path)
    qids = [q for q in run.query_ids(task.dataset, task.query_limit) if q not in done]
    repeats = task.options.get("latency_repeats", 0)
    dense_block = None
    if repeats:
        dense_block = create_block("dense_retrieval", config["dense_retrieval"]["method"], config["dense_retrieval"]["params"],
                                   replace(services, embedder=create_block("embedding", config["embedding"]["method"], config["embedding"]["params"], services)))  # fmt: skip
    failures, start = 0, time.perf_counter()
    for n, qid in enumerate(qids, start=1):
        trace = await run_rag(queries[qid], config, services, stop_after=STOP_AFTER, save_trace=False)
        rec = {"qid": qid, **extract(trace, doc_map, depth["documents"], task.options.get("store_chunks", False))}
        if dense_block and trace["status"] == "completed":
            rec["latency_repeats_ms"] = [(await dense_block.retrieve(queries[qid])).details["search_ms"] for _ in range(repeats)]
        append(path, rec)
        failures += rec["status"] != "completed"
        if n <= 5 and failures == n:  # the first queries all fail: a systematic problem, stop early
            raise RuntimeError(f"the first {n} queries failed: {rec['error']}")
        if n % 50 == 0 or n == len(qids):
            rate = n / (time.perf_counter() - start)
            print(f"    {task.key}: {n}/{len(qids)} queries ({rate:.1f}/s, {failures} failed)", flush=True)
    return {"queries": len(read_done(path)), "failed_queries": failures, "index_id": db.index_id, "config": config,
            "index_manifest": db.get_manifest(), "storage": db.storage_info()}  # fmt: skip


async def run_fixture_task(run: Run, task: Task) -> dict:
    """R0 / R9 / R10 on the metadata fixture, or R12's gate on the HYU sample questions."""
    fixture = run.online["fixture"]
    offline = preset_config("O0_SECTION_AWARE_256_32")
    db, _ = ensure_folder_index(run.services, fixture["index"], offline, ROOT / "data" / "samples", force=run.args.force)
    documents = {d["doc_id"]: d for d in db.documents.find({}, {"_id": 0})}
    services = Services(db=db, ollama=run.ollama, settings=run.settings)
    path = run.raw_file(task)
    done = read_done(path)
    cutoff = fixture["candidate_cutoff"]
    if task.experiment == "R12_SUFFICIENCY_GATE":
        cases = [{"qid": q["qid"], **q} for q in load_jsonl(ROOT / fixture["gate_questions"])]
    else:
        cases = [{"qid": c["case_id"], **c} for c in load_jsonl(ROOT / fixture["metadata_queries"])]
    for case in cases:
        if case["qid"] in done:
            continue
        stages: dict = {}
        if "criteria" in case:  # the same small candidate cutoff for R0, R9 and R10
            stages["dense_retrieval"] = {"params": {"top_k": cutoff}}
        if task.experiment in ("R9_PREFILTERING", "R10_POSTFILTERING"):
            stages["query_understanding"] = {"params": case["criteria"]}
        config = preset_config(task.preset, stages)
        trace = await run_rag(case["question"], config, services, stop_after=STOP_AFTER, save_trace=False)
        rec = {"qid": case["qid"], **extract(trace, {d: documents[d]["source_uri"] for d in documents}, 10)}
        if "criteria" in case:  # eligibility from the documents' declared metadata, with the pipeline's own predicate code
            predicate = FilterCriteria(**case["criteria"]).to_filter()
            eligible = sorted(d["source_uri"] for d in documents.values() if predicate.matches(d.get("metadata", {})))
            rec.update(criteria=case["criteria"], relevant=case["relevant"], eligible=eligible,
                       target=sorted(set(case["relevant"]) & set(eligible)), cutoff=cutoff)  # fmt: skip
        else:
            rec.update(relevant=[u.replace("local://", "") for u in case["relevant"]], answerable=case["answerable"])
        append(path, rec)
    return {"queries": len(read_done(path)), "index_id": db.index_id, "config": preset_config(task.preset)}


async def generation_cases(run: Run) -> list[dict]:
    """The questions both backbones answer: BEIR test queries and the HYU sample questions, with evidence
    retrieved ONCE (B0) and cached, so both models get identical contexts."""
    cache = run.raw / "generation" / "contexts.jsonl"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cached = {c["case_id"]: c for c in load_jsonl(cache)}  # empty when the file does not exist yet
    spec = run.generation["cases"]
    per_dataset = 1 if run.args.smoke else spec["beir"]["per_dataset"]
    wanted: list[tuple[str, str, str, Database]] = []
    for ds in spec["beir"]["datasets"]:
        if run.args.dataset and ds not in run.args.dataset.split(","):
            continue
        _, queries, _ = run.dataset(ds)
        db = run.index(ds, run.online["index"])
        wanted += [(f"{ds}:{q}", ds, queries[q], db) for q in sorted(queries)[:per_dataset]]
    hyu_db, _ = ensure_folder_index(run.services, run.online["fixture"]["index"], preset_config("O0_SECTION_AWARE_256_32"), ROOT / "data" / "samples")
    hyu = load_jsonl(ROOT / spec["hyu_fixture"])[: 2 if run.args.smoke else None]
    wanted += [(f"hyu_fixture:{q['qid']}", "hyu_fixture", q["question"], hyu_db) for q in hyu]
    config = preset_config(run.generation["retrieval_preset"])
    for case_id, ds, question, db in wanted:
        if case_id in cached:
            continue
        trace = await run_rag(question, config, Services(db=db, ollama=run.ollama, settings=run.settings), stop_after=STOP_AFTER, save_trace=False)
        selected = next((s["output"] for s in trace["stages"] if s["stage_id"] == "evidence_selection" and s["status"] == "completed"), [])
        cached[case_id] = {"case_id": case_id, "dataset": ds, "question": question, "evidence": selected, "retrieval_status": trace["status"],
                           "index_id": db.index_id}  # fmt: skip
        append(cache, cached[case_id])
    return [cached[c[0]] for c in wanted]


async def run_generation_task(run: Run, task: Task) -> dict:
    model = task.options["model"]
    installed = {m["name"]: m for m in await run.ollama.list_models()}
    if model not in installed:
        raise LookupError(f"Ollama model '{model}' is not installed. Run: ollama pull {model}")
    identity = await run.ollama.model_identity(installed[model])
    cases = await generation_cases(run)
    params = {**run.generation["generation"], "model": model}
    config = preset_config(task.preset, {"generation": {"params": params}})
    services = Services(db=run.db, ollama=run.ollama, settings=run.settings)
    path = run.raw_file(task)
    done = read_done(path)
    for n, case in enumerate(cases, start=1):
        if case["case_id"] in done:
            continue
        evidence = [Evidence(**e) for e in case["evidence"]]
        rec: dict[str, Any] = {"qid": case["case_id"], "dataset": case["dataset"], "model": model}
        try:
            result = await answer_from_evidence(case["question"], evidence, config, services)
            final, generated, prompt = result["final"], result["generated"], result["prompt"]
            rec.update(status="completed", error=None, answer=final.answer, outcome=final.outcome,
                       raw_answer=generated.answer if generated else None, prompt_labels=[e.label for e in prompt.evidence] if prompt else [],
                       prompt_tokens_estimate=prompt.token_count if prompt else 0, cited=[s.label for s in final.sources if s.cited],
                       usage=generated.usage if generated else {}, context_ms=result["context_ms"], generation_ms=result["generation_ms"],
                       first_token_ms=generated.first_token_ms if generated else None)  # fmt: skip
        except Exception as exc:  # record and continue with the next case
            rec.update(status="failed", error=f"{exc.__class__.__name__}: {exc}")
        append(path, rec)
        print(f"    {task.key}: {n}/{len(cases)} {case['case_id']} → {rec.get('outcome', rec['error'])}", flush=True)
    return {"queries": len(read_done(path)), "model_identity": identity, "config": config}


# --------------------------------------------------------------------------------------------- dry run, manifest, main


def check_task(run: Run, task: Task, installed: set[str] | None) -> tuple[str, str]:
    """Without running: is the configuration valid and is everything it needs available?"""
    if task.status in ("NOT_APPLICABLE", "SHARED"):
        return task.status, task.reason
    try:
        if task.preset and task.preset not in PRESETS_BY_ID:
            return "FAILED", f"unknown preset {task.preset}"
        if task.suite in ("offline", "retrieval"):
            retrieval_config(run, task)  # raises ConfigError when the configuration is invalid
            aux = run.online.get("auxiliary_llm") if task.options.get("llm") else None
            if not beir.is_downloaded(task.dataset):
                return "BLOCKED", f"dataset not downloaded (python -m evaluation.runner --download {task.dataset})"
            if aux and installed is not None and aux not in installed:
                return "BLOCKED", f"auxiliary LLM '{aux}' is not installed (ollama pull {aux})"
        if task.suite == "generation" and installed is not None and task.options["model"] not in installed:
            return "BLOCKED", f"Ollama model '{task.options['model']}' is not installed (ollama pull {task.options['model']})"
        if (task.suite == "generation" or task.options.get("llm")) and installed is None:
            return "BLOCKED", "Ollama is not reachable"
    except ConfigError as exc:
        return "FAILED", f"invalid configuration: {exc}"
    return "READY", ""


def git_info() -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return None
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


async def write_manifest(run: Run, tasks: list[Task]) -> None:
    import importlib.metadata as md

    def version(pkg: str) -> str | None:
        try:
            return md.version(pkg)
        except md.PackageNotFoundError:
            return None

    try:
        ollama_version = (await run.ollama.http.get("/api/version")).json().get("version")
    except Exception:
        ollama_version = None
    try:
        memory = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip())
    except Exception:
        memory = None
    manifest = {
        "run_id": run.run_id, "started_at": datetime.now(UTC).isoformat(), "argv": sys.argv[1:], "git": git_info(),
        "machine": {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(), "memory_bytes": memory},
        "python": sys.version.split()[0], "ollama_version": ollama_version,
        "packages": {p: version(p) for p in ("torch", "sentence-transformers", "transformers", "qdrant-client", "pymongo", "numpy", "pyyaml")},
        "split": run.split, "smoke": run.args.smoke, "max_queries": run.args.max_queries,
        "configs": {"offline": run.offline, "online": run.online, "generation": run.generation},
        "datasets": {ds: json.loads((beir.dataset_dir(ds) / "SOURCE.json").read_text()) for ds in beir.DATASETS if beir.is_downloaded(ds)},
        "tasks": [t.key for t in tasks],
    }  # fmt: skip
    run.dir.mkdir(parents=True, exist_ok=True)
    path = run.dir / "run_manifest.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    manifest["sessions"] = previous.get("sessions", []) + [{"started_at": manifest["started_at"], "argv": manifest["argv"], "git": manifest["git"]}]
    path.write_text(json.dumps(manifest, indent=2, default=str))


async def main_async(args) -> int:
    run = Run(args)
    tasks = build_plan(args, run.offline, run.online, run.generation)
    try:
        installed: set[str] | None = {m["name"] for m in await run.ollama.list_models()}
    except OllamaError:
        installed = None
    health = run.db.check()
    print(f"Run '{run.run_id}' → {run.dir.relative_to(ROOT)}   split={run.split}   smoke={args.smoke}")
    print(f"MongoDB: {'ok' if health['mongodb']['ok'] else 'NOT reachable'} · Qdrant: {'ok' if health['qdrant']['ok'] else 'NOT reachable'}"
          f" · Ollama: {', '.join(sorted(installed)) if installed is not None else 'NOT reachable'}")  # fmt: skip
    for t in tasks:
        status, reason = check_task(run, t, installed)
        if status != "READY":
            t.status, t.reason = status, reason
    if args.dry_run:
        print(f"\n{'TASK':70} STATUS")
        for t in tasks:
            limit = f" (first {t.query_limit} queries)" if t.query_limit else ""
            print(f"{t.key:70} {'READY' if t.status == 'PENDING' else t.status}{limit} {t.reason}")
        print(f"\n{len(tasks)} tasks; nothing was run (dry run).")
        return 0
    if not (health["mongodb"]["ok"] and health["qdrant"]["ok"]):
        print("MongoDB and Qdrant must be running (docker compose up -d).")
        return 1
    await write_manifest(run, tasks)
    for t in tasks:
        previous = run.status.get(t.key, {})
        if t.status in ("NOT_APPLICABLE", "SHARED", "BLOCKED", "FAILED"):
            run.status[t.key] = {"status": t.status, "reason": t.reason}
            run.save_status()
            print(f"[{t.status}] {t.key}: {t.reason}")
            continue
        path = run.raw_file(t)
        if previous.get("status") == "COMPLETED" and not args.force:
            if args.resume:
                print(f"[done] {t.key}")
                continue
        if path.exists() and path.stat().st_size and not (args.resume or args.force):
            print(f"[skip] {t.key}: results exist — use --resume to continue or --force to recompute")
            continue
        if args.force and path.exists():
            path.unlink()
        print(f"[run] {t.key}", flush=True)
        started = time.perf_counter()
        try:
            if t.suite in ("offline", "retrieval"):
                info = await run_retrieval_task(run, t)
            elif t.suite == "fixture":
                info = await run_fixture_task(run, t)
            else:
                info = await run_generation_task(run, t)
            run.status[t.key] = {"status": "COMPLETED", "seconds": round(time.perf_counter() - started, 1), **info}
        except LookupError as exc:
            run.status[t.key] = {"status": "BLOCKED", "reason": str(exc)}
        except Exception as exc:
            run.status[t.key] = {"status": "FAILED", "reason": f"{exc.__class__.__name__}: {exc}"}
        run.save_status()
        print(f"  → {run.status[t.key]['status']} {run.status[t.key].get('reason', '')}", flush=True)
    write_reports(run.dir)
    print(f"\nReports: {(run.dir / 'summary.md').relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="HYU Compass headless benchmark runner")
    parser.add_argument("--suite", choices=["all", "offline", "retrieval", "generation"], default="all")
    parser.add_argument("--dataset", help="comma-separated BEIR datasets (default: all in the config)")
    parser.add_argument("--experiment", help="comma-separated experiment IDs, e.g. B0_BASIC_DENSE_RAG,R2_HYBRID_RRF")
    parser.add_argument("--split", help="dataset split (default: the config's, i.e. test)")
    parser.add_argument("--dry-run", action="store_true", help="validate everything and print the plan; run nothing")
    parser.add_argument("--smoke", action="store_true", help=f"{SMOKE_QUERIES} queries on a small corpus slice, separate indexes and run")
    parser.add_argument("--resume", action="store_true", help="continue tasks of an existing run (skip finished queries)")
    parser.add_argument("--force", action="store_true", help="recompute tasks and rebuild their indexes")
    parser.add_argument("--run-id", help="results folder name under evaluation/results/ (default: main, or smoke)")
    parser.add_argument("--max-queries", type=int, help="limit queries per task (recorded in the run manifest)")
    parser.add_argument("--download", help="download BEIR datasets (comma-separated) and exit")
    args = parser.parse_args()
    if args.download:
        for name in args.download.split(","):
            print(name, beir.download(name))
        return 0
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
