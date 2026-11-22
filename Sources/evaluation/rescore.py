"""Re-score a finished HYU run with evaluator v2 (amendment A34). No system re-run: it reads only the saved replies.

Run from Sources/ (Ollama with qwen3.5:4b must be running):
  python -m evaluation.rescore --run-id dev-02
  python -m evaluation.rescore --run-id test-final

Writes, next to the v1 tables (which stay unchanged):
  reply_actions_v2.jsonl                      one label per (preset, qid): label, rule or llm, prompt hash
  hyu_<split>_v2_{slices,per_case,actions_confusion,comparisons_paired}.csv
  summary_v2.md                               the v2 table and the pre-registered comparisons under v2
The labels are read by the evaluation code (hyu_suite.load_cases), never opened by an agent.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from evaluation import reply_action
from evaluation.hyu_suite import write_hyu_reports
from evaluation.reports import write_csv

from app.config import RESULTS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--classify-only", action="store_true", help="write reply_actions_v2.jsonl and stop")
    args = parser.parse_args()
    run_dir = RESULTS_DIR / args.run_id
    cache = run_dir / "reply_actions_v2.jsonl"
    behaviors = {split_dir.name: reply_action.classify_folder(split_dir, cache) for split_dir in sorted((run_dir / "raw" / "hyu").glob("*"))}
    if args.classify_only:
        return 0
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    section = write_hyu_reports(run_dir, manifest, write_csv, behaviors=behaviors, tag="_v2")
    header = [f"# {args.run_id}: re-scored with evaluator v2", "",
              f"Evaluator v2 = `evaluation/reply_action.py` (rules + {reply_action.MODEL['model']}, temperature 0, seed 42, "
              f"prompt hash `{reply_action.PROMPT_HASH}`), {datetime.now(UTC).isoformat(timespec='seconds')}. "
              "Same saved replies as the v1 tables (`summary.md`); no system re-run.", ""]  # fmt: skip
    (run_dir / "summary_v2.md").write_text("\n".join(header) + section + "\n", encoding="utf-8")
    print(f"wrote {run_dir}/summary_v2.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
