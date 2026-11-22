import json

import pytest

from labeling.drafts import validate_drafts


DOC_ID = "11111111-1111-1111-1111-111111111111"


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _draft(**changes):
    row = {
        "draft_id": "draft-1",
        "slice": "unconditional",
        "campus": "seoul",
        "persona_id": "persona-01",
        "topic_doc_ids": [DOC_ID],
        "question": "Where is the international office?",
        "session_history": [],
        "intended_attributes": ["campus"],
        "intended_answerability": "answerable",
        "why": "A new student needs to find the office.",
        "annotator": "codex:test",
        "origin": "agent_draft",
    }
    row.update(changes)
    return row


@pytest.fixture
def source_files(tmp_path):
    topics = tmp_path / "topics.jsonl"
    personas = tmp_path / "personas.json"
    _write_jsonl(
        topics,
        [
            {
                "doc_id": DOC_ID,
                "site": "seoul",
                "title": "Contact",
                "headings": [],
                "post_date": None,
                "superseded_by": None,
                "file_type": "html",
                "korean_only": False,
            }
        ],
    )
    personas.write_text(
        json.dumps(
            [
                {
                    "persona_id": "persona-01",
                    "gold_profile": {"campus": "seoul"},
                }
            ]
        ),
        encoding="utf-8",
    )
    return topics, personas


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([_draft(persona_id="persona-missing")], "unknown persona_id"),
        ([_draft(topic_doc_ids=["missing-doc"])], "unknown topic doc_id"),
        ([_draft(), _draft()], "duplicate draft_id"),
    ],
)
def test_checker_rejects_bad_references_and_duplicate_ids(
    tmp_path, source_files, rows, message
):
    drafts = tmp_path / "drafts.jsonl"
    _write_jsonl(drafts, rows)

    _, errors = validate_drafts(drafts, *source_files)

    assert any(message in error for error in errors)
