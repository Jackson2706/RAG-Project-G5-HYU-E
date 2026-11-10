"""Failure categories per query: the EARLIEST observable faulty stage, plus secondary labels.

Only what the saved results can show is labelled. Document qrels tell us whether a relevant document
was retrieved or selected; they cannot show that an answer is wrong or a claim unsupported — those
categories need annotated cases and are otherwise never assigned.
"""

from __future__ import annotations

CATEGORIES = {
    "service_failure": "Service/model execution failure",
    "index_inconsistency": "Index/provenance inconsistency",
    "rewrite_drift": "Query rewrite semantic drift",
    "not_retrieved": "Relevant source not retrieved",
    "eligible_excluded": "Eligible source excluded by a filter",
    "candidate_starvation": "Candidate starvation after Postfiltering",
    "ranked_too_low": "Relevant source ranked too low",
    "dropped_by_selection": "Relevant source retrieved but dropped by Evidence Selection",
    "wrong_answer_correct_context": "Correct context but incorrect generated answer",
    "unsupported_claim": "Unsupported factual claim",
    "invalid_citation": "Invalid or unsupported citation",
    "wrong_gate_decision": "Incorrect proceed/abstain decision",
}
ORDER = list(CATEGORIES)  # pipeline order: earlier = more upstream
TOP = 10  # "ranked too low" = the first relevant document is below this rank


def classify_retrieval(record: dict, relevant: set[str], baseline: dict | None = None, baseline_relevant_found: bool | None = None) -> list[str]:
    """Labels for one retrieval record (ranking of original document IDs), earliest first. [] = no failure."""
    labels: list[str] = []
    error = (record.get("error") or "").lower()
    if record.get("status") != "completed":
        labels.append("index_inconsistency" if "missing in mongodb" in error or "dimensional" in error else "service_failure")
        return labels
    if not relevant:
        return labels  # no judged relevant document: nothing to diagnose
    ranking = [d for d in record.get("ranking", []) if d != record.get("qid")]
    first = next((i for i, d in enumerate(ranking, start=1) if d in relevant), None)
    rewrite = record.get("rewrite") or {}
    rewritten = rewrite.get("validation", {}).get("used") == "rewrite" or bool(rewrite.get("alternatives")) or bool(rewrite.get("embedding_text"))
    if rewritten and baseline is not None and baseline_relevant_found and first is None:
        labels.append("rewrite_drift")  # B0 found a relevant document for this query; the rewritten search did not
    if first is None:
        labels.append("not_retrieved")
    elif first > TOP:
        labels.append("ranked_too_low")
    selected = set(record.get("selected", []))
    if first is not None and record.get("selected_units") and not selected & relevant:
        labels.append("dropped_by_selection")
    return sorted(set(labels), key=ORDER.index)


def classify_fixture(record: dict) -> list[str]:
    """Labels for a prefilter/postfilter fixture case."""
    if record.get("status") != "completed":
        return ["service_failure"]
    labels = []
    post = (record.get("stage_status") or {}).get("metadata_postfiltering") == "completed"
    returned, target = record.get("ranking", []), set(record.get("target", []))
    if post and record.get("units_ranked", 0) < record.get("cutoff", 0):
        labels.append("candidate_starvation")
    if target and not target & set(returned):
        labels.append("not_retrieved")
    return sorted(set(labels), key=ORDER.index)


def classify_generation(record: dict, marker: dict) -> list[str]:
    """Generation-stage labels that are measurable without annotations."""
    if record.get("status") != "completed":
        return ["service_failure"]
    return ["invalid_citation"] if marker.get("invalid_markers") else []
