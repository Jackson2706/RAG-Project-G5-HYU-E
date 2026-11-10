"""Answer-quality metrics that need REFERENCE answers or labels (manually annotated cases only).

BEIR qrels say which documents are relevant; they are not reference answers. These functions are
only applied to annotated cases (Sources/data/HYU/labels/legacy/); otherwise results are NOT_APPLICABLE.
"""

from __future__ import annotations

import re
import string
from collections import Counter


def normalize_answer(text: str) -> str:
    """SQuAD normalization: lowercase, remove punctuation, articles and extra spaces."""
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(prediction: str, reference: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))


def token_f1(prediction: str, reference: str) -> float:
    pred, ref = normalize_answer(prediction).split(), normalize_answer(reference).split()
    common = sum((Counter(pred) & Counter(ref)).values())
    if not pred or not ref:
        return float(pred == ref)
    if common == 0:
        return 0.0
    precision, recall = common / len(pred), common / len(ref)
    return 2 * precision * recall / (precision + recall)


def abstention_correct(outcome: str, expected_behavior: str) -> bool:
    """expected_behavior "answer" or "abstain"; outcome "answered" or "insufficient_context"."""
    return (outcome == "insufficient_context") == (expected_behavior == "abstain")
