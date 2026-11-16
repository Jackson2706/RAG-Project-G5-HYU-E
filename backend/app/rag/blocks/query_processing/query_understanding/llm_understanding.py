"""LLM query understanding: ask the LLM what the student explicitly states about eligibility."""

from __future__ import annotations

import json
import re
from typing import Any

from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import FilterCriteria, QueryAnalysis

ALLOWED_FIELDS = ("campus", "audience", "academic_year", "document_type", "effective_date")
ALLOWED_CAMPUS = {"SEOUL", "ERICA", "ALL"}
ALLOWED_AUDIENCE = {"UNDERGRADUATE", "GRADUATE", "INTERNATIONAL", "EXCHANGE", "FRESHMAN", "SOPHOMORE", "JUNIOR", "SENIOR", "DOMESTIC", "ALL"}
ALLOWED_DOCUMENT_TYPES = {
    "HANDBOOK", "NOTICE", "GUIDE", "STUDENT_GUIDE", "SCHOLARSHIP", "ADMISSION", "COURSE",
    "REGISTRATION", "ORIENTATION", "HOUSING", "DORMITORY", "POLICY", "APPLICATION", "TUITION",
    "WAIVER", "PROGRAM", "ACADEMIC"
}

AUDIENCE_ALIASES = {
    "undergraduate": "UNDERGRADUATE",
    "undergraduate student": "UNDERGRADUATE",
    "grad": "GRADUATE",
    "graduate": "GRADUATE",
    "graduate student": "GRADUATE",
    "international": "INTERNATIONAL",
    "international student": "INTERNATIONAL",
    "exchange": "EXCHANGE",
    "exchange student": "EXCHANGE",
    "freshman": "FRESHMAN",
    "first-year": "FRESHMAN",
    "first year": "FRESHMAN",
    "sophomore": "SOPHOMORE",
    "junior": "JUNIOR",
    "senior": "SENIOR",
    "domestic": "DOMESTIC",
    "domestic student": "DOMESTIC",
    "all": "ALL",
    "all students": "ALL",
}

DOCUMENT_TYPE_ALIASES = {
    "student guide": "STUDENT_GUIDE",
    "guide": "GUIDE",
    "handbook": "HANDBOOK",
    "notice": "NOTICE",
    "scholarship": "SCHOLARSHIP",
    "scholarships": "SCHOLARSHIP",
    "admission": "ADMISSION",
    "course": "COURSE",
    "registration": "REGISTRATION",
    "orientation": "ORIENTATION",
    "housing": "HOUSING",
    "dormitory": "DORMITORY",
    "dorm": "DORMITORY",
    "policy": "POLICY",
    "application": "APPLICATION",
    "tuition": "TUITION",
    "waiver": "WAIVER",
    "program": "PROGRAM",
}


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a", "na"}:
        return None
    return text.strip('"\'')


def _normalize_campus(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    token = text.strip().upper().replace(" ", "")
    if token in {"SEOUL", "ERICA", "ALL"}:
        return token
    for alias, canonical in {"ERICACAMPUS": "ERICA", "SEOULCAMPUS": "SEOUL"}.items():
        if token == alias:
            return canonical
    return None


def _normalize_audience(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    lowered = text.lower().strip()
    if not lowered:
        return None
    for alias, canonical in AUDIENCE_ALIASES.items():
        if lowered == alias:
            return canonical
    for word in ("undergraduate", "graduate", "international", "exchange", "freshman", "sophomore", "junior", "senior", "domestic"):
        if word in lowered:
            return AUDIENCE_ALIASES[word]
    return None


def _normalize_year(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if match:
        return match.group(1)
    return None


def _normalize_document_type(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    lowered = text.lower().strip()
    if not lowered:
        return None
    for alias, canonical in DOCUMENT_TYPE_ALIASES.items():
        if lowered == alias:
            return canonical
    for token in LOWERCASE_DOCUMENT_TYPES:
        if token in lowered:
            return token.upper()
    return None


LOWERCASE_DOCUMENT_TYPES = tuple(sorted({v.lower() for v in ALLOWED_DOCUMENT_TYPES}, key=len, reverse=True))


def _normalize_date(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)
    return None


def _normalize_field(field: str, raw: Any) -> str | None:
    if field == "campus":
        return _normalize_campus(raw)
    if field == "audience":
        return _normalize_audience(raw)
    if field == "academic_year":
        return _normalize_year(raw)
    if field == "document_type":
        return _normalize_document_type(raw)
    if field == "effective_date":
        return _normalize_date(raw)
    return None


class LLMQueryUnderstanding(BaseQueryUnderstanding):
    async def analyze(self, question: str) -> QueryAnalysis:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params.get("model", ""), self.services.settings.ollama_chat_model)

        instruction = (
            "Extract only information explicitly stated in the user's question. "
            "Return one JSON object with exactly these keys: intent, campus, audience, academic_year, "
            "document_type, effective_date. Use null when a value is not explicitly stated. "
            "Do not infer the user's audience or any other missing value. "
            "Allowed campus values: SEOUL, ERICA, ALL. "
            "Allowed audience values: UNDERGRADUATE, GRADUATE, INTERNATIONAL, EXCHANGE, FRESHMAN, "
            "SOPHOMORE, JUNIOR, SENIOR, DOMESTIC, ALL. "
            "academic_year must be a four-digit year. "
            "Allowed document_type values: HANDBOOK, NOTICE, GUIDE, STUDENT_GUIDE, SCHOLARSHIP, "
            "ADMISSION, COURSE, REGISTRATION, ORIENTATION, HOUSING, DORMITORY, POLICY, APPLICATION, "
            "TUITION, WAIVER, PROGRAM, ACADEMIC. effective_date must use YYYY-MM-DD. "
            "Do not include explanations, markdown, or text outside the JSON object."
        )
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": question}
        ]

        options = {
            "temperature": self.params.get("temperature", 0.0),
            "num_predict": self.params.get("max_tokens", 128),
            "num_ctx": 4096,
            "seed": 42,
        }
        text, usage = await ollama.complete(model, messages, options, format="json")
        self.trace_details = {
            "model": model["name"],
            "prompt_tokens": usage.get("prompt_eval_count"),
            "output_tokens": usage.get("eval_count"),
        }

        try:
            payload = text.strip()

            match = re.search(r"\{.*\}", payload, re.DOTALL)
            if match:
                payload = match.group(0)

            if payload.startswith("```"):
                payload = re.sub(r"^```(?:json)?\s*", "", payload, flags=re.IGNORECASE)
                payload = re.sub(r"\s*```\s*$", "", payload)

            obj = json.loads(payload)
            if not isinstance(obj, dict):
                raise ValueError("JSON root is not an object")
            if isinstance(obj.get("criteria"), dict):
                obj = {**obj, **obj["criteria"]}
            intent = _clean_string(obj.get("intent")) or None

            values: dict[str, str | None] = {}
            for field in ALLOWED_FIELDS:
                value = _normalize_field(field, obj.get(field))
                if value is not None:
                    values[field] = value

            if not values:
                self.trace_details["reason"] = "no valid criteria extracted"
                return QueryAnalysis(intent=intent, criteria=FilterCriteria())

            criteria = FilterCriteria(**values)
            self.trace_details["accepted_fields"] = list(values.keys())
            return QueryAnalysis(intent=intent, criteria=criteria)
        except (json.JSONDecodeError, TypeError, ValueError):
            self.trace_details["reason"] = "invalid JSON or no recognizable criteria"
            return QueryAnalysis(intent=None, criteria=FilterCriteria())
