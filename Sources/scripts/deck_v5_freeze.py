"""Deck v5 Phase 2 step 7: write Report/slides/deck_v4/aaes_plus_freeze.md before the held-out run.

Run from Sources/ after `python scripts/deck_v5.py ablation …` wrote aaes_plus/selection.json:
  python scripts/deck_v5_freeze.py
Records the commit, the chosen AAES+ version, SHA-256 of every prompt the held-out methods use, the method list,
the order rule and the pre-registered hypotheses. The held-out preset lists in evaluation/configs/hyu.yaml must
already name the seven methods (checked here).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Sources" / "backend"))
sys.path.insert(0, str(ROOT / "Sources"))
import yaml  # noqa: E402

from app.rag import aaes_llm  # noqa: E402
from app.rag.blocks.grounded_generation.context_construction import standard_context  # noqa: E402
from app.rag.blocks.query_processing.query_understanding import self_query  # noqa: E402
from app.rag.presets import preset_config  # noqa: E402
from evaluation import reply_action  # noqa: E402

DECK = ROOT / "Report" / "slides" / "deck_v4"
BASELINES = ["A0_AAES", "AP_BBBB", "B0_BASIC_DENSE_RAG", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL", "G1_ORACLE_CONTEXT"]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    selection = json.loads((DECK / "aaes_plus" / "selection.json").read_text())
    ours = selection["choice"]
    methods = [ours] + [m for m in BASELINES if m != ours]
    hyu = yaml.safe_load((ROOT / "Sources" / "evaluation" / "configs" / "hyu.yaml").read_text())
    assert hyu["heldout_presets"] == methods and hyu["test2_presets"] == methods, "set heldout_presets and test2_presets first"
    for m in methods:
        preset_config(m)  # every method must validate
    prompts = {name: sha(getattr(aaes_llm, name)) for name in ("PROFILE", "APPLIES", "DIFFERS", "SAME", "DECIDE", "ASK", "REFER", "EXTRACT")}
    prompts |= {"self_query.INSTRUCTION": sha(self_query.INSTRUCTION), "standard_context.SYSTEM_PROMPT": sha(standard_context.SYSTEM_PROMPT),
                "evaluator_v2 (reply_action.PROMPT)": sha(reply_action.PROMPT),
                "judge_v3_prompt.md": hashlib.sha256((ROOT / "Sources" / "evaluation" / "judge_v3_prompt.md").read_bytes()).hexdigest()}
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    lines = ["# AAES+ freeze (deck v5, before the held-out run)", "",
             f"Frozen on top of commit `{commit}` (which already holds the held-out preset lists in evaluation/configs/hyu.yaml); "
             "the freeze commit adds only this file, selection.json, dev_ablation.csv and timing_v5.csv. The held-out run "
             "must start from the commit that contains this file.", "",
             f"**AAES+ = `{ours}`**, chosen by the rule fixed before Stage B: {selection['rule']}", "",
             f"Reference (A0_AAES = RRRR) kept {selection['reference']['kept']} needed questions/splits on dev + dev-2; minimum "
             f"for eligibility {selection['minimum_kept']:.1f}. Candidates: `aaes_plus/selection.json`, table "
             "`aaes_plus/dev_ablation.csv`.", "",
             "## Held-out methods (this order, all seven per question)", "",
             *[f"{i}. `{m}`" for i, m in enumerate(methods, 1)], "",
             "## Order rule", "",
             "test-3 (140) first, then test-2 (75) only if at least 2.5 h remain before STOP_AT = 2026-11-21 12:00 KST; "
             "`--case-major` (every method on a question before the next question) and `--stop-at` (checked between "
             "questions); test-2 never started twice; test-1 never run. Qwen 3.5 4B, temperature 0, seed 42, thinking off, "
             "4,096 context, index r5. Reply types: frozen evaluator v2.", "",
             "## Pre-registered hypotheses (Holm-corrected over H1–H3; paired bootstrap 95% CI, 10,000 resamples, seed 0; McNemar)", "",
             f"- H1: `{ours}` > `A0_AAES` on acceptable reply type, all held-out questions run (one-sided).",
             f"- H2: on student-dependent questions that need a question or split, `{ours}` keeps them within 10 points of "
             "`A0_AAES` (non-inferiority: bootstrap 95% lower bound of the difference > −0.10).",
             f"- H3: `{ours}` > `R16_PROMPTED_CONDITIONAL` on acceptable reply type on student-dependent questions (one-sided).",
             "- Secondary (no correction): unneeded-question rate, wrong referrals, seconds per question.",
             "- Only questions with a v2 reply type for every method are analysed (balanced); dropped ones are listed.", "",
             "## Prompt hashes (SHA-256)", "", "| Prompt | SHA-256 |", "|---|---|",
             *[f"| {k} | `{v}` |" for k, v in prompts.items()], ""]  # fmt: skip
    (DECK / "aaes_plus_freeze.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
