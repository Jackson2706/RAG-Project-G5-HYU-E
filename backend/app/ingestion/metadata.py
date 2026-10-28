"""Deterministic metadata extraction.

Two implemented methods:

* ``declared`` — only values the source states explicitly (Markdown front matter,
  HTML <meta> tags, PDF document info). Nothing is inferred.
* ``rule_based`` — declared values plus transparent keyword rules (topics, campus
  mentions, academic-year patterns). Every inferred value is marked ``rule`` in
  ``metadata_provenance`` so it is never confused with declared metadata.

Unknown values stay ``None`` / empty. An LLM extractor is registered as planned.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Controlled vocabularies shared by ingestion, query understanding and filtering.
CAMPUSES = {"SEOUL": "Seoul", "ERICA": "ERICA", "ALL": "University-wide"}
AUDIENCES = {
    "undergraduate": "Undergraduate",
    "graduate": "Graduate",
    "international": "International students",
    "exchange": "Exchange students",
    "freshman": "New / first-year students",
    "all": "All students",
}
# A student in the key group also belongs to the listed broader groups, so documents written
# for a broader group apply to them (e.g. a rule for undergraduates applies to freshmen).
AUDIENCE_PARENTS = {"freshman": ["undergraduate"]}
DOCUMENT_TYPES = {
    "student_guide": "Student guide",
    "regulation": "Regulation",
    "notice": "Notice",
    "faq": "FAQ",
    "form": "Form / application",
    "handbook": "Handbook",
}
TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "orientation": ("orientation", "welcome week", "freshman week"),
    "course_registration": ("course registration", "register for courses", "add/drop", "sugang"),
    "scholarship": ("scholarship", "tuition waiver", "financial aid"),
    "tuition": ("tuition", "payment of fees", "fee payment"),
    "housing": ("dormitory", "residence hall", "housing"),
    "visa": ("visa", "immigration", "alien registration", "residence card"),
    "student_services": ("student service", "student support", "counseling", "career center", "health center"),
    "academic_calendar": ("academic calendar", "semester begins", "final exam"),
    "graduation": ("graduation", "degree requirement", "credits required"),
    "leave_of_absence": ("leave of absence", "return to school", "readmission"),
}
CAMPUS_RULES = {"SEOUL": re.compile(r"\bseoul campus\b", re.I), "ERICA": re.compile(r"\berica\b", re.I)}
ACADEMIC_YEAR_PATTERN = re.compile(r"\b(20\d{2})\s*(?:[-–/]\s*(20\d{2}|\d{2}))?\s+academic year\b|\bacademic year\s+(20\d{2})\b", re.I)
WORD_PATTERN = re.compile(r"[a-z][a-z0-9'-]+")
STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being below between
    both but by can could did do does doing down during each few for from further had has have having he her here
    hers him his how i if in into is it its itself just me more most my no nor not now of off on once only or other
    our ours out over own same she should so some such than that the their theirs them then there these they this
    those through to too under until up very was we were what when where which while who whom why will with would
    you your yours may must also via per etc e.g i.e""".split()
)

DECLARED_FIELDS = (
    "title", "language", "issuer", "document_type", "campus", "audience", "academic_year",
    "publication_date", "effective_from", "effective_until", "topics",
)  # fmt: skip


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def normalize_declared(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Map declared key/values onto the document schema. Returns (fields, warnings).

    Values outside the controlled vocabularies are dropped with a warning rather
    than stored, so filters never see unvalidated labels.
    """
    out: dict[str, Any] = {}
    warnings: list[str] = []
    lowered = {str(k).strip().lower().replace("-", "_").replace(" ", "_"): v for k, v in raw.items()}
    for key in DECLARED_FIELDS:
        value = lowered.get(key)
        if value in (None, "", []):
            continue
        if key == "campus":
            campus = str(value).strip().upper()
            if campus in CAMPUSES:
                out[key] = campus
            else:
                warnings.append(f"declared campus '{value}' not in vocabulary {sorted(CAMPUSES)}; left unknown")
        elif key == "audience":
            values = [v.lower() for v in _as_list(value)]
            known = [v for v in values if v in AUDIENCES]
            if len(known) != len(values):
                warnings.append(f"dropped unknown audience values {sorted(set(values) - set(known))}")
            out[key] = known
        elif key == "document_type":
            doc_type = str(value).strip().lower().replace(" ", "_")
            if doc_type in DOCUMENT_TYPES:
                out[key] = doc_type
            else:
                warnings.append(f"declared document_type '{value}' not in vocabulary; left unknown")
        elif key == "topics":
            out[key] = [t.lower().replace(" ", "_") for t in _as_list(value)]
        else:
            out[key] = str(value).strip()
    return out, warnings


def detect_topics(text: str) -> list[str]:
    lowered = text.lower()
    return [topic for topic, phrases in TOPIC_RULES.items() if any(p in lowered for p in phrases)]


def detect_campus(text: str) -> str | None:
    """Returns a campus only when exactly one campus is mentioned."""
    hits = [campus for campus, pattern in CAMPUS_RULES.items() if pattern.search(text)]
    return hits[0] if len(hits) == 1 else None


def detect_academic_year(text: str) -> str | None:
    match = ACADEMIC_YEAR_PATTERN.search(text)
    if not match:
        return None
    start = match.group(1) or match.group(3)
    end = match.group(2)
    if end and len(end) == 2:
        end = start[:2] + end
    return f"{start}-{end}" if end else start


def content_terms(text: str) -> list[str]:
    return [w for w in WORD_PATTERN.findall(text.lower()) if w not in STOPWORDS and len(w) > 2]


def top_keywords(text: str, limit: int) -> list[str]:
    """Most frequent content terms; ties broken alphabetically for determinism."""
    if limit <= 0:
        return []
    counts = Counter(content_terms(text))
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def extract_document_metadata(
    declared: dict[str, Any], title: str | None, content: str, method: str, params: dict[str, Any], default_language: str
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """Returns (fields, provenance, warnings) for a SourceDocument."""
    if method not in ("declared", "rule_based"):
        raise ValueError(f"metadata method '{method}' is not implemented")
    fields, warnings = normalize_declared(declared)
    provenance = {k: "declared" for k in fields}
    if "title" not in fields and title:
        fields["title"] = title
        provenance["title"] = "parser"
    if "language" not in fields:
        fields["language"] = default_language
        provenance["language"] = "configured_default"
    if method == "rule_based":
        if params.get("detect_topics", True) and not fields.get("topics"):
            topics = detect_topics(content)
            if topics:
                fields["topics"], provenance["topics"] = topics, "rule"
        if params.get("detect_campus", True) and "campus" not in fields:
            campus = detect_campus(content)
            if campus:
                fields["campus"], provenance["campus"] = campus, "rule"
        if params.get("detect_academic_year", True) and "academic_year" not in fields:
            year = detect_academic_year(content)
            if year:
                fields["academic_year"], provenance["academic_year"] = year, "rule"
    return fields, provenance, warnings
