"""Merge the test-2 labels (A35 Step 5): agreed cases take annotator A's row, disputed cases the adjudicated row;
EXCLUDE decisions go to excluded_test2.jsonl. Slice and persona come from the selection (selected.jsonl).

Run from Sources/:
  python -m labeling.merge_test2            # -> data/HYU/labels/test2/merged.jsonl, data/HYU/labels/test2/excluded_test2.jsonl
  python -m labeling.merge_test2 --freeze   # -> data/HYU/labels/test2.jsonl + FROZEN_test2.sha256 (after checks and verification)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LABELS = Path(__file__).resolve().parents[1] / "data" / "HYU" / "labels"
T2 = LABELS / "test2"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def merge() -> tuple[list[dict], list[dict]]:
    a = {r["case_id"]: r for r in load(T2 / "annot_A" / "all.jsonl")}
    selected = {r["draft_id"]: r for r in load(T2 / "selected.jsonl")}
    decisions = {d["case_id"]: d for d in load(T2 / "adjudication.jsonl")}
    disputed = set(json.loads((T2 / "disputed_ids.json").read_text()))
    assert disputed == set(decisions), "every disputed case needs exactly one adjudication decision"
    extra = {d["case_id"]: d for d in load(T2 / "verification.jsonl")} if (T2 / "verification.jsonl").exists() else {}
    merged, excluded = [], []
    for cid in sorted(a):
        decision = extra.get(cid) or decisions.get(cid)
        if decision and decision["decision"] == "EXCLUDE":
            excluded.append({"case_id": cid, "reason": decision.get("reason", ""), "rule": decision.get("rule", "")})
            continue
        row = dict(decision["row"]) if decision else dict(a[cid])
        origin = "agent_edited" if decision else "agent_draft"
        merged.append({**row, "slice": selected[cid]["slice"], "persona_id": selected[cid]["persona_id"], "origin": origin, "split": "test2"})
    return merged, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        merged = (T2 / "merged.jsonl").read_bytes()
        (LABELS / "test2.jsonl").write_bytes(merged)
        (LABELS / "FROZEN_test2.sha256").write_text(f"{hashlib.sha256(merged).hexdigest()}  test2.jsonl\n", encoding="utf-8")
        print(f"frozen {len(merged.splitlines())} cases -> test2.jsonl, FROZEN_test2.sha256")
        return 0
    merged, excluded = merge()
    write(T2 / "merged.jsonl", merged)
    write(T2 / "excluded_test2.jsonl", excluded)
    print(f"merged {len(merged)}, excluded {len(excluded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
