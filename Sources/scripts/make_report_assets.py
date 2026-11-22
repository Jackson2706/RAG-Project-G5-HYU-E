"""Report figures and tables from one evaluation run (P10 T33). Written by Claude Code.

Run from Sources/:
  python scripts/make_report_assets.py test-final          # -> Report/tables/test-final_*.{csv,md}, Report/figures/test-final_*.{png,svg}
  python scripts/make_report_assets.py dev-02
  python scripts/make_report_assets.py test-final v2   # evaluator v2 tables -> Report/tables/test-final_v2_*, figures likewise

Reads only the run's summary CSVs (hyu_<split>_slices.csv, _comparisons_paired.csv, _actions_confusion.csv), never
labels. Every table and figure names its source file, so each number in the report traces to Report/results/.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import REPORT_DIR, RESULTS_DIR  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MAIN = ["cases", "answered_rate", "action_accuracy", "acceptable_rate", "macro_f1", "unnecessary_clarification_rate",
        "applicable_recall@5", "intrusion@5", "aer", "outdated", "unknown_caveat_rate", "p50_ms", "llm_calls"]
ORDER = ["B0", "R5", "R9S", "R15", "R16", "G0", "G1", "A0", "A1", "A2", "A3", "A4", "A6"]
ACTIONS = ["answer", "conditional_answer", "clarify", "abstain"]


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None  # "N/A"


def short(preset: str) -> str:
    return preset.split("_")[0]


def write_table(name: str, cols: list[str], rows: list[dict], source: Path, out: Path) -> None:
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    lines = [f"Source: `{source.relative_to(REPORT_DIR.parent)}`", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save(fig, name: str, source: Path, out: Path) -> None:
    fig.text(0.01, 0.01, f"Source: {source.relative_to(REPORT_DIR.parent)}", fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}", dpi=200)
    plt.close(fig)


def main(run_id: str, evaluator: str = "v1") -> int:
    run = RESULTS_DIR / run_id
    tag = "" if evaluator == "v1" else f"_{evaluator}"
    split = next(p for p in run.glob("hyu_*_slices.csv") if "_v2_" not in p.name).name.split("_")[1]
    slices_path = run / f"hyu_{split}{tag}_slices.csv"
    paired_path, confusion_path = run / f"hyu_{split}{tag}_comparisons_paired.csv", run / f"hyu_{split}{tag}_actions_confusion.csv"
    run_id = run_id + tag  # output names: test-final_v2_main.md, ...
    tables, figures = REPORT_DIR / "tables", REPORT_DIR / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    slices = read(slices_path)
    overall = sorted((r for r in slices if r["slice"] == "all"), key=lambda r: ORDER.index(short(r["preset"])) if short(r["preset"]) in ORDER else 99)
    write_table(f"{run_id}_main", ["preset", *MAIN], overall, slices_path, tables)
    per_slice = [r for r in slices if r["slice"] != "all"]
    write_table(f"{run_id}_slices", ["preset", "slice", *MAIN], per_slice, slices_path, tables)
    write_table(f"{run_id}_comparisons", ["comparison", "metric", "diff", "ci_low", "ci_high", "p", "p_holm", "cases", "status"],
                read(paired_path), paired_path, tables)  # fmt: skip

    # Figure 1: action quality and AER per preset.
    metrics = [("acceptable_rate", "acceptable action"), ("macro_f1", "action macro-F1"),
               ("unnecessary_clarification_rate", "unnecessary clarification"), ("aer", "AER")]
    fig, ax = plt.subplots(figsize=(10, 4))
    width = 0.8 / len(metrics)
    for i, (metric, label) in enumerate(metrics):
        values = [num(r[metric]) for r in overall]
        xs = [j + i * width for j, v in enumerate(values) if v is not None]
        ax.bar(xs, [v for v in values if v is not None], width, label=label)
    ax.set_xticks([j + 0.4 - width / 2 for j in range(len(overall))], [short(r["preset"]) for r in overall])
    ax.set_ylim(0, 1)
    ax.set_title(f"HYU {split}: action quality and applicability error per method (LLM-annotated labels)")
    ax.legend(fontsize=8, ncol=4)
    save(fig, f"{run_id}_actions", slices_path, figures)

    # Figure 2: acceptable-action rate per slice for AAES, the ablation A4, and the baselines R5 / R16 / B0.
    shown = [p for p in ("A0", "A4", "B0", "R5", "R16") if any(short(r["preset"]) == p for r in per_slice)]
    names = sorted({r["slice"] for r in per_slice})
    fig, ax = plt.subplots(figsize=(10, 4))
    width = 0.8 / max(1, len(shown))
    for i, preset in enumerate(shown):
        rows = {r["slice"]: num(r["acceptable_rate"]) for r in per_slice if short(r["preset"]) == preset}
        ax.bar([j + i * width for j in range(len(names))], [rows.get(s) or 0 for s in names], width, label=preset)
    ax.set_xticks([j + 0.4 - width / 2 for j in range(len(names))], names)
    ax.set_ylim(0, 1)
    ax.set_ylabel("acceptable-action rate")
    ax.set_title(f"HYU {split}: acceptable-action rate per slice")
    ax.legend(fontsize=8, ncol=len(shown))
    save(fig, f"{run_id}_slices", slices_path, figures)

    # Figure 3: A0 confusion matrix (expected rows, predicted columns), all slices.
    rows = {r["expected"]: r for r in read(confusion_path) if short(r["preset"]) == "A0" and r["slice"] == "all"}
    grid = [[int(rows[e][p]) if e in rows else 0 for p in ACTIONS] for e in ACTIONS]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(grid, cmap="Blues")
    for i, row in enumerate(grid):
        for j, value in enumerate(row):
            ax.text(j, i, value, ha="center", va="center", color="black" if value < max(map(max, grid)) * 0.6 else "white")
    ax.set_xticks(range(4), ["answer", "cond.", "clarify", "abstain"])
    ax.set_yticks(range(4), ["answer", "cond.", "clarify", "abstain"])
    ax.set_xlabel("A0 predicted")
    ax.set_ylabel("expected (label)")
    ax.set_title(f"A0 (AAES) actions, HYU {split}")
    save(fig, f"{run_id}_a0_confusion", confusion_path, figures)
    print(f"tables -> {tables}, figures -> {figures} ({run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test-final", sys.argv[2] if len(sys.argv) > 2 else "v1"))
