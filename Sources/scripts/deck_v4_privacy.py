"""Deck v4 Task 5: does the HYU index hold personal data? Read-only scan of index r5 chunk texts (counts, masked examples).

Run from Sources/:  python scripts/deck_v4_privacy.py   -> Report/slides/deck_v4/privacy_scan.json
Patterns: e-mail addresses (unmasked), the mask "[email]", phone numbers, and person-name cues (titles before a
capitalised name, "My name is"). Names are a heuristic: the counts are candidates, not confirmed people.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402

PATTERNS = {
    "email_unmasked": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "email_masked": re.compile(r"\[email\]|\[EMAIL\]|\[e-mail\]"),
    "phone": re.compile(r"(?<!\d)(?:\+82[-\s]?|0)\d{1,2}[-.\s)]\d{3,4}[-.\s]\d{4}(?!\d)"),
    "name_title": re.compile(r"\b(?:Prof\.|Professor|Dr\.|Mr\.|Ms\.|Mrs\.|Dean|Director|Manager)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"),
    "name_intro": re.compile(r"\bMy name is\s+[A-Z][a-z]+"),
}


def mask(text: str) -> str:
    """Keep the first character of each word: 'Professor Kim Minsu' -> 'P******** K** M****'."""
    return re.sub(r"\w+", lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)


def main() -> int:
    db = Database.connect(get_settings()).for_index("hyu_20261110_97dc1269_r5")
    counts, chunks_with, examples = Counter(), Counter(), {k: [] for k in PATTERNS}
    total = 0
    for c in db.chunks.find({}, {"_id": 0, "text": 1}):
        total += 1
        for name, pattern in PATTERNS.items():
            hits = pattern.findall(c.get("text") or "")
            counts[name] += len(hits)
            chunks_with[name] += bool(hits)
            for h in hits[: 1]:
                if len(examples[name]) < 5:
                    examples[name].append(mask(h))
    out = {"index": "hyu_20261110_97dc1269_r5", "chunks": total, "matches": dict(counts), "chunks_with_match": dict(chunks_with), "masked_examples": examples}
    path = REPORT_DIR / "slides" / "deck_v4" / "privacy_scan.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    assert mask("Professor Kim") == "P******** K**"
    raise SystemExit(main())
