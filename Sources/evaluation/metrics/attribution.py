"""Attribution and grounding metrics (Lesson 6, slide "Citation metrics need a consistent counting unit").

Two different things:
- MARKER VALIDITY (measurable from the run alone): does each [E#] marker in the answer point to an
  evidence block that was really in the prompt? attach_sources() removes invalid markers at runtime;
  here we count them from the raw model output.
- SEMANTIC GROUNDING (needs human or judge labels per claim): is each material claim supported by the
  evidence, and does its citation support it? Without claim annotations these are NOT_APPLICABLE.
"""

from __future__ import annotations

import re


def marker_validity(raw_answer: str, prompt_labels: list[str]) -> dict:
    """Counts of [E#] markers in the raw answer that resolve / do not resolve to a prompt evidence block."""
    markers = re.findall(r"\[(E\d+)\]", raw_answer)
    valid = [m for m in markers if m in set(prompt_labels)]
    return {"markers": len(markers), "valid_markers": len(valid), "invalid_markers": len(markers) - len(valid),
            "marker_validity": len(valid) / len(markers) if markers else None,
            "cites_any_source": bool(valid), "distinct_sources_cited": len(set(valid))}  # fmt: skip


def claim_metrics(claims: list[dict]) -> dict:
    """claims: one annotation per MATERIAL claim:
        {"supported": bool,          # the supplied evidence supports the claim
         "cited": bool,              # the claim carries at least one citation
         "citation_supports": bool}  # the cited source(s) support the claim

    grounding support  = supported claims / all claims
    citation precision = cited claims whose citation supports them / cited claims
    citation coverage  = claims with a supporting citation / all claims
    """
    n = len(claims)
    cited = [c for c in claims if c["cited"]]
    supporting = sum(c["cited"] and c["citation_supports"] for c in claims)
    return {"claims": n, "grounding_support": sum(c["supported"] for c in claims) / n if n else None,
            "citation_precision": supporting / len(cited) if cited else None,
            "citation_coverage": supporting / n if n else None}  # fmt: skip


def reference_coverage(required_facts_covered: list[bool]) -> float | None:
    """Required reference facts covered correctly / all required facts (needs a human judgment per fact)."""
    return sum(required_facts_covered) / len(required_facts_covered) if required_facts_covered else None
