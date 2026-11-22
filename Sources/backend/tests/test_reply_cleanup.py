"""Deck v7 reply cleanup: internal markers removed, "ask the office" cases merged. Written by Claude Code."""

from __future__ import annotations

import pytest

from app.rag.reply_cleanup import OTHER_CASES, clean_reply


@pytest.mark.parametrize("raw, shown", [
    ("You must register by March 3 [E1]. [INSUFFICIENT_CONTEXT]", "You must register by March 3 [E1]."),
    ("Visit the office [E2]. INSUFFICIENT_CONTEXT The rest is unknown.", "Visit the office [E2]. The rest is unknown."),
    ("Ask the OIA office. [No Evidence Provided]", "Ask the OIA office."),
    ("Fees are listed [E1][E3] [no evidence].", "Fees are listed [E1][E3]."),
    ("See the [application form](https://example.org) [E1].", "See the [application form](https://example.org) [E1]."),  # links stay
    ("Choose [Seoul] or [ERICA] on the form [E1].", "Choose [Seoul] or [ERICA] on the form [E1]."),  # ordinary brackets stay
])  # fmt: skip
def test_internal_markers_are_removed(raw, shown):
    assert clean_reply(raw, "ANSWER") == shown


def test_ask_only_cases_merge_into_one_line_and_cases_with_facts_stay():
    raw = ("If you are at the Seoul campus with an enrolled status, you should ask the OIA office. [No Evidence Provided]\n"
           "If you are at the ERICA campus with a leave of absence status, you must register for group insurance [E1].\n"
           "If you are at the ERICA campus and enrolled, the fee is 25,000 Won [E2].\n"
           "If you are at the Seoul campus with a leave of absence status, you should ask the OIA office.")
    assert clean_reply(raw, "CONDITIONAL") == (
        "If you are at the ERICA campus with a leave of absence status, you must register for group insurance [E1].\n"
        "If you are at the ERICA campus and enrolled, the fee is 25,000 Won [E2].\n\n" + OTHER_CASES)


def test_one_case_with_facts_keeps_its_ask_cases_without_markers():
    raw = ("If you are at Seoul, you should ask the OIA office. [No Evidence Provided]\n"
           "If you are at ERICA, you must register for group insurance [E1].")
    assert clean_reply(raw, "CONDITIONAL") == "If you are at Seoul, you should ask the OIA office.\nIf you are at ERICA, you must register for group insurance [E1]."


def test_cases_in_one_paragraph_and_a_lead_in_are_handled():
    raw = ("It depends on your campus. If you are at Seoul, you apply online [E1]. If you are a graduate student, use the form [E2]. "
           "If you are at ERICA, the evidence does not detail this, so please contact the OIA office.")
    assert clean_reply(raw, "CONDITIONAL") == ("It depends on your campus. If you are at Seoul, you apply online [E1]. "
                                               "If you are a graduate student, use the form [E2].\n\n" + OTHER_CASES)


@pytest.mark.parametrize("raw", [
    "If you are at Seoul, apply online [E1].\nIf you are at ERICA, apply at the office [E2].",  # every case has facts
    "If you are at Seoul, ask the OIA office.\nIf you are at ERICA, ask the OIA office.",  # no case with facts: keep the text
])  # fmt: skip
def test_per_case_text_without_a_merge_is_unchanged(raw):
    assert clean_reply(raw, "CONDITIONAL") == raw


def test_only_per_case_answers_are_merged():
    raw = "If you are at Seoul, apply online [E1].\nIf you are at ERICA, ask the OIA office."
    assert clean_reply(raw, "ANSWER") == raw and clean_reply(raw, None) == raw
