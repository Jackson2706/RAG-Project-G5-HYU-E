"""Check the T13 persona set against applicability vocabulary v1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import DATA_DIR
from app.rag.applicability import VOCABULARY

PERSONAS_PATH = DATA_DIR / "HYU" / "labels" / "personas.json"
LOW_TOPIK = {"none", "1", "2"}
GRADUATE_LEVELS = {"master", "doctoral"}
VISA_QUESTION_TYPES = {"D-2", "D-4", "D-10"}
REQUIRED_UPDATES = {
    ("visa", "D-4", "D-2"),
    ("academic_status", "enrolled", "completed_coursework"),
    ("korean_standard", "fail", "pass"),
}


def load_personas(path: Path = PERSONAS_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("personas.json must contain a list")
    return data


def _ids(personas: list[dict], predicate) -> list[str]:
    matches = []
    for persona in personas:
        if not isinstance(persona, dict) or not isinstance(persona.get("gold_profile"), dict):
            continue
        if predicate(persona["gold_profile"]):
            matches.append(str(persona.get("persona_id", "<missing>")))
    return matches


def validate_personas(personas: list[dict]) -> list[str]:
    errors: list[str] = []
    if not 10 <= len(personas) <= 12:
        errors.append(f"expected 10-12 personas, found {len(personas)}")

    seen_ids: set[str] = set()
    update_owners: dict[tuple[str, str, str], set[str]] = {transition: set() for transition in REQUIRED_UPDATES}
    personas_with_updates: set[str] = set()

    for index, persona in enumerate(personas):
        if not isinstance(persona, dict):
            errors.append(f"row {index + 1}: must be an object")
            continue
        label = str(persona.get("persona_id") or f"row {index + 1}")
        persona_id = persona.get("persona_id")
        if not isinstance(persona_id, str) or not persona_id.strip():
            errors.append(f"{label}: persona_id must be a non-empty string")
        elif persona_id in seen_ids:
            errors.append(f"{label}: persona_id must be unique")
        else:
            seen_ids.add(persona_id)
        if not isinstance(persona.get("name"), str) or not persona["name"].strip():
            errors.append(f"{label}: name must be a non-empty role")
        description = persona.get("description")
        if not isinstance(description, str) or not description.strip() or "\n" in description:
            errors.append(f"{label}: description must be one non-empty line")

        profile = persona.get("gold_profile")
        if not isinstance(profile, dict):
            errors.append(f"{label}: gold_profile must be an object")
            continue
        expected = set(VOCABULARY) - {"year"}
        if profile.get("degree_level") == "undergraduate":
            expected.add("year")
        missing = sorted(expected - profile.keys())
        unknown = sorted(profile.keys() - set(VOCABULARY))
        if missing:
            errors.append(f"{label}: gold_profile is missing {', '.join(missing)}")
        if unknown:
            errors.append(f"{label}: gold_profile has unknown attributes {', '.join(unknown)}")
        if profile.get("degree_level") != "undergraduate" and "year" in profile:
            errors.append(f"{label}: year is only valid for undergraduates")
        for attribute, value in profile.items():
            if attribute in VOCABULARY and (not isinstance(value, str) or value not in VOCABULARY[attribute]):
                errors.append(f"{label}: {attribute} value {value!r} is outside vocabulary v1")

        updates = persona.get("updates", [])
        if not isinstance(updates, list):
            errors.append(f"{label}: updates must be a list")
            continue
        if updates:
            personas_with_updates.add(label)
        for update_index, update in enumerate(updates):
            update_label = f"{label}: updates[{update_index}]"
            if not isinstance(update, dict):
                errors.append(f"{update_label} must be an object")
                continue
            missing_update = {"attribute", "from", "to", "why"} - update.keys()
            if missing_update:
                errors.append(f"{update_label} is missing {', '.join(sorted(missing_update))}")
                continue
            attribute = update["attribute"]
            if attribute not in VOCABULARY:
                errors.append(f"{update_label} has unknown attribute {attribute!r}")
                continue
            for field in ("from", "to"):
                if update[field] not in VOCABULARY[attribute]:
                    errors.append(f"{update_label} {field} value {update[field]!r} is outside vocabulary v1")
            if update["from"] == update["to"]:
                errors.append(f"{update_label} must change the value")
            if profile.get(attribute) != update["from"]:
                errors.append(f"{update_label} from value must match gold_profile")
            if not isinstance(update["why"], str) or not update["why"].strip():
                errors.append(f"{update_label} why must be a non-empty string")
            transition = (attribute, update["from"], update["to"])
            if transition in update_owners:
                update_owners[transition].add(label)

    minimums = [
        (len(_ids(personas, lambda p: p.get("english_track") == "yes" and p.get("topik_level") in LOW_TOPIK)) >= 2,
         "need at least 2 English-track personas with low or no TOPIK"),
        (len(_ids(personas, lambda p: p.get("campus") == "erica" and p.get("visa") in VISA_QUESTION_TYPES)) >= 2,
         "need at least 2 ERICA personas with D-2, D-4, or D-10 visa questions"),
        (bool(_ids(personas, lambda p: p.get("academic_status") == "applicant")), "need at least 1 applicant"),
        (bool(_ids(personas, lambda p: p.get("academic_status") == "admitted_not_enrolled" and p.get("korean_standard") == "fail")),
         "need at least 1 admitted student with korean_standard fail"),
        (bool(_ids(personas, lambda p: p.get("academic_status") == "completed_coursework")), "need at least 1 completed-coursework persona"),
        (bool(_ids(personas, lambda p: p.get("degree_level") in GRADUATE_LEVELS)), "need at least 1 graduate persona"),
    ]
    errors.extend(message for passed, message in minimums if not passed)

    for value in VOCABULARY["campus"]:
        if not _ids(personas, lambda p, value=value: p.get("campus") == value):
            errors.append(f"campus value {value!r} has no persona")
    for attribute in ("degree_level", "student_type"):
        for value in VOCABULARY[attribute]:
            if not _ids(personas, lambda p, attribute=attribute, value=value: p.get(attribute) == value):
                errors.append(f"{attribute} value {value!r} has no persona")
    if len(personas_with_updates) < 3:
        errors.append("at least 3 personas must have updates")
    for transition, owners in update_owners.items():
        if not owners:
            errors.append(f"missing update {transition[0]}: {transition[1]} -> {transition[2]}")
    if len(set().union(*update_owners.values())) < 3:
        errors.append("the 3 required updates must belong to different personas")
    return errors


def coverage_lines(personas: list[dict]) -> list[str]:
    lines = ["attribute\tvalue\tpersona_ids"]
    for attribute, values in VOCABULARY.items():
        for value in values:
            ids = _ids(personas, lambda p, attribute=attribute, value=value: p.get(attribute) == value)
            lines.append(f"{attribute}\t{value}\t{', '.join(ids) if ids else '-'}")
    return lines


def main() -> int:
    try:
        personas = load_personas()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print("\n".join(coverage_lines(personas)))
    errors = validate_personas(personas)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
