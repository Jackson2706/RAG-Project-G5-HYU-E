"""Deck v4 Task 4: why did A0b (AAES spec-fixed) keep 0 of the 7 dev questions that need a split or a question?

Run from Sources/ (dev only; stops after evidence sufficiency, so no answer is generated):
  python scripts/deck_v4_a0b_diagnosis.py   # -> Report/slides/deck_v4/aaes_plus/a0b_diagnosis.json
For each dev case labelled conditional_answer or clarify: A0's decision, and A0b's step-by-step details (campus
candidate, A0 action after the campus rule, the extraction per evidence set and its answer group, the yes/no check).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402

from app.config import REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.pipeline import run_rag  # noqa: E402
from app.rag.presets import preset_config  # noqa: E402
from app.rag.schemas import Services  # noqa: E402


async def main() -> int:
    settings = get_settings().model_copy(update={"embedding_device": "auto"})
    services = Services(db=Database.connect(settings).for_index(settings.hyu_index_id), ollama=OllamaClient(settings.ollama_base_url, timeout=settings.ollama_timeout),
                        settings=settings)  # fmt: skip
    rows = []
    for case in hyu_suite.load_cases("dev"):
        if case["expected_behavior"] not in ("conditional_answer", "clarify"):
            continue
        row = {"qid": case["case_id"], "expected": case["expected_behavior"], "branch_attributes": case["branch_attributes"]}
        for preset in ("A0_AAES", "A0b_AAES_SPEC_FIXED"):
            config = preset_config(preset)
            trace = await run_rag(hyu_suite.question_for(case, config), config, services, stop_after="evidence_sufficiency", save_trace=False,
                                  history=hyu_suite.history_of(case))  # fmt: skip
            stage = next(s for s in trace["stages"] if s["stage_id"] == "evidence_sufficiency")
            sig = stage["output"]["signals"]
            row[preset] = {"action": sig["action"], "reason": sig["reason"], "branch_attributes": sig.get("branch_attributes"),
                           "support": len(sig.get("support") or []), "details": stage.get("details")}  # fmt: skip
        rows.append(row)
        print(row["qid"], row["expected"], row["A0_AAES"]["action"], "->", row["A0b_AAES_SPEC_FIXED"]["action"], row["A0b_AAES_SPEC_FIXED"]["reason"], flush=True)
    out = REPORT_DIR / "slides" / "deck_v4" / "aaes_plus" / "a0b_diagnosis.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
