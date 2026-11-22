"""AAES applicability vocabulary (v1) and the chunk condition format.

This is the ONLY place the attribute vocabulary lives (AGENTS.md). Every tagger, filter, profile
and label file imports it from here. v0 was proposed in PLAYBOOK.md Appendix C; v1 is Amendment A17.

A chunk condition says to WHOM a chunk applies:

    constraints   {attribute: [allowed values]}; an attribute that is absent means "no constraint"
    any_of        alternative condition sets joined by "or" in the text, e.g.
                  [{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}]; the chunk applies
                  when `constraints` fit AND (any_of is empty OR at least one set fits)
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

VOCABULARY_VERSION = "v1"

# attribute -> allowed values, in a fixed order (used for sorting and for the UI)
VOCABULARY: dict[str, tuple[str, ...]] = {
    "campus": ("seoul", "erica"),
    "degree_level": ("undergraduate", "master", "doctoral", "language_program", "non_degree"),
    "year": ("1", "2", "3", "4"),  # undergraduate only
    "student_type": ("degree_seeking", "exchange", "visiting", "language_program"),
    "visa": ("D-2", "D-2-5", "D-2-8", "D-4", "D-10", "other"),
    "topik_level": ("none", "1", "2", "3", "4", "5", "6"),
    "english_track": ("yes", "no"),
    "academic_status": ("applicant", "admitted_not_enrolled", "enrolled", "leave_of_absence", "completed_coursework", "graduating"),
    "korean_standard": ("pass", "exempt", "fail"),  # the admission Korean-language standard (pass/fail, not a TOPIK level)
}
# Declared scope defaults (A17): an attribute the user has NOT stated is assumed to exclude these values.
# Step 1 shows them in the trace with status "scope_default"; Step 2 treats them like a stated value.
SCOPE_DEFAULTS: dict[str, tuple[str, ...]] = {
    "academic_status": tuple(v for v in ("admitted_not_enrolled", "enrolled", "leave_of_absence", "completed_coursework", "graduating")),
}
# `term` is open-ended, so it is a pattern, not a value list.
TERM_RE = re.compile(r"^\d{4}-[12]$")
CONSTRAINT_ATTRIBUTES = tuple(a for a in VOCABULARY if a != "campus")  # campus has its own field
SCOPES = ("national", "campus")
METHODS = ("site_default", "rule", "llm", "snapshot")
FIELDS = ("constraints", "any_of", "scope", "campus", "requirements", "effective_term", "superseded_by")


@dataclass
class ChunkCondition:
    constraints: dict[str, list[str]] = field(default_factory=dict)
    any_of: list[dict[str, list[str]]] = field(default_factory=list)
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
            any_of=[{a: sorted(set(v), key=order(a)) for a, v in group.items() if v} for group in self.any_of],
            scope=self.scope, campus=sorted(set(self.campus), key=order("campus")),
            requirements=list(self.requirements), effective_term=self.effective_term,
            superseded_by=self.superseded_by, extraction_method=dict(self.extraction_method),
            evidence=dict(self.evidence),
        )  # fmt: skip

    def validate(self, text: str | None = None) -> None:
        """Raise ValueError unless every value is in the vocabulary. With `text`, every evidence
        quote must be a substring of it, and every field extracted by the LLM must have one."""
        for group in self.any_of:
            if not group:
                raise ValueError("an any_of condition set may not be empty")
            ChunkCondition(constraints=group, campus=["seoul"]).validate()
        if len(self.any_of) == 1:
            raise ValueError("any_of needs at least two alternative sets (one set belongs in constraints)")
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
        if n.any_of:  # alternatives are not hard-filterable: a prefilter must not drop the chunk on them
            payload["app_any_of"] = True
        return payload


def term_of(year: int, month: int) -> str:
    """Term of a date: January–June → YYYY-1, July–December → YYYY-2.

    shortcut: a notice posted in Jan/Feb about the spring term maps correctly, but one posted in
    June about the fall term maps to -1; text that names a term ("2026 Fall Semester") wins over this.

    >>> term_of(2026, 3), term_of(2021, 9)
    ('2026-1', '2021-2')
    """
    return f"{year}-{1 if month <= 6 else 2}"


# --------------------------------------------------------------------------- profile fit (Step 2 helper)

FIT_COMPATIBLE, FIT_CONFLICTING, FIT_OPEN = "compatible", "conflicting", "open"


def profile_with_scope_defaults(profile: dict[str, list[str]]) -> dict[str, dict]:
    """Stated profile {attribute: [values]} → {attribute: {"values": [...], "status": ...}}.

    Stated attributes get status "stated". An unstated attribute with a SCOPE_DEFAULTS entry gets those values
    with status "scope_default" (A17: unless the user says they are an applicant, they are not one).

    >>> profile_with_scope_defaults({"campus": ["erica"]})["academic_status"]["status"]
    'scope_default'
    """
    out = {a: {"values": list(v), "status": "stated"} for a, v in profile.items() if v}
    for attribute, values in SCOPE_DEFAULTS.items():
        out.setdefault(attribute, {"values": list(values), "status": "scope_default"})
    return out


def _set_fit(group: dict[str, list[str]], profile: dict[str, dict]) -> str:
    """One condition set against a profile: conflicting if a known value is outside an allowed list,
    open if an attribute is unknown, else compatible. A profile with several possible values (scope
    default) conflicts only when none of them is allowed."""
    result = FIT_COMPATIBLE
    for attribute, allowed in group.items():
        entry = profile.get(attribute, {})
        known = entry.get("values")
        if not known:
            result = FIT_OPEN
        elif not set(known) & set(allowed):
            return FIT_CONFLICTING
        elif entry.get("status") == "scope_default":
            result = FIT_OPEN  # a scope default only rules values OUT (e.g. "applicant"); it never confirms a branch
    return result


def condition_fit(condition: ChunkCondition, profile: dict[str, list[str]]) -> str:
    """A_e(u): does this chunk apply to the student? "compatible", "conflicting" or "open" (unknown).

    Campus is part of the check (scope national = both campuses). `any_of` holds when ANY set fits:
    compatible if one set is compatible, conflicting only if every set conflicts, else open.
    """
    full = profile_with_scope_defaults(profile)
    base = _set_fit({"campus": condition.campus, **condition.constraints}, full)
    if base == FIT_CONFLICTING or not condition.any_of:
        return base
    fits = [_set_fit(group, full) for group in condition.any_of]
    alt = FIT_COMPATIBLE if FIT_COMPATIBLE in fits else FIT_CONFLICTING if all(f == FIT_CONFLICTING for f in fits) else FIT_OPEN
    if alt == FIT_CONFLICTING:
        return FIT_CONFLICTING
    return FIT_COMPATIBLE if base == alt == FIT_COMPATIBLE else FIT_OPEN
