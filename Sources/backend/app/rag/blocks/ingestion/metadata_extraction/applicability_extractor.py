"""AAES chunk applicability tags: readable rules first, guarded LLM fallback second."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from app.rag.applicability import CONSTRAINT_ATTRIBUTES, VOCABULARY, VOCABULARY_VERSION, ChunkCondition, term_of
from app.rag.blocks.ingestion.metadata_extraction.base import BaseMetadataExtractor
from app.rag.blocks.ingestion.metadata_extraction.basic_extractor import BasicMetadataExtractor
from app.rag.schemas import DocumentMetadata, ParsedDocument


# The LLM is asked only about chunks the rules left untagged AND that contain one of these cues (cost control).
LLM_CUE = re.compile(
    r"eligib|\bapplicants?\b|\bonly\b|\bmust\b|\brequired\b|\bstudents? (?:who|with|in)\b|"  # eligibility wording
    r"graduat|\bmaster|\bdoctor|\bph\.?\s*d\b|\bfreshm|\bnew students?\b|"  # degree level / year of study
    r"\bexchange\b|\bvisiting\b|\binternational students?\b|"  # student type
    r"\bvisa\b|\bD-\d|\bTOPIK\b|\bkorean (?:language|proficiency)\b|"  # visa / language
    r"\benrolled\b|leave of absence|\bcomplet|\bsemesters?\b|\byears?\b|"  # academic status / term
    r"\bSeoul\b|\bERICA\b",  # the other campus may be named on a page
    re.IGNORECASE)
LLM_NUM_CTX, LLM_SEED = 4096, 42

NATIONAL_RULES = (
    r"\bpart[- ]time (?:employment|work permits?)\b",
    r"\bextension of (?:residence|stay)\b",
    r"\b(?:visa|residence) status change\b",
    r"\bchange of (?:visa|residence|status of (?:stay|sojourn))\b",
    r"\balien[- ]registration\b",
    r"\bnational health insur(?:ance|ane)\b",
    r"\bNHI (?:enrollment|premiums?)\b",
)
CAMPUS_PROCEDURE = re.compile(
    r"\b(?:submit|apply|visit|contact)\b.{0,60}\b(?:OIA|HY-IN|international office)\b",
    re.IGNORECASE | re.DOTALL,
)
MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        (
            "", "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December",
        )
    )
    if name
}


# "graduate school/students/courses" or a "Graduate:" table cell = master + doctoral ("undergraduate" never matches \b)
GRADUATE = r"\bgraduate(?: school| students?| courses?| programs?|\s*:)"
GUIDE_DEGREE_LEVELS = (
    (re.compile(r"\bundergraduate\s+admission\s+(?:guides?|guidelines?)\b|\bGKS\s*[-–]\s*U\b", re.IGNORECASE),
     ["undergraduate"]),
    (re.compile(r"\bgraduate\s+admission\s+(?:guides?|guidelines?)\b|\bGKS\s*[-–]\s*G\b", re.IGNORECASE),
     ["master", "doctoral"]),
)
PRIOR_QUALIFICATION = re.compile(
    r"\b(?:must\s+hold|(?:must\s+)?have\s+completed|holders?\s+of|graduated\s+with)\s+"
    r"(?:an?\s+)?bachelor(?:'s|’s)?(?:\s+degree)?\b|"
    r"\bcompleted\s+(?:your|an?)\s+undergraduate\s+program\b|"
    r"\bfield of study\s*:\s*bachelor(?:'s|’s)?(?:\s+degree)?\b|"  # S06: a required prior field
    r"\bbachelor(?:'s|’s)?\s+degree\s*(?:\([^\n)]*\)\s*)?or\s+higher\b",
    re.IGNORECASE,
)
VISA_NOISE = re.compile(
    r"\bvisa\b.*\b(?:contact|inquir(?:y|ies))\b|\b(?:contact|inquir(?:y|ies))\b.*\bvisa\b|"
    r"abus\s*ing\s+visa|\basylum\b|countries?\s+subject\s+to\s+intensive\s+management",
    re.IGNORECASE,
)
NAMED_GRADUATE_SCHOOL = re.compile(
    r"\b(?:[A-Z][\w&.'’()-]*[ \t]+){1,6}Graduate School of[ \t]+"
    r"(?:[A-Z][\w&.'’()-]*(?:[ \t]+|(?=[,;:.\n]|$))){1,6}",
)
# "Except students who took a leave of absence, …" and ineligibility lists name groups that are NOT eligible.
NEGATED = re.compile(
    r"\b(?:except|excluding|excluded|cannot apply|are not allowed)\b[^.\n)]*|"
    r"\(\s*\b(?:ineligibility|ineligible|not eligible|exclusions?)\b\s*:?\s*(?:[^()]|\([^)]*\))*\)|"
    r"\b(?:ineligibility|ineligible|not eligible|exclusions?)\b\s*:\s*[^.\n]*",
    re.IGNORECASE,
)
PREFERENCE = re.compile(r"\b(?:prefer\w*|additional points?|bonus|advantage|optional)\b", re.IGNORECASE)
ADMISSION_GUIDE = re.compile(
    r"\b(?:admission (?:guidelines?|guides?)|application forms?\s*&\s*guidelines?)\b|"
    r"\b(?:GKS|scholarship program|degree program)[^\n]{0,60}\bapplication guidelines?\b|"  # not "Visa Application Guideline"
    r"\brecruitment of\b.{0,120}\bstudents?\b",
    re.IGNORECASE,
)
RULE_5B_OPTION = re.compile(
    r"\b(?:Social Integration Program|Korea Immigration and Integration Program|KIIP|"
    r"IIE(?:\s+level)?|King Sejong Institute|pre[- ]assessment(?:\s+score)?)\b",
    re.IGNORECASE,
)


def _first_match(patterns: tuple[str, ...], text: str) -> re.Match[str] | None:
    return next((match for pattern in patterns if (match := re.search(pattern, text, re.IGNORECASE))), None)


def _evidence(patterns: tuple[str, ...], text: str) -> str | None:
    match = _first_match(patterns, text)
    return match.group(0) if match else None


def _scope(context: str) -> str:
    national = _first_match(NATIONAL_RULES, context)
    return "national" if national and not CAMPUS_PROCEDURE.search(context) else "campus"


def _guide_degree_level(chunk: dict) -> tuple[list[str], str | None]:
    for label in [chunk.get("title", ""), *(chunk.get("heading_path") or [])]:
        for pattern, values in GUIDE_DEGREE_LEVELS:
            if pattern.search(label):
                return values, label
    return [], None


def _degree_level(context: str) -> tuple[list[str], str | None]:
    context = PRIOR_QUALIFICATION.sub(" ", context)
    context = NAMED_GRADUATE_SCHOOL.sub(" ", context)
    patterns = {
        "undergraduate": (r"\bbachelor(?:'s|’s)?\b", r"\bundergraduate(?: school| students?)?\b"),
        "master": (r"\bmaster(?:'s|’s)?\b", GRADUATE),
        "doctoral": (r"\bdoctoral\b", r"\bph\.?\s*d\.?\b", GRADUATE),
        "language_program": (r"\b(?:korean )?language program(?: students?)?\b",),
        "non_degree": (r"\bnon[- ]degree(?: students?| program)?\b",),
    }
    values = [value for value, value_patterns in patterns.items() if _first_match(value_patterns, context)]
    matched_patterns = tuple(pattern for value in values for pattern in patterns[value])
    return values, _evidence(matched_patterns, context) if matched_patterns else None


def _year(context: str) -> tuple[list[str], str | None]:
    values: set[int] = set()
    evidence: str | None = None
    explicit_year = r"\bYear\s*:?\s*(?:Year\s*)?([1-4])(?:\s*(?:[-–~,]|and)\s*([1-4]))?\b"
    for match in re.finditer(explicit_year, context, re.IGNORECASE):
        evidence = evidence or match.group(0)
        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        values.update(range(min(first, last), max(first, last) + 1))

    for line in context.splitlines():
        if not re.search(r"\b(?:bachelor(?:'s|’s)?\s+degree|undergraduate)\b", line, re.IGNORECASE):
            continue
        for match in re.finditer(r"\b([1-4])\s*(?:[-–~,]|and)\s*([1-4])\s+years?\b", line, re.IGNORECASE):
            evidence = evidence or match.group(0)
            first, last = int(match.group(1)), int(match.group(2))
            values.update(range(min(first, last), max(first, last) + 1))

    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4}
    for match in re.finditer(
        r"\b(first|second|third|fourth)(?:\s+and\s+(first|second|third|fourth))?\s+years?\b",
        context,
        re.IGNORECASE,
    ):
        evidence = evidence or match.group(0)
        values.add(ordinals[match.group(1).lower()])
        if match.group(2):
            values.add(ordinals[match.group(2).lower()])
    return [str(value) for value in sorted(values)], evidence


def _topik_level(context: str) -> tuple[list[str], str | None]:
    met = re.search(
        r"(?:TOPIK|Korean Language Proficiency)[^;\n]{0,50}?Level\s*([1-6])"
        r"(?:\s*;[^;\n]{0,80}?(?:TOPIK|Korean Language Proficiency)[^;\n]{0,30}?:\s*)?([OX])\b",
        context,
        re.IGNORECASE,
    )
    if met:
        level = int(met.group(1))
        values = range(level, 7) if met.group(2).upper() == "O" else range(0, level)
        return ["none" if value == 0 else str(value) for value in values], met.group(0)
    minimum = TOPIK_THRESHOLD.search(context)
    if minimum:
        return topik_at_least(int(minimum.group(1))), minimum.group(0)
    return [], None


# "TOPIK level 3 or higher", "TOPIK 4 or above", "TOPIK Lv4~6", "TOPIK level 5+" — a threshold, so levels N…6
TOPIK_THRESHOLD = re.compile(
    r"\bTOPIK\s*(?:level|lv\.?|grade)?\s*([1-6])\s*(?:or (?:above|higher|more)\b|\+|[~–-]\s*6\b)", re.IGNORECASE)


def topik_at_least(level: int) -> list[str]:
    """>>> topik_at_least(3)
    ['3', '4', '5', '6']
    """
    return [str(value) for value in range(level, 7)]


VISA_CODE = r"D\s*-\s*(?:10(?:\s*-\s*1)?|2(?:\s*-\s*(?:5|8))?|4)"


def _normalized_visa(code: str) -> str:
    value = re.sub(r"\s+", "", code).upper()
    return "D-10" if value == "D-10-1" else value


def _visa(context: str) -> tuple[list[str], str | None]:
    # Contact details and misuse warnings mention visa codes without defining their audience (one sentence each).
    context = re.sub(r"[^.\n]+", lambda m: " " if VISA_NOISE.search(m.group(0)) else m.group(0), context)
    # "When transferring from D-4 to D-2" is the procedure for current D-4 holders: keep the old visa (C03)
    transfer = re.search(rf"\btransferring from\b.{{0,180}}?\b(?P<old>{VISA_CODE})\b.{{0,180}}?\bto\b", context, re.IGNORECASE)
    if transfer:
        return [_normalized_visa(transfer.group("old"))], transfer.group("old")
    # "received permission to change … to D-10", "If you change from D-4 visa to D-2 visa": the new visa (R07, R12)
    change = re.search(
        rf"\bchang\w*\b[^.\n]{{0,300}}?\bt\s*o\b[^.\n]{{0,120}}?\b(?P<target>{VISA_CODE})\b",
        context,
        re.IGNORECASE,
    )
    if not change:
        change = re.search(
            rf"\bfrom\b[^.\n]{{0,120}}?\b{VISA_CODE}\b[^.\n]{{0,120}}?\bt\s*o\b[^.\n]{{0,80}}?\b(?P<target>{VISA_CODE})\b",
            context,
            re.IGNORECASE,
        )
    if change:
        return [_normalized_visa(change.group("target"))], change.group("target")
    matches = list(re.finditer(rf"\b{VISA_CODE}\b", context, re.IGNORECASE))
    values = [_normalized_visa(match.group(0)) for match in matches]
    return list(dict.fromkeys(values)), matches[0].group(0) if matches else None


def _student_type(context: str) -> tuple[list[str], str | None]:
    patterns = {
        "degree_seeking": (
            r"\b(?:international\W+)?degree\W+(?:program\W+)?students?\b",
            r"\benrolled\s+in\s+(?:an?\s+)?degree\s+program\b",
            r"\bdegree\s+programs?\b",
            r"\bmaster(?:'s|’s|s)?\s*/\s*doctoral\s+degree\s+students?\b",
        ),
        "exchange": (r"\bexchange students?\b",),
        "visiting": (r"\bvisiting students?\b", r"\bvisiting program participants?\b"),
        "language_program": (
            r"\b(?:korean )?language program(?: students?)?\b",
            r"\blanguage training\b[^.;\n]{0,60}\bstudents?\b",
            r"\blanguage school program\b",  # not "language school attendance rate" (a requirement, C03)
        ),
    }
    values = [value for value, value_patterns in patterns.items() if _first_match(value_patterns, context)]
    matched_patterns = tuple(pattern for value in values for pattern in patterns[value])
    return values, _evidence(matched_patterns, context) if matched_patterns else None


def _english_track(context: str) -> tuple[list[str], str | None]:
    no = re.search(r"\b(?:non[- ]English|Korean)[- ](?:track|taught)\b", context, re.IGNORECASE)
    if no:
        return ["no"], no.group(0)
    yes = re.search(r"\bEnglish[- ](?:track|taught)(?: program| course)?\b", context, re.IGNORECASE)
    return (["yes"], yes.group(0)) if yes else ([], None)


def _academic_status(title: str, context: str) -> tuple[list[str], str | None]:
    # an exclusion list that removes every other status states "enrolled" (C04)
    exclusions = re.search(r"\bExclusions\s*:(.*)", context, re.IGNORECASE | re.DOTALL)
    if exclusions and re.search(r"expected graduates|leave of absence|completed students|extra semesters", exclusions.group(1), re.IGNORECASE):
        return ["enrolled"], _evidence((r"\bInternational students studying\b", r"\bEligibility\b"), context)
    context = NEGATED.sub(" ", context)  # statuses in an exclusion clause are not constraints
    if re.search(r"\b(?:return to school|re[- ]registration)\b", title, re.IGNORECASE):
        match = re.search(r"\bstudents? who (?:took|take|have taken) (?:a )?leave of absence\b", context, re.IGNORECASE)
        return ["leave_of_absence"], match.group(0) if match else None
    if re.search(r"\bleave of absence\b", title, re.IGNORECASE):
        match = re.search(r"\b(?:currently in school|currently enrolled|enrolled students?)\b", context, re.IGNORECASE)
        return ["enrolled"], match.group(0) if match else None
    patterns = {
        "enrolled": (
            r"\benrolled students?\b",
            r"\bstudents? who (?:are )?enrolled(?: at)?\b",
            r"\bcurrently enrolled\b",
            r"\bcurrently in school\b",
        ),
        "leave_of_absence": (
            r"\bstudents? (?:who (?:took|take|have taken) (?:a )?leave of absence|on leave)\b",
        ),
        "completed_coursework": (r"\bcompleted coursework\b", r"\bcompleted students?\b"),
        "graduating": (r"\bexpected graduates?\b", r"\bgraduating students?\b"),
        "admitted_not_enrolled": (r"\bacceptance\b", r"\badmitted students?\b", r"\badmission result page\b"),
    }
    values = [value for value, value_patterns in patterns.items() if _first_match(value_patterns, context)]
    matched_patterns = tuple(pattern for value in values for pattern in patterns[value])
    return values, _evidence(matched_patterns, context) if matched_patterns else None


def _applicant(title: str, text: str) -> tuple[list[str], str | None]:
    if not ADMISSION_GUIDE.search(title):
        return [], None
    admitted = re.search(
        r"\bsuccessful candidates?\b|\bcertificate of admission\b|\badmission certificate\b|"
        r"\bafter\s+deposit\s+payment\b",
        text,
        re.IGNORECASE,
    )
    if admitted:
        return ["admitted_not_enrolled"], admitted.group(0)
    mention = re.search(r"\b(?:applicants?|applications?|admission)\b", text, re.IGNORECASE)
    return ["applicant"], mention.group(0) if mention else None


def _korean_standard(context: str) -> tuple[list[str], str | None]:
    failed = re.search(
        r"\bdid not satisfy the Korean Language Standards?\b|\bKorean Standard Fail\b",
        context,
        re.IGNORECASE,
    )
    if failed:
        return ["fail"], failed.group(0)
    pass_or_exempt = re.search(
        r"\bSatisfied\s*\(\s*or being exempted\s*\)\s*the Korean Language Standards?\b",
        context,
        re.IGNORECASE,
    )
    if pass_or_exempt:
        return ["pass", "exempt"], pass_or_exempt.group(0)
    # "exempt" only next to the Korean standard itself; a bare "exempted" (fees, vaccination, …) is not it
    exempt = re.search(r"\bexempt(?:ed|ion)?\b[^.\n;]{0,40}\bKorean (?:Language )?Standards?\b|"
                       r"\bKorean (?:Language )?Standards?\b[^.\n;]{0,40}\bexempt(?:ed|ion)?\b", context, re.IGNORECASE)
    return (["exempt"], exempt.group(0)) if exempt else ([], None)


def _any_of(text: str) -> tuple[list[dict[str, list[str]]], str | None]:
    """Recognise one line/sentence that explicitly joins TOPIK and English alternatives with ``or``."""
    english_pattern = re.compile(r"\b(?:IELTS|TOEFL|TEPS|English[- ]track)\b", re.IGNORECASE)
    certificate_pattern = re.compile(r"\b(?:valid\s+)?TOPIK(?:\s+score)?\s+certificate\b", re.IGNORECASE)
    for line in text.splitlines():
        for sentence in re.finditer(r"[^.!?]+(?:[.!?]|$)", line):
            phrase = sentence.group(0).strip()
            threshold = TOPIK_THRESHOLD.search(phrase)
            topik = threshold or certificate_pattern.search(phrase)
            english = english_pattern.search(phrase, topik.end() if topik else 0)
            if not topik or not english or not re.search(r"\bor\b", phrase[topik.end() : english.start()], re.IGNORECASE):
                continue
            levels = topik_at_least(int(threshold.group(1))) if threshold else [str(level) for level in range(1, 7)]
            return [{"topik_level": levels}, {"english_track": ["yes"]}], phrase
    return [], None


def _rule_5b_requirements(text: str) -> list[str]:
    """Return TOPIK alternatives that include an option outside vocabulary v1."""
    requirements = []
    for line in text.splitlines():
        phrases = [line.strip()] if re.match(r"\s*Sort\s*:", line, re.IGNORECASE) else [
            sentence.group(0).strip() for sentence in re.finditer(r"[^.!?]+(?:[.!?]|$)", line)
        ]
        for phrase in phrases:
            if re.search(r"\bTOPIK\b", phrase, re.IGNORECASE) and RULE_5B_OPTION.search(phrase):
                requirements.append(phrase[:200].rstrip())
    return list(dict.fromkeys(requirements))


def _preference_context(text: str, quote: str | None) -> str | None:
    """Return the exact local text around a rule/evidence quote when it marks a preference."""
    if not quote:
        return None
    start = text.find(quote)
    if start < 0:
        return quote if PREFERENCE.search(quote) else None
    nearby = text[max(0, start - 80) : min(len(text), start + len(quote) + 80)]
    return nearby.strip() if PREFERENCE.search(nearby) else None


def _add_preference_requirement(condition: ChunkCondition, phrase: str, text: str) -> None:
    requirement = f"preference: {phrase}"
    if requirement not in condition.requirements:
        condition.requirements.append(requirement)
    condition.extraction_method["requirements"] = "rule"
    if phrase in text:
        condition.evidence.setdefault("requirements", phrase)


def _requirements(text: str) -> list[str]:
    patterns = (
        r"\b(?:language school )?attendance rate of less than \d{1,3}%",
        r"\bTOPIK scores? (?:are|is) now higher than [^.\n;]{1,100}",
        r"\bApplicants who [^\n]{0,100}English Language Standards\b",
        r"[^.;\n]{0,60}\bGPA\b[^.;\n]{0,60}",
        r"\bmust (?:pay|show)[^.\n]{0,100}\b(?:KRW\s*)?\d[\d,]*(?:\s*million)?(?:\s*(?:won|KRW|USD))?\b",
        r"\bbank account balance[^.\n]{0,160}\bKRW\s*\d[\d,]*(?:\s*million)?\b",
    )
    found = []
    for pattern in patterns:
        found.extend(match.group(0).strip() for match in re.finditer(pattern, text, re.IGNORECASE))
    return list(dict.fromkeys(found))


def _effective_term(context: str, post_date: str | None) -> tuple[str | None, str | None]:
    semester = re.search(r"\b(20\d{2})\s+(Spring|Fall)\s+Semester\b", context, re.IGNORECASE)
    if semester:
        return f"{semester.group(1)}-{1 if semester.group(2).lower() == 'spring' else 2}", semester.group(0)
    numbered = re.search(r"\b(20\d{2})\s*[-–]\s*([12])\b", context)
    if numbered:
        return f"{numbered.group(1)}-{numbered.group(2)}", numbered.group(0)
    applied = re.search(
        r"\bapplied from\s+"
        r"(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*(20\d{2})"
        r"|(20\d{2})[-./](\d{1,2})[-./]\d{1,2})",
        context,
        re.IGNORECASE,
    )
    if applied:
        year = int(applied.group(2) or applied.group(3))
        month = MONTHS[applied.group(1).lower()] if applied.group(1) else int(applied.group(4))
        return term_of(year, month), applied.group(0)
    if post_date:
        try:
            posted = date.fromisoformat(post_date)
            return term_of(posted.year, posted.month), None
        except ValueError:
            pass
    return None, None


def _first_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[start:])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


# Every chunk lands in exactly one bucket; VERIFY checks the buckets add up to the chunk count.
TAG_BUCKETS = ("rule_tagged", "rule_unconditioned", "rule_cue_unknown", "llm_tagged", "llm_unconditioned", "llm_rejected", "llm_errors")
TAG_PROMPT_VERSION = "v3"  # bump whenever the fallback prompt below changes
POSTCHECK_VERSION = "p1"


def _normalized_substring(text: str, quote: str) -> str | None:
    words = quote.split()
    if not words:
        return None
    match = re.search(r"\s+".join(map(re.escape, words)), text, re.IGNORECASE)
    return match.group(0) if match else None


def _apply_llm_fallback(
    condition: ChunkCondition,
    text: str,
    llm: Callable[[str], str],
    trace_details: dict[str, Any] | None,
) -> None:
    prompt = (
        "Which students does this chunk apply to? Tag only constraints the chunk states explicitly.\n"
        "Do not tag preferences ('preferred', 'additional points', 'optional').\n"
        "Reply with JSON only. `evidence` is an OBJECT with one exact quote from the chunk PER attribute in `constraints`.\n"
        'Example: {"constraints":{"degree_level":["master","doctoral"],"visa":["D-2"]},'
        '"evidence":{"degree_level":"graduate students","visa":"D-2 visa holders"}}\n'
        'If the chunk applies to every student, reply {"constraints":{},"evidence":{}}.\n'
        f"Allowed attributes and values: {json.dumps({a: VOCABULARY[a] for a in CONSTRAINT_ATTRIBUTES})}\n\n"
        f"Chunk:\n{text}"
    )
    details: dict[str, Any] = {"status": "called"}
    if trace_details is not None:
        trace_details["llm_fallback"] = details
    try:
        raw = llm(prompt)
    except Exception as exc:  # a fallback must never make offline tagging fail
        details.update(status="error", reason=f"{type(exc).__name__}: {exc}")
        return
    details["raw_output"] = str(raw)[:800]
    parsed = _first_json_object(str(raw))
    if parsed is None:
        details.update(status="rejected", reason="bad_json", rejected_fields={"_output": "bad_json"}, mapped_fields={})
        return
    constraints = parsed.get("constraints")
    evidence = parsed.get("evidence")
    if not isinstance(constraints, dict) or not isinstance(evidence, dict):
        details.update(status="rejected", reason="bad_json", rejected_fields={"_output": "bad_json"}, mapped_fields={})
        return

    constraints = dict(constraints)
    mapped: dict[str, str] = {}
    if "semester" in constraints:
        constraints.pop("semester")
        mapped["semester"] = "dropped"
    student_types = constraints.get("student_type")
    if isinstance(student_types, list):
        kept = [value for value in student_types if value not in ("international", "volunteer")]
        if len(kept) != len(student_types):
            mapped["student_type"] = "dropped"
            if kept:
                constraints["student_type"] = kept
            else:
                constraints.pop("student_type")
    visas = constraints.get("visa")
    if isinstance(visas, list):
        normalized_visas = []
        changed = []
        for value in visas:
            if isinstance(value, str) and value not in VOCABULARY["visa"] and (value.startswith("F") or value.startswith("D-")):
                normalized_visas.append("other")
                changed.append(value)
            else:
                normalized_visas.append(value)
        if changed:
            constraints["visa"] = list(dict.fromkeys(normalized_visas))
            mapped["visa"] = f"{', '.join(changed)} → other"

    rejected: dict[str, str] = {}
    for attribute, values in constraints.items():
        quote = evidence.get(attribute)
        if attribute not in CONSTRAINT_ATTRIBUTES:
            rejected[str(attribute)] = "unknown_attribute"
        elif not isinstance(values, list) or not values or any(value not in VOCABULARY[attribute] for value in values):
            rejected[attribute] = "value_outside_vocabulary"
        elif not isinstance(quote, str) or not quote:
            rejected[attribute] = "missing_quote"
        else:
            exact_quote = _normalized_substring(text, quote)
            if exact_quote is None:
                rejected[attribute] = "quote_not_in_text"
                continue
            if set(values) == set(VOCABULARY[attribute]):
                rejected[attribute] = "every_value"
                continue
            if preference := _preference_context(text, exact_quote):
                rejected[attribute] = "preference"
                _add_preference_requirement(condition, preference, text)
                continue
            if attribute == "topik_level" and (threshold := TOPIK_THRESHOLD.search(exact_quote)):
                values = topik_at_least(int(threshold.group(1)))  # the LLM often keeps only "3" from "3 or above"
            condition.constraints[attribute] = list(dict.fromkeys(values))
            condition.extraction_method[attribute] = "llm"
            condition.evidence[attribute] = exact_quote
    details["mapped_fields"] = mapped
    details["rejected_fields"] = rejected
    # a valid answer with no constraints = "unconditioned"; any refused field with nothing accepted = "rejected" (tags unknown)
    details["status"] = "accepted" if condition.constraints else ("rejected" if rejected else "unconditioned")


def tag_chunk(
    chunk: dict,
    llm: Callable[[str], str] | None = None,
    *,
    trace_details: dict[str, Any] | None = None,
) -> ChunkCondition:
    """Tag one crawler chunk. Rules are authoritative; the optional LLM only fills an empty result."""
    text = chunk["text"]
    context = "\n".join([chunk.get("title", ""), *chunk.get("heading_path", []), text])
    scope = _scope(context)
    campus = list(VOCABULARY["campus"]) if scope == "national" else [chunk["site"]]
    condition = ChunkCondition(
        scope=scope,
        campus=campus,
        superseded_by=chunk.get("superseded_by"),
        extraction_method={
            "scope": "rule" if scope == "national" else "site_default",
            "campus": "rule" if scope == "national" else "site_default",
            "superseded_by": "snapshot",
        },
    )
    national_quote = _evidence(NATIONAL_RULES, text)
    if scope == "national" and national_quote:
        condition.evidence.update(scope=national_quote, campus=national_quote)

    positive_context = NEGATED.sub(" ", context)
    guide_degree, guide_quote = _guide_degree_level(chunk)
    extractors = {
        "degree_level": _degree_level,
        "year": _year,
        "topik_level": _topik_level,
        "visa": _visa,
        "student_type": _student_type,
        "english_track": _english_track,
        "korean_standard": _korean_standard,
    }
    for attribute, extractor in extractors.items():
        source = positive_context if attribute in ("degree_level", "student_type") else context
        values, quote = extractor(source)
        if not values:
            continue
        if preference := _preference_context(text, quote):
            _add_preference_requirement(condition, preference, text)
            continue
        condition.constraints[attribute] = values
        condition.extraction_method[attribute] = "rule"
        if quote and quote in text:
            condition.evidence[attribute] = quote

    if guide_degree:
        condition.constraints["degree_level"] = guide_degree
        condition.extraction_method["degree_level"] = "rule"
        condition.evidence.pop("degree_level", None)
        if guide_quote and guide_quote in text:
            condition.evidence["degree_level"] = guide_quote

    status, status_quote = _academic_status(chunk.get("title", ""), context)
    if status:
        condition.constraints["academic_status"] = status
        condition.extraction_method["academic_status"] = "rule"
        if status_quote and status_quote in text:
            condition.evidence["academic_status"] = status_quote

    applicant, applicant_quote = _applicant(chunk.get("title", ""), text)
    if applicant:
        condition.constraints["academic_status"] = applicant
        condition.extraction_method["academic_status"] = "rule"
        condition.evidence.pop("academic_status", None)
        if applicant_quote:
            condition.evidence["academic_status"] = applicant_quote

    alternatives, alternatives_quote = _any_of(text)
    if alternatives:
        if preference := _preference_context(text, alternatives_quote):
            _add_preference_requirement(condition, preference, text)
        else:
            condition.any_of = alternatives
            condition.evidence["any_of"] = alternatives_quote
            condition.extraction_method["any_of"] = "rule"
            for attribute in ("topik_level", "english_track"):
                condition.constraints.pop(attribute, None)
                condition.extraction_method.pop(attribute, None)
                condition.evidence.pop(attribute, None)

    rule_5b_requirements = _rule_5b_requirements(text)
    if rule_5b_requirements:
        condition.constraints.pop("topik_level", None)
        condition.extraction_method.pop("topik_level", None)
        condition.evidence.pop("topik_level", None)
        if any("topik_level" in group for group in condition.any_of):
            condition.any_of = []
            condition.extraction_method.pop("any_of", None)
            condition.evidence.pop("any_of", None)

    rule_requirements = [*_requirements(text), *rule_5b_requirements]
    condition.requirements.extend(requirement for requirement in rule_requirements if requirement not in condition.requirements)
    if condition.requirements:
        condition.extraction_method["requirements"] = "rule"
        condition.evidence.setdefault("requirements", rule_requirements[0] if rule_requirements else condition.evidence["requirements"])

    condition.effective_term, term_quote = _effective_term(context, chunk.get("post_date"))
    if condition.effective_term:
        condition.extraction_method["effective_term"] = "rule"
        if term_quote and term_quote in text:
            condition.evidence["effective_term"] = term_quote

    if llm is not None and not condition.constraints and not condition.any_of:
        _apply_llm_fallback(condition, text, llm, trace_details)
    return condition.normalized()


class ApplicabilityExtractor(BaseMetadataExtractor):
    """Basic document metadata plus a separate chunk-tagging entry point for T09 ingestion."""

    # shortcut: class-level cache path; one ingest per process, pass it per call if two ever share a process
    cache_path: Path | None = None
    summary: dict[str, Any] = {}

    def extract(self, document: ParsedDocument) -> DocumentMetadata:
        return BasicMetadataExtractor(self.params, self.services).extract(document)

    def tag_chunks(self, chunks: list[dict], cache_path: Path | None = None) -> list[ChunkCondition]:
        """Tag every chunk with rules; ask the auxiliary LLM only for untagged chunks with an LLM_CUE.

        cache_path: JSONL of earlier LLM answers keyed by model digest, prompt version, and chunk text hash.
        After the call, self.summary has the counts and LLM settings for the index manifest.
        """
        use_llm = self.params.get("llm_fallback", True)
        model_name = self.params.get("model", "qwen3.5:4b")
        cache_path = cache_path or self.cache_path
        cache = _read_cache(cache_path)
        counts = {"llm_candidates": 0, "llm_called": 0, "llm_cache_hits": 0, "llm_accepted": 0,
                  "llm_rejected": 0, "llm_rejected_fields_by_reason": {}, "llm_rejected_total": 0,
                  "llm_errors": 0}  # fmt: skip
        loop = asyncio.new_event_loop() if use_llm else None
        selected: dict = {}
        resolution: dict[str, Any] = {"attempted": False, "error": None}
        fallback_details: list[dict[str, Any]] = []

        async def complete(prompt: str, details: dict[str, Any]) -> str:
            options = {"temperature": 0, "num_predict": self.params.get("max_tokens", 256),
                       "num_ctx": LLM_NUM_CTX, "seed": LLM_SEED}  # fmt: skip
            output, usage = await self.services.ollama.complete(selected, [{"role": "user", "content": prompt}], options, think="off")
            details.update(model=selected["name"], digest=selected["digest"], prompt_tokens=usage.get("prompt_eval_count"),
                           output_tokens=usage.get("eval_count"))  # fmt: skip
            return output

        def resolve_model() -> None:
            if not resolution["attempted"]:
                resolution["attempted"] = True
                try:
                    selected.update(loop.run_until_complete(self.services.ollama.pick_model(model_name, "")))  # type: ignore[union-attr]
                    if not selected.get("digest"):
                        raise ValueError(f"Ollama model {selected.get('name', model_name)} has no digest")
                except Exception as exc:
                    resolution["error"] = exc
            if resolution["error"] is not None:
                raise resolution["error"]

        def make_llm(details: dict[str, Any], text: str) -> Callable[[str], str]:
            def llm(prompt: str) -> str:
                try:
                    resolve_model()
                except Exception:
                    counts["llm_called"] += 1
                    raise
                key = _cache_key(selected["digest"], text)
                if key in cache:
                    counts["llm_cache_hits"] += 1
                    details.update(model=selected["name"], digest=selected["digest"], cache_hit=True)
                    return cache[key]
                counts["llm_called"] += 1
                output = loop.run_until_complete(complete(prompt, details))  # type: ignore[union-attr]
                _append_cache(cache_path, key, output)
                cache[key] = output
                return output

            return llm

        try:
            tagged = []
            self.buckets: list[str] = []  # one TAG_BUCKETS entry per chunk, in order
            for index, chunk in enumerate(chunks):
                details: dict[str, Any] = {"chunk_index": index, "doc_id": chunk.get("doc_id")}
                has_cue = LLM_CUE.search(chunk["text"]) is not None
                ask = use_llm and has_cue
                result = tag_chunk(chunk, llm=make_llm(details, chunk["text"]) if ask else None, trace_details=details)
                if "llm_fallback" in details:
                    counts["llm_candidates"] += 1
                    fallback = details["llm_fallback"]
                    if fallback.get("status") == "accepted":
                        counts["llm_accepted"] += 1
                    elif fallback.get("status") == "error":
                        counts["llm_errors"] += 1
                        counts.setdefault("llm_first_error", fallback.get("reason"))
                    elif fallback.get("status") == "unconditioned":
                        counts["llm_unconditioned"] = counts.get("llm_unconditioned", 0) + 1
                    elif fallback.get("status") == "rejected":
                        counts["llm_rejected"] += 1
                        counts["llm_rejected_total"] += 1
                    for reason in fallback.get("rejected_fields", {}).values():
                        by_reason = counts["llm_rejected_fields_by_reason"]
                        by_reason[reason] = by_reason.get(reason, 0) + 1
                    fallback_details.append(details)
                tagged.append(result)
                status = details.get("llm_fallback", {}).get("status")
                rule_bucket = "rule_tagged" if result.constraints or result.any_of else (
                    "rule_cue_unknown" if not use_llm and has_cue else "rule_unconditioned"
                )
                self.buckets.append({None: rule_bucket, "accepted": "llm_tagged",
                                     "unconditioned": "llm_unconditioned", "error": "llm_errors"}.get(status, "llm_rejected"))  # fmt: skip
        finally:
            if loop is not None:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
        self.trace_details = {"llm_fallbacks": fallback_details[:50]}
        degree_inherited = sum(bool(_guide_degree_level(chunk)[0]) for chunk in chunks)
        self.summary = {**counts, "degree_inherited": degree_inherited,
                        "llm": {"enabled": use_llm, "role": "auxiliary", "model": model_name,
                                          "digest": selected.get("digest"), "prompt_version": TAG_PROMPT_VERSION,
                                          "postcheck_version": POSTCHECK_VERSION, "vocabulary_version": VOCABULARY_VERSION,
                                          "temperature": 0, "num_ctx": LLM_NUM_CTX, "seed": LLM_SEED, "thinking": "off",
                                          "cache_path": str(cache_path) if cache_path is not None else None}}  # fmt: skip
        return tagged


def _cache_key(model_digest: str, text: str) -> str:
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    return hashlib.sha256(f"{model_digest}\n{TAG_PROMPT_VERSION}\n{text_hash}".encode()).hexdigest()


def _read_cache(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {row["key"]: row["output"] for row in map(json.loads, f) if row}


def _append_cache(path: Path | None, key: str, output: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "output": output}) + "\n")
