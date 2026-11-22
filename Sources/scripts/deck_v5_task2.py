"""Deck v5 Phase 4: Task 2 content numbers from the merged GPT-6 Sol judgments (v3 prompt). Saved data only.

Run from Sources/ after `python scripts/deck_v4_followup.py merge`:
  python scripts/deck_v5_task2.py    # -> Report/slides/deck_v4/followup/content_v5.{csv,json}

Per system, over its answered replies (answer / conditional_answer): facts covered = correct / required facts,
wrong fact = wrong / required facts, wrong group = share of replies judged wrong_group. Turns = mean user turns.
Paired: AAES two-turn final reply (reply_only, reply_reask) minus each baseline, per persona (pid), on facts covered
of the persona's reply (an unanswered reply counts 0 facts covered), bootstrap 95% CI (10,000 resamples, seed 0).
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import REPORT_DIR  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v4" / "followup"
LABEL = "judged by GPT-6 Sol (v3 prompt)"
AAES = ("A0 reply_only", "A0 reply_reask")


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def covered(j: dict | None) -> float:
    facts = (j or {}).get("facts") or []
    return sum(f == "correct" for f in facts) / len(facts) if facts else 0.0


def bootstrap(diffs: list[float], n: int = 10_000) -> tuple[float, float]:
    rng = random.Random(0)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return round(means[int(0.025 * n)], 3), round(means[int(0.975 * n) - 1], 3)


def main() -> int:
    judgments = {j["id"]: j for j in load(OUT / "judge" / "judgments.jsonl")}
    items = {i["id"]: i for i in load(OUT / "judge" / "items.jsonl")}
    key = load(OUT / "judge" / "key.jsonl")
    by_system: dict[str, list[dict]] = {}
    for k in key:
        by_system.setdefault(k["system"], []).append({**k, "type": items[k["id"]]["reply_type"], "j": judgments[k["id"]]})
    rows = []
    for system, recs in sorted(by_system.items()):
        answered = [r for r in recs if r["type"] in ("answer", "conditional_answer")]
        facts = [f for r in answered for f in r["j"]["facts"] or []]
        rows.append({"system": system, "replies": len(recs), "answered": len(answered),
                     "facts_covered": round(sum(f == "correct" for f in facts) / len(facts), 3) if facts else None,
                     "wrong_fact": round(sum(f == "wrong" for f in facts) / len(facts), 3) if facts else None,
                     "wrong_group": round(statistics.fmean(bool(r["j"]["wrong_group"]) for r in answered), 3) if answered else None,
                     "turns_mean": round(statistics.fmean(r["user_turns"] for r in recs), 2)})  # fmt: skip
    paired = []
    for ours in AAES:
        mine = {r["pid"]: r for r in by_system.get(ours, [])}
        for system, recs in sorted(by_system.items()):
            if system.startswith("A0"):
                continue
            theirs = {r["pid"]: r for r in recs}
            common = sorted(set(mine) & set(theirs))
            diffs = [covered(mine[p]["j"]) - covered(theirs[p]["j"]) for p in common]
            if diffs:
                paired.append({"ours": ours, "baseline": system, "personas": len(common), "diff_facts_covered": round(statistics.fmean(diffs), 3),
                               "ci95": bootstrap(diffs), "better": sum(d > 0 for d in diffs), "worse": sum(d < 0 for d in diffs)})  # fmt: skip
    with (OUT / "content_v5.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    meta = json.loads((OUT / "judge" / "judgments.meta.json").read_text())
    (OUT / "content_v5.json").write_text(json.dumps({"label": LABEL, "judge": meta, "systems": rows, "paired": paired}, indent=1) + "\n")
    print(json.dumps({"systems": rows, "paired": paired}, indent=1))
    return 0


if __name__ == "__main__":
    assert covered({"facts": ["correct", "missing"]}) == 0.5 and covered(None) == 0.0
    raise SystemExit(main())
