"""AAES applicability vocabulary (v0) and the chunk condition format.

This is the ONLY place the attribute vocabulary lives (AGENTS.md). Every tagger, filter, profile
and label file imports it from here. v0 is proposed in PLAYBOOK.md Appendix C and becomes v1 at
Gate G2.

A chunk condition says to WHOM a chunk applies:

    constraints   {attribute: [allowed values]}; an attribute that is absent means "no constraint"
    scope         "national" (a national rule: immigration law, NHI) or "campus"
    campus        ["seoul"], ["erica"], or both when scope is national
    requirements  conditions outside the vocabulary (GPA, attendance, documents), as short text;
                  answers state them as caveats and never ask about them
    effective_term "YYYY-1" / "YYYY-2", or None for undated pages
    superseded_by doc_id of the newer version (from the snapshot), or None
    extraction_method  {field: "site_default" | "rule" | "llm" | "snapshot"}
    evidence      {field: substring of the chunk text that supports it}; required for "llm" fields
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

VOCABULARY_VERSION = "v0"

# attribute -> allowed values, in a fixed order (used for sorting and for the UI)
VOCABULARY: dict[str, tuple[str, ...]] = {
    "campus": ("seoul", "erica"),
    "degree_level": ("undergraduate", "master", "doctoral", "language_program", "non_degree"),
    "year": ("1", "2", "3", "4"),  # undergraduate only
    "student_type": ("degree_seeking", "exchange", "visiting", "language_program", "short_term"),
    "visa": ("D-2", "D-2-5", "D-2-8", "D-4", "D-10", "other"),
    "topik_level": ("none", "1", "2", "3", "4", "5", "6"),
    "english_track": ("yes", "no"),
    "academic_status": ("enrolled", "leave_of_absence", "completed_coursework", "graduating", "admitted_not_enrolled"),
}
# `term` is open-ended, so it is a pattern, not a value list.
TERM_RE = re.compile(r"^\d{4}-[12]$")
CONSTRAINT_ATTRIBUTES = tuple(a for a in VOCABULARY if a != "campus")  # campus has its own field
SCOPES = ("national", "campus")
METHODS = ("site_default", "rule", "llm", "snapshot")
FIELDS = ("constraints", "scope", "campus", "requirements", "effective_term", "superseded_by")


@dataclass
class ChunkCondition:
    constraints: dict[str, list[str]] = field(default_factory=dict)
    scope: str = "campus"
    campus: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    effective_term: str | None = None
    superseded_by: str | None = None
    extraction_method: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)

    def normalized(self) -> ChunkCondition:
        """Same condition with values deduplicated and in vocabulary order, empty constraints dropped."""
        order = lambda attr: lambda v: VOCABULARY[attr].index(v)  # noqa: E731
        return ChunkCondition(
            constraints={a: sorted(set(v), key=order(a)) for a, v in self.constraints.items() if v},
            scope=self.scope, campus=sorted(set(self.campus), key=order("campus")),
            requirements=list(self.requirements), effective_term=self.effective_term,
            superseded_by=self.superseded_by, extraction_method=dict(self.extraction_method),
            evidence=dict(self.evidence),
        )  # fmt: skip

    def validate(self, text: str | None = None) -> None:
        """Raise ValueError unless every value is in the vocabulary. With `text`, every evidence
        quote must be a substring of it, and every field extracted by the LLM must have one."""
        for attr, values in self.constraints.items():
            if attr not in CONSTRAINT_ATTRIBUTES:
                raise ValueError(f"unknown attribute {attr!r} (vocabulary {VOCABULARY_VERSION})")
            bad = [v for v in values if v not in VOCABULARY[attr]]
            if bad:
                raise ValueError(f"{attr}: values {bad} not in {VOCABULARY[attr]}")
        if self.scope not in SCOPES:
            raise ValueError(f"scope {self.scope!r} not in {SCOPES}")
        if not self.campus or any(c not in VOCABULARY["campus"] for c in self.campus):
            raise ValueError(f"campus {self.campus!r} must be a non-empty subset of {VOCABULARY['campus']}")
        if self.scope == "national" and set(self.campus) != set(VOCABULARY["campus"]):
            raise ValueError("a national rule applies to both campuses")
        if self.effective_term is not None and not TERM_RE.match(self.effective_term):
            raise ValueError(f"effective_term {self.effective_term!r} is not YYYY-1 or YYYY-2")
        for name, method in self.extraction_method.items():
            if name not in FIELDS and name not in CONSTRAINT_ATTRIBUTES:
                raise ValueError(f"extraction_method for unknown field {name!r}")
            if method not in METHODS:
                raise ValueError(f"extraction_method {method!r} not in {METHODS}")
        if text is not None:
            for name, quote in self.evidence.items():
                if not quote or quote not in text:
                    raise ValueError(f"evidence for {name!r} is not a substring of the chunk")
            missing = [n for n, m in self.extraction_method.items() if m == "llm" and n not in self.evidence]
            if missing:
                raise ValueError(f"LLM-extracted fields without an evidence quote: {missing}")

    def to_dict(self) -> dict:
        """Full form, stored in the MongoDB chunk metadata."""
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: dict) -> ChunkCondition:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    def to_payload(self) -> dict:
        """Compact copy of the filterable fields for the Qdrant payload (flat keys, lists of strings)."""
        n = self.normalized()
        payload = {f"app_{a}": v for a, v in n.constraints.items()}
        payload.update(app_scope=n.scope, app_campus=n.campus)
        if n.effective_term:
            payload["app_term"] = n.effective_term
        payload["app_superseded"] = n.superseded_by is not None
        return payload


def term_of(year: int, month: int) -> str:
    """Term of a date: January–June → YYYY-1, July–December → YYYY-2.

    shortcut: a notice posted in Jan/Feb about the spring term maps correctly, but one posted in
    June about the fall term maps to -1; text that names a term ("2026 Fall Semester") wins over this.

    >>> term_of(2026, 3), term_of(2021, 9)
    ('2026-1', '2021-2')
    """
    return f"{year}-{1 if month <= 6 else 2}"
