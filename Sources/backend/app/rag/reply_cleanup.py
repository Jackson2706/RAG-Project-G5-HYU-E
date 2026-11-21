"""Reply cleanup (deck v7): writer post-processing for the text shown to students.

1. Internal markers the 4B writer sometimes leaves in the text are removed: INSUFFICIENT_CONTEXT (bare or bracketed)
   and bracketed notes about evidence such as "[No Evidence Provided]" or "[no evidence]". [E#] citations and
   markdown links stay.
2. In an answer per case, every case that only tells the student to ask the office (no [E#] citation) is merged
   into one final line, "For other cases, please ask the OIA office of your campus." Cases with facts are unchanged.

Behind the `clean_reply` flag: on in the app (settings), off in run_rag's default, so evaluation runs are unchanged.
"""

from __future__ import annotations

import re

OTHER_CASES = "For other cases, please ask the OIA office of your campus."
MARKER = re.compile(  # [CODE_WORDS] (upper case with an underscore), or a bracketed note about evidence; never [E#] or a link
    r"\s*\[(?!E\d+\])(?:[A-Z]+(?:_[A-Z]+)+|(?i:[^\[\]\n]{0,40}\b(?:evidence|context|information|insufficient|source|citation)\b[^\[\]\n]{0,40}))\](?!\()"
    r"|\s*\bINSUFFICIENT_CONTEXT\b"
)
CASE_START = re.compile(r"(?:(?<=^)|(?<=\n)|(?<=[.!?]\s)|(?<=[.!?]\]\s))(?=(?:[-*]\s+)?\**If you\b)")
ASK_ONLY = re.compile(r"\b(ask|contact|check with|confirm with|reach out to)\b|\bno (?:specific )?information\b|\bnot (?:detail|specif|provid|availab|mention)", re.IGNORECASE)
CITATION = re.compile(r"\[E\d+\]")


def strip_markers(text: str) -> str:
    text = MARKER.sub("", text)
    return re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()


def merge_ask_only_cases(text: str) -> str:
    """Per-case answers: drop cases that only say "ask the office" and add one closing line instead."""
    parts = CASE_START.split(text)
    prefix, cases = (parts[0], parts[1:]) if parts and not parts[0].lstrip(" -*").startswith("If you") else ("", parts)
    asks = [c for c in cases if not CITATION.search(c) and ASK_ONLY.search(c)]
    kept = [c for c in cases if c not in asks]
    if not asks or not kept:  # nothing to merge, or no case with facts left: keep the writer's text
        return text
    body = (prefix + "".join(kept)).rstrip()
    return f"{body}\n\n{OTHER_CASES}"


def clean_reply(answer: str, action: str | None) -> str:
    text = strip_markers(answer)
    return merge_ask_only_cases(text) if action == "CONDITIONAL" else text
