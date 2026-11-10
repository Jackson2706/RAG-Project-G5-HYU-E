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

from app.rag.applicability import CONSTRAINT_ATTRIBUTES, VOCABULARY, ChunkCondition, term_of
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
# "Except students who took a leave of absence, …" names statuses that are NOT eligible
NEGATED = re.compile(r"\b(?:except|excluding|excluded|not eligible|cannot apply|are not allowed)\b[^.\n)]*", re.IGNORECASE)


def _first_match(patterns: tuple[str, ...], text: str) -> re.Match[str] | None:
    return next((match for pattern in patterns if (match := re.search(pattern, text, re.IGNORECASE))), None)


def _evidence(patterns: tuple[str, ...], text: str) -> str | None:
    match = _first_match(patterns, text)
    return match.group(0) if match else None


def _scope(context: str) -> str:
    national = _first_match(NATIONAL_RULES, context)
    return "national" if national and not CAMPUS_PROCEDURE.search(context) else "campus"


def _degree_level(context: str) -> tuple[list[str], str | None]:
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
    # "Year: Year 1-2", "Year 3, 4", "Year 3~4"
    match = re.search(r"\bYear\s*:?\s*(?:Year\s*)?([1-4])(?:\s*(?:[-–~,]|and)\s*([1-4]))?\b", context, re.IGNORECASE)
    if not match:
        return [], None
    first, last = int(match.group(1)), int(match.group(2) or match.group(1))
    if first > last:
        first, last = last, first
    return [str(value) for value in range(first, last + 1)], match.group(0)


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
    minimum = re.search(r"\bTOPIK\s+level\s*([1-6])\s+or higher\b", context, re.IGNORECASE)
    if minimum:
        return [str(value) for value in range(int(minimum.group(1)), 7)], minimum.group(0)
    return [], None


def _visa(context: str) -> tuple[list[str], str | None]:
    transfer = re.search(r"\btransferring from\b.{0,180}?\b(D-(?:10(?:-1)?|2(?:-5|-8)?|4))\b.{0,180}?\bto\b", context, re.IGNORECASE)
    if transfer:
        value = transfer.group(1).upper()
        return ["D-10" if value == "D-10-1" else value], transfer.group(1)
    matches = list(re.finditer(r"\bD-(?:10(?:-1)?|2(?:-5|-8)?|4)\b", context, re.IGNORECASE))
    values = [("D-10" if match.group(0).upper() == "D-10-1" else match.group(0).upper()) for match in matches]
    return list(dict.fromkeys(values)), matches[0].group(0) if matches else None


