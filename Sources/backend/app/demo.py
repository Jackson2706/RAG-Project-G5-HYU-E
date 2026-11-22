"""Demo cases (P8D T37): 8-10 labeled cases from the frozen DEV split, never test (AGENTS.md "UI and demo rules").

GET /api/demo/cases lists them; a chat request with `demo_case_id` gets the case's oracle inputs, which the oracle
presets need (G1 gold evidence, A2 stated profile). Without a demo case those presets return HTTP 422 with a reason.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import DATA_DIR
from app.rag.snapshot import snapshot_dir

DEMO_PATH = DATA_DIR / "HYU" / "labels" / "demo_cases.jsonl"
PUBLIC = ("case_id", "slice", "question", "stated_profile", "expected_behavior", "story")
ORACLE_METHODS = ("oracle_profile", "oracle_evidence")


def needs_oracle(stages: dict) -> bool:
    return any((choice or {}).get("method") in ORACLE_METHODS for choice in stages.values())


def load_demo_cases(path: Path | None = None) -> list[dict]:
    """The demo cases; [] if the file does not exist yet (before the G4 freeze). A test case is refused."""
    path = path or DEMO_PATH
    if not path.is_file():
        return []
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for case in cases:
        if case.get("split") != "dev":
            raise ValueError(f"demo case {case.get('case_id')} is not from the dev split")
    return cases


def public_view(case: dict) -> dict:
    """What the picker shows: no gold evidence; earlier user turns as plain text for the chat history."""
    history = [t["text"] for t in case.get("session_history") or [] if t.get("role", "user") == "user"]
    return {**{k: case.get(k) for k in PUBLIC}, "history": history}


@lru_cache(maxsize=2)
def _documents(snapshot_id: str) -> dict[str, dict]:
    with (snapshot_dir(snapshot_id) / "documents.jsonl").open(encoding="utf-8") as handle:
        return {row["doc_id"]: row for row in map(json.loads, handle)}


def oracle_for(case: dict, documents: dict[str, dict] | None = None) -> dict:
    """The labeled inputs the oracle methods read: A2 the stated profile, G1 the gold spans as Evidence dicts.
    A gold chunk id is gold:<snapshot doc_id>:<start>-<end>, so the metrics can map it back to the label span."""
    documents = documents if documents is not None else _documents(case["snapshot_id"])
    evidence = []
    for rank, span in enumerate(case["gold_evidence"], start=1):
        doc, start, end = documents[span["doc_id"]], span["char_start"], span["char_end"]
        evidence.append({"rank": rank, "chunk_id": f"gold:{span['doc_id']}:{start}-{end}", "doc_id": span["doc_id"], "score": 1.0,
                         "text": doc["text"][start:end], "title": doc.get("title") or "", "source_uri": doc.get("source_uri") or ""})
    return {"profile": dict(case["stated_profile"]), "evidence": evidence}
