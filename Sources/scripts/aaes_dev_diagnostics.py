"""A0's step-4 decisions on the DEV split, with the reasons the saved raw records do not keep (amendment A34, exploratory).

Run from Sources/ (MongoDB, Qdrant and the r5 index; no LLM, it stops after evidence sufficiency):
  python scripts/aaes_dev_diagnostics.py            # -> Report/results/dev-02/a0_decisions_dev.jsonl + printed counts

Dev only: AGENTS.md forbids opening test.jsonl, and A34 forbids system re-runs on test. The decision is
deterministic (rule profile, retrieval, decide()), so its action is checked against the dev-02 A0 record.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import RESULTS_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.pipeline import run_rag  # noqa: E402
from app.rag.presets import preset_config  # noqa: E402
from app.rag.schemas import Services  # noqa: E402

PRESET = "A0_AAES"


async def main() -> int:
    settings = get_settings().model_copy(update={"embedding_device": "auto"})
    db = Database.connect(settings).for_index(settings.hyu_index_id)
    services = Services(db=db, ollama=OllamaClient(settings.ollama_base_url, timeout=settings.ollama_timeout), settings=settings)
    config = preset_config(PRESET)
    saved = {r["qid"]: r for r in load_jsonl(RESULTS_DIR / "dev-02" / "raw" / "hyu" / "dev" / f"{PRESET}__-.jsonl") if r["status"] == "completed"}
    out_path = RESULTS_DIR / "dev-02" / "a0_decisions_dev.jsonl"
    rows = []
    for case in hyu_suite.load_cases("dev"):
        trace = await run_rag(hyu_suite.question_for(case, config), config, services, stop_after="evidence_sufficiency", save_trace=False,
                              history=hyu_suite.history_of(case))  # fmt: skip
        stage = next(s for s in trace["stages"] if s["stage_id"] == "evidence_sufficiency")
        d = stage["output"]["signals"]
        campus_rows = [r for r in d.get("branch_table", []) if "campus" in r["when"]]
        rows.append({"qid": case["case_id"], "expected": case["expected_behavior"], "action": d["action"], "reason": d["reason"],
                     "saved_action": saved.get(case["case_id"], {}).get("action"), "clarify_attribute": d.get("clarify_attribute"),
                     "branch_attributes": d.get("branch_attributes"), "branches": len(d.get("branch_table", [])),
                     "campus_branch_without_evidence": "campus" in (d.get("branch_attributes") or []) and any(not r["evidence"] for r in campus_rows)})  # fmt: skip
    out_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} dev cases -> {out_path}")
    print("actions match dev-02:", sum(r["action"] == r["saved_action"] for r in rows), "/", len(rows))
    print("action x reason:", Counter((r["action"], r["reason"]) for r in rows))
    print("clarify attribute:", Counter(r["clarify_attribute"] for r in rows if r["action"] == "CLARIFY"))
    print("campus branch with one side empty:", Counter(r["action"] for r in rows if r["campus_branch_without_evidence"]))
    print("CLARIFY on abstain-labelled:", sum(r["action"] == "CLARIFY" and r["expected"] == "abstain" for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
