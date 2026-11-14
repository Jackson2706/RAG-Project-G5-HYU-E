"""AG "AAES guard" (amendment A35 Step 3). Written by Claude Code before the guard itself. The LLM calls are mocked:
`_ask` gets (kind, question, chunk_ids, extra) and the fake answers from a small script per test."""

from __future__ import annotations

import asyncio
import json

from app.rag.aaes import answer_parts, same_answer
from app.rag.blocks.evidence.evidence_sufficiency.aaes_guard import AAESGuard
from app.rag.schemas import Evidence


def ev(chunk_id: str, doc_id: str, text: str, campus: list[str], constraints: dict | None = None) -> Evidence:
    condition = {"campus": campus, "scope": "national" if len(campus) == 2 else "campus", "constraints": constraints or {}, "any_of": []}
    return Evidence(rank=1, chunk_id=chunk_id, doc_id=doc_id, score=1.0, text=text, title="t", source_uri="u",
                    applicability={"condition": condition, "condition_status": "rule_tagged"})  # fmt: skip


class Fake:
    """Scripted answers: yes/no per chunk set, a short answer per chunk set, and the verification quotes."""

    def __init__(self, sufficient: dict, values: dict, quotes: dict):
        self.sufficient, self.values, self.quotes, self.calls = sufficient, values, quotes, []

    async def __call__(self, kind, question, chunk_ids, extra="", texts=None):
        self.calls.append(kind)
        key = tuple(chunk_ids)
        if kind == "branch_answers":
            return self.sufficient.get(key, "no")
        if kind == "extract":
            return self.values[key]
        a_part, _, b_part = extra.partition("\n\nB:\n")  # the guard says which set is A; quote each from its own set
        ordered = sorted(self.quotes.values(), key=lambda q: q not in a_part)
        if ordered[0] in b_part and ordered[1] in a_part:
            ordered.reverse()
        return json.dumps({"a": ordered[0], "b": ordered[1]})


def guard(fake: Fake) -> AAESGuard:
    block = AAESGuard({"model": "", "temperature": 0.0, "max_tokens": 64}, services=None)  # type: ignore[arg-type]
    block._ask = fake  # type: ignore[method-assign]
    return block


HOURS_HIGH = "Bachelor's year 1-2 with Korean level 3: Permitted Hours / Weekdays: 30 hours"
HOURS_LOW = "Bachelor's year 1-2 without the Korean level: Permitted Hours / Weekdays: 10 hours"


def test_erica_part_time_hours_by_topik_fires_conditional():
    evidence = [ev("hi", "D1", HOURS_HIGH, ["erica"], {"topik_level": ["3", "4", "5", "6"]}),
                ev("lo", "D1", HOURS_LOW, ["erica"], {"topik_level": ["none", "1", "2"]})]  # fmt: skip
    fake = Fake({("hi",): "yes", ("lo",): "yes"}, {("hi",): "30 hours on weekdays", ("lo",): "10 hours on weekdays"},
                {"a": "Weekdays: 30 hours", "b": "Weekdays: 10 hours"})  # fmt: skip
    d = asyncio.run(guard(fake).check("I'm at ERICA. How many hours can I work part time?", evidence))
    assert d.action == "CONDITIONAL" and d.signals["guard"]["fired"] is True
    assert set(d.evidence_ids) == {"hi", "lo"} and "TOPIK level" in d.prompt_note


def test_same_fee_on_seoul_and_erica_pages_does_not_fire():
    evidence = [ev("s", "DS", "Group insurance: KRW 25,000 per semester", ["seoul"]),
                ev("e", "DE", "KRW 25,000 (same premium for undergraduate and graduate schools)", ["erica"])]  # fmt: skip
    fake = Fake({("s",): "yes", ("e",): "yes"}, {("s",): "KRW 25,000", ("e",): "25,000 won"}, {})
    d = asyncio.run(guard(fake).check("How much is the group insurance?", evidence))
    assert d.action is None and d.sufficient and d.evidence_ids is None and d.message is None  # R16's reply, unchanged
    assert d.signals["guard"]["fired"] is False and "verify" not in fake.calls


def test_one_empty_branch_does_not_fire():
    evidence = [ev("e", "DE", "ERICA dormitory fee: KRW 1,168,000", ["erica"]), ev("x", "DX", "unrelated", ["seoul", "erica"])]
    fake = Fake({}, {}, {})
    d = asyncio.run(guard(fake).check("How much is the dormitory fee?", evidence))
    assert d.action is None and d.signals["guard"]["fired"] is False  # campus is no candidate: only ERICA is scoped


def test_ten_vs_twenty_hours_are_two_values():
    assert not same_answer(answer_parts("up to 10 hours per week"), answer_parts("up to 20 hours per week"))
    assert same_answer(answer_parts("KRW 25,000"), answer_parts("25,000 won"))
    assert not same_answer(answer_parts("Yes"), answer_parts("No"))
    assert same_answer(answer_parts("apply online through the portal"), answer_parts("You apply through the online portal"))
    assert answer_parts("NONE") is None


def test_unverifiable_quotes_do_not_fire():
    evidence = [ev("hi", "D1", HOURS_HIGH, ["erica"], {"topik_level": ["3", "4", "5", "6"]}),
                ev("lo", "D1", HOURS_LOW, ["erica"], {"topik_level": ["none", "1", "2"]})]  # fmt: skip
    fake = Fake({("hi",): "yes", ("lo",): "yes"}, {("hi",): "30 hours", ("lo",): "10 hours"},
                {"a": "Weekdays: 40 hours", "b": "Weekdays: 10 hours"})  # "40 hours" is not in the evidence
    d = asyncio.run(guard(fake).check("I'm at ERICA. How many hours can I work part time?", evidence))
    assert d.action is None and d.signals["guard"]["fired"] is False and d.signals["guard"]["stop"] == "quotes_not_verified"
