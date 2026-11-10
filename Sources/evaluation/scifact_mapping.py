"""Check whether BEIR SciFact queries map to labeled original SciFact claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import RESULTS_DIR
from evaluation import beir, scifact_original

LABELS = ("SUPPORT", "CONTRADICT", "NEI", "MIXED")
QREL_RELATIONS = ("equal", "superset", "subset", "other")
DOWNLOAD_COMMAND = "python -m evaluation.runner --download scifact,scifact_original"


def _source_md5(folder: Path) -> str:
    source_file = folder / "SOURCE.json"
    if not source_file.exists():
        raise FileNotFoundError(f"Missing dataset provenance file: {source_file}")
    md5 = json.loads(source_file.read_text(encoding="utf-8")).get("md5")
    if not md5:
        raise ValueError(f"Dataset provenance has no MD5: {source_file}")
    return str(md5)


def _normalized_text(text: str) -> str:
    return " ".join(text.strip().split())


def build_report(beir_split: str = "test", orig_split: str = "dev") -> dict:
    """Compare BEIR query IDs, texts, and qrels with original SciFact claims."""
    _corpus, queries, qrels = beir.load("scifact", beir_split)
    claims = scifact_original.load_claims(orig_split)
    claims_by_id = {str(claim["id"]): claim for claim in claims}

    matched_orig_ids = set()
    unmatched_ids = []
    text_mismatch_examples = []
    n_text_equal = 0
    label_counts = dict.fromkeys(LABELS, 0)
    qrels_vs_evidence = dict.fromkeys(QREL_RELATIONS, 0)
    n_nei_with_qrels = 0
    n_qrels_equal_cited = 0

    for beir_id, beir_text in queries.items():
        try:
            orig_id = str(int(beir_id))
        except ValueError:
            orig_id = ""
        claim = claims_by_id.get(orig_id)
        if claim is None:
            if len(unmatched_ids) < 20:
                unmatched_ids.append(beir_id)
            continue

        matched_orig_ids.add(orig_id)
        label_counts[claim["label"]] += 1
        if _normalized_text(beir_text) == _normalized_text(claim["claim"]):
            n_text_equal += 1
        elif len(text_mismatch_examples) < 5:
            text_mismatch_examples.append({"id": beir_id, "beir": beir_text, "orig": claim["claim"]})

        qrel_docs = set(qrels.get(beir_id, {}))
        evidence_docs = set(claim["evidence"])
        if qrel_docs == evidence_docs:
            relation = "equal"
        elif qrel_docs > evidence_docs:
            relation = "superset"
        elif qrel_docs < evidence_docs:
            relation = "subset"
        else:
            relation = "other"
        qrels_vs_evidence[relation] += 1

        if claim["label"] == "NEI" and qrel_docs:
            n_nei_with_qrels += 1
        if qrel_docs == set(claim["cited_doc_ids"]):
            n_qrels_equal_cited += 1

    missing_claims = [claim for claim_id, claim in claims_by_id.items() if claim_id not in matched_orig_ids]
    missing_by_label = dict.fromkeys(LABELS, 0)
    for claim in missing_claims:
        missing_by_label[claim["label"]] += 1

    return {
        "beir_split": beir_split,
        "orig_split": orig_split,
        "source_checksums": {
            "beir_md5": _source_md5(beir.dataset_dir("scifact")),
            "scifact_original_md5": _source_md5(scifact_original.FOLDER),
        },
        "n_beir_queries": len(queries),
        "n_orig_claims": len(claims),
        "n_id_matched": sum(label_counts.values()),
        "unmatched_ids": unmatched_ids,
        "n_text_equal": n_text_equal,
        "text_mismatch_examples": text_mismatch_examples,
        "label_counts": label_counts,
        "qrels_vs_evidence": qrels_vs_evidence,
        "n_nei_with_qrels": n_nei_with_qrels,
        "n_qrels_equal_cited": n_qrels_equal_cited,
        "orig_claims_missing_from_beir": len(missing_claims),
        "orig_claims_missing_from_beir_by_label": missing_by_label,
    }


def _table(rows: list[tuple[str, object]]) -> str:
    return "\n".join(["| Metric | Count |", "|---|---:|", *(f"| {name} | {value} |" for name, value in rows)])


def summary_markdown(report: dict) -> str:
    """Render the small table printed by the CLI."""
    return _table([
        ("BEIR queries", report["n_beir_queries"]),
        ("Original claims", report["n_orig_claims"]),
        ("ID matched", report["n_id_matched"]),
        ("Text equal", report["n_text_equal"]),
        ("Qrels equal evidence", report["qrels_vs_evidence"]["equal"]),
        ("Qrels equal cited docs", report["n_qrels_equal_cited"]),
        ("Original claims missing from BEIR", report["orig_claims_missing_from_beir"]),
    ])


def _markdown_cell(value: str) -> str:
    return _normalized_text(value).replace("|", "\\|")


def render_markdown(report: dict) -> str:
    """Render the complete human-readable mapping report."""
    unmatched = ", ".join(f"`{item}`" for item in report["unmatched_ids"]) or "None"
    lines = [
        "# SciFact mapping report",
        "",
        f"- BEIR split: `{report['beir_split']}`",
        f"- Original SciFact split: `{report['orig_split']}`",
        f"- BEIR SOURCE MD5: `{report['source_checksums']['beir_md5']}`",
        f"- Original SciFact SOURCE MD5: `{report['source_checksums']['scifact_original_md5']}`",
        "",
        "## Mapping summary",
        "",
        summary_markdown(report),
        "",
        f"Unmatched BEIR IDs (first 20): {unmatched}",
        "",
        "## Matched claim labels",
        "",
        _table([(label, report["label_counts"][label]) for label in LABELS]),
        "",
        "## Qrels comparison",
        "",
        _table([
            (f"Qrels vs evidence: {relation}", report["qrels_vs_evidence"][relation])
            for relation in QREL_RELATIONS
        ] + [
            ("NEI claims with qrels", report["n_nei_with_qrels"]),
            ("Qrels equal cited docs", report["n_qrels_equal_cited"]),
        ]),
        "",
        "## Original claims missing from BEIR",
        "",
        _table([
            ("Total", report["orig_claims_missing_from_beir"]),
            *((label, report["orig_claims_missing_from_beir_by_label"][label]) for label in LABELS),
        ]),
    ]
    if report["text_mismatch_examples"]:
        lines.extend([
            "",
            "## Text mismatch examples",
            "",
            "| ID | BEIR | Original |",
            "|---|---|---|",
            *(f"| `{item['id']}` | {_markdown_cell(item['beir'])} | {_markdown_cell(item['orig'])} |"
              for item in report["text_mismatch_examples"]),
        ])
    return "\n".join(lines) + "\n"


def write_report(report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "mapping.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "mapping.md").write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map BEIR SciFact queries to original SciFact claims")
    parser.add_argument("--beir-split", default="test", choices=("train", "test"))
    parser.add_argument("--orig-split", default="dev", choices=("train", "dev"))
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "scifact_mapping")
    args = parser.parse_args(argv)

    try:
        report = build_report(args.beir_split, args.orig_split)
    except FileNotFoundError as error:
        parser.error(f"{error}. Download the datasets first: {DOWNLOAD_COMMAND}")
    write_report(report, args.out)
    print(summary_markdown(report))
    print(f"\nWrote {args.out / 'mapping.json'} and {args.out / 'mapping.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
