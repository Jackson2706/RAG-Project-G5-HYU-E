"""Deck v3 Part 2c: readable walk-through of the saved A0 traces (trace_S1.json, trace_S2_S6.json) -> deck_v3/trace_online.md.

Run from Sources/:  python scripts/deck_v3_trace_md.py
Label names for slides: compatible = applies, conflicting = conflicts, open = depends, unconditioned = applies to all,
unknown = tag status unknown (Sources/backend/app/rag/aaes.py label_chunk).
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "Report" / "slides" / "deck_v3"
NAMES = {"compatible": "applies", "conflicting": "conflicts", "open": "depends", "unconditioned": "applies to all", "unknown": "unknown status"}


def tags(cond: dict) -> str:
    parts = [f"campus={'/'.join(cond.get('campus') or [])}", f"scope={cond.get('scope')}"]
    parts += [f"{a}={'/'.join(v)}" for a, v in (cond.get("constraints") or {}).items()]
    parts += ["any_of=" + " OR ".join("+".join(f"{a}={'/'.join(v)}" for a, v in g.items()) for g in cond["any_of"])] if cond.get("any_of") else []
    return "; ".join(parts)


def walk(name: str, t: dict) -> list[str]:
    st = {s["stage_id"]: s for s in t["stages"]}
    out = [f"## {name}", "", f"Question: \"{t['question']}\"" + (f" (earlier turns: {t['history']})" if t.get("history") else ""), ""]
    prof = st["query_understanding"]["output"]["profile"]
    out += ["**Step 1 profile** (rules):", ""] + [f"- {a}: {e['status']}" + (f" = {', '.join(e['values'])}" if e["values"] else "") + (f" (from \"{e['evidence']}\")" if e.get("evidence") else "")
                                                for a, e in prof.items()] + [""]  # fmt: skip
    fused = st["hybrid_fusion"]["output"]["candidates"]
    rer = st["reranking"]["output"]
    labels = st["reranking"]["details"]["labels"]
    by_id = {e["chunk_id"]: e for e in rer}
    out += [f"**Retrieval**: dense top 10 + BM25 top 10, RRF fused to {len(fused)} candidates ({len(rer)} after enrichment):", "",
            "| RRF rank | Title | Section | dense | BM25 | RRF | cross-encoder | label | tags | after penalty | reranked rank |", "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    rank_after = {e["chunk_id"]: i for i, e in enumerate(rer, 1)}
    for c in fused:
        e = by_id.get(c["chunk_id"])
        if not e:
            out.append(f"| {c['rank']} | (not enriched) | | {c['scores'].get('dense', '')} | {c['scores'].get('bm25', '')} | {c['scores'].get('rrf', '')} | | | | | |")
            continue
        s = e["scores"]
        out.append(f"| {c['rank']} | {e['title'][:40]} | {(e.get('section') or '')[:35]} | {s.get('dense', '')} | {s.get('bm25', '')} | {s.get('rrf', '')} | "
                   f"{round(s.get('cross_encoder', 0), 2)} | {NAMES.get(labels.get(e['chunk_id']), labels.get(e['chunk_id']))} | {tags((e.get('applicability') or {}).get('condition') or {})} | "
                   f"{round(s.get('applicability', 0), 2)} | {rank_after[e['chunk_id']]} |")  # fmt: skip
    sel = st["evidence_selection"]["output"]
    d = st["evidence_sufficiency"]["output"]
    sig = d["signals"]
    out += ["", "**Top-3 evidence and coverage** (relevant if query-word coverage ≥ 0.30):", ""]
    out += [f"- {e['title'][:60]} ({e['source_uri']}): coverage {sig['coverage'].get(e['chunk_id'])}" for e in sel]
    out += ["", f"**Branches** (information score per detail, over the relevant chunks: {', '.join(sig['support']) or 'none'}):", ""]
    out += [f"- {a}: information {b['ig']}; chunks that apply per value: " + "; ".join(f"{v} → {len(ids)}" for v, ids in b["outcomes"].items()) for a, b in sig["branches"].items()] or ["- none"]
    out += ["", "**Branch table** (detail → value → passages):", ""] + [f"- {r['when']} → {r['evidence'] or 'no passage'}" for r in sig["branch_table"]] or ["- none"]
    out += ["", f"**Decision**: {d['action']} (reason: {sig['reason']}; clarify detail: {sig.get('clarify_attribute')})", ""]
    if d.get("prompt_note"):
        out += ["**Branch note added to the prompt**:", "", "```", d["prompt_note"], "```", ""]
    if "context_construction" in st and st["context_construction"]["status"] == "completed":
        sysmsg = st["context_construction"]["output"]["messages"][0]["content"]
        out += [f"**Prompt** ({st['context_construction']['output']['token_count']} tokens; system message trimmed):", "", "```", sysmsg[:600] + " …", "```", ""]
    else:
        out += ["**Reply source**: fixed template, no LLM call.", ""]
    out += ["**Final reply**:", "", "> " + (t.get("answer") or "").replace("\n", "\n> "), ""]
    return out


def main() -> int:
    s1 = json.load(open(OUT / "trace_S1.json"))
    both = json.load(open(OUT / "trace_S2_S6.json"))
    lines = ["# Online traces of AAES (A0) on the demo questions", "",
             "From the backend traces behind the Execution tab (`trace_S1.json`, `trace_S2_S6.json`, index r5, run 2026-11-16). "
             "Labels: applies / conflicts / depends / applies to all / unknown status.", ""]  # fmt: skip
    lines += walk("S1: one question", s1) + walk("S2: the counseling question, no profile", both["S2_no_history"]) + walk("S6: the same question after \"I'm a Seoul campus student.\"", both["S6_with_history"])
    (OUT / "trace_online.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote trace_online.md", len(lines), "lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