def _student_type(context: str) -> tuple[list[str], str | None]:
    patterns = {
        "degree_seeking": (r"\b(?:international\s+)?degree students?\b",),
        "exchange": (r"\bexchange students?\b",),
        "visiting": (r"\bvisiting students?\b", r"\bvisiting program participants?\b"),
        "language_program": (r"\b(?:korean )?language program(?: students?)?\b",),
        "short_term": (r"\bshort[- ]term (?:students?|participants?|program)\b",),
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


def _academic_status(context: str) -> tuple[list[str], str | None]:
    exclusions = re.search(r"\bExclusions\s*:(.*)", context, re.IGNORECASE | re.DOTALL)
    if exclusions and re.search(r"expected graduates|leave of absence|completed students|extra semesters", exclusions.group(1), re.IGNORECASE):
        evidence = _evidence((r"\bInternational students studying\b", r"\bEligibility\b"), context)
        return ["enrolled"], evidence

    patterns = {
        "enrolled": (r"\benrolled students?\b", r"\bstudents? (?:who are )?enrolled\b", r"\bcurrently enrolled\b"),
        "leave_of_absence": (r"\bleave of absence\b", r"\bstudents? on leave\b"),
        "completed_coursework": (r"\bcompleted coursework\b", r"\bcompleted students?\b"),
        "graduating": (r"\bexpected graduates?\b", r"\bgraduating students?\b"),
        "admitted_not_enrolled": (r"\bacceptance\b", r"\badmitted students?\b", r"\badmission result page\b"),
    }
    positive = NEGATED.sub(" ", context)  # statuses in an exclusion clause are not constraints
    values = [value for value, value_patterns in patterns.items() if _first_match(value_patterns, positive)]
    matched_patterns = tuple(pattern for value in values for pattern in patterns[value])
    return values, _evidence(matched_patterns, positive) if matched_patterns else None


def _requirements(text: str) -> list[str]:
    patterns = (
        r"\b(?:language school )?attendance rate of less than \d{1,3}%",
        r"\bTOPIK scores? (?:are|is) now higher than [^.\n;]{1,100}",
        r"\bApplicants who [^\n]{0,100}Korean Language Standards\b",
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
TAG_BUCKETS = ("rule_tagged", "rule_unconditioned", "llm_tagged", "llm_unconditioned", "llm_rejected", "llm_errors")
TAG_PROMPT_VERSION = "v2"  # v2: evidence-object example, campus left out (site default/rules)  # bump whenever the fallback prompt below changes


def _apply_llm_fallback(
    condition: ChunkCondition,
    text: str,
    llm: Callable[[str], str],
    trace_details: dict[str, Any] | None,
) -> None:
    prompt = (
        "Which students does this chunk apply to? Tag only constraints the chunk states explicitly.\n"
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
        details.update(status="rejected", reason="no JSON object")
        return
    constraints = parsed.get("constraints")
    evidence = parsed.get("evidence")
    if not isinstance(constraints, dict) or not isinstance(evidence, dict):
        details.update(status="rejected", reason="constraints and evidence must be objects")
        return

    rejected: dict[str, str] = {}
    for attribute, values in constraints.items():
        quote = evidence.get(attribute)
        if attribute not in CONSTRAINT_ATTRIBUTES:
            rejected[str(attribute)] = "unknown attribute"
        elif not isinstance(values, list) or not values or any(value not in VOCABULARY[attribute] for value in values):
            rejected[attribute] = "value outside vocabulary"
        elif not isinstance(quote, str) or not quote:
            rejected[attribute] = "missing evidence quote"
        elif quote not in text:
            rejected[attribute] = "evidence is not an exact substring"
        else:
            condition.constraints[attribute] = list(dict.fromkeys(values))
            condition.extraction_method[attribute] = "llm"
            condition.evidence[attribute] = quote
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

    extractors = {
        "degree_level": _degree_level,
        "year": _year,
        "topik_level": _topik_level,
        "visa": _visa,
        "student_type": _student_type,
        "english_track": _english_track,
        "academic_status": _academic_status,
    }
    for attribute, extractor in extractors.items():
        values, quote = extractor(context)
        if not values:
            continue
        condition.constraints[attribute] = values
        condition.extraction_method[attribute] = "rule"
        if quote and quote in text:
            condition.evidence[attribute] = quote

    condition.requirements = _requirements(text)
    if condition.requirements:
        condition.extraction_method["requirements"] = "rule"
        condition.evidence["requirements"] = condition.requirements[0]

    condition.effective_term, term_quote = _effective_term(context, chunk.get("post_date"))
    if condition.effective_term:
        condition.extraction_method["effective_term"] = "rule"
        if term_quote and term_quote in text:
            condition.evidence["effective_term"] = term_quote

    if llm is not None and not condition.constraints:
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
                  "llm_rejected": {}, "llm_rejected_total": 0, "llm_errors": 0}  # fmt: skip
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
                ask = use_llm and LLM_CUE.search(chunk["text"]) is not None
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
                    else:
                        counts["llm_rejected_total"] += 1
                        reasons = list(fallback.get("rejected_fields", {}).values()) or [fallback.get("reason", fallback.get("status"))]
                        for reason in reasons:
                            counts["llm_rejected"][reason] = counts["llm_rejected"].get(reason, 0) + 1
                    fallback_details.append(details)
                tagged.append(result)
                status = details.get("llm_fallback", {}).get("status")
                self.buckets.append({None: "rule_tagged" if result.constraints else "rule_unconditioned", "accepted": "llm_tagged",
                                     "unconditioned": "llm_unconditioned", "error": "llm_errors"}.get(status, "llm_rejected"))  # fmt: skip
        finally:
            if loop is not None:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
        self.trace_details = {"llm_fallbacks": fallback_details[:50]}
        self.summary = {**counts, "llm": {"enabled": use_llm, "role": "auxiliary", "model": model_name,
                                          "digest": selected.get("digest"), "prompt_version": TAG_PROMPT_VERSION,
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
