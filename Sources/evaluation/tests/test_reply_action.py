"""Evaluator v2 rules (amendment A34). The model part needs Ollama and is not unit-tested."""

from evaluation.reply_action import parse_label, rule_label


def test_templates_and_case_lines():
    assert rule_label("The answer depends on your campus. Which applies to you: Seoul or ERICA?") == "clarify"
    assert rule_label("Earlier you said your visa is D-2. Is that still correct?") == "clarify"
    assert rule_label("The official pages I found do not apply to you (they are for another campus). Please contact x.") == "abstain"
    assert rule_label("I could not find enough information in the indexed HYU documents to answer this question. See x.") == "abstain"
    assert rule_label("If you are at Seoul, pay A [E1].\n\nIf you are at ERICA, pay B [E2].") == "conditional_answer"
    assert rule_label("*   **If you are** a master student: x\n*   **If you are** a PhD student: y") == "conditional_answer"
    assert rule_label("Yes. If you are late, ask the office.") is None  # one case line is not a conditional answer
    assert rule_label("Re-registration runs from January 5 to 16 [E2].") is None


def test_parse_label():
    assert parse_label("conditional_answer") == "conditional_answer"
    assert parse_label(" Clarify.") == "clarify"
    assert parse_label("Label: abstain") == "abstain"
    assert parse_label("I think") is None
