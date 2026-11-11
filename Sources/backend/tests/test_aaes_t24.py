"""T24: tests first for the AAES online steps (aaes_spec.md, "Online steps (P7)"). Written by Claude Code.

Synthetic chunks only. A chunk is the dict `decide` receives from the sufficiency block:
{"id", "doc_id", "condition": ChunkCondition.to_dict(), "status": condition_status, "superseded": bool}.
"""

from __future__ import annotations

import math

import pytest

from app.rag import aaes
from app.rag.applicability import ChunkCondition


def chunk(cid, doc="d1", status="conditioned", superseded=False, **condition):
    condition.setdefault("campus", ["seoul", "erica"] if condition.get("scope") == "national" else ["erica"])
    return {"id": cid, "doc_id": doc, "condition": ChunkCondition(**condition).to_dict(), "status": status, "superseded": superseded}


def profile(question, history=(), remembered=None):
    return aaes.extract_profile(question, history, remembered)


# ---------------------------------------------------------------- step 1: profile


def test_profile_statuses_stated_missing_and_scope_default():
    p = profile("I'm an ERICA undergrad. How many hours can I work part-time?")
    assert p["campus"] == {"values": ["erica"], "status": "stated", "evidence": "ERICA"}
    assert p["degree_level"]["values"] == ["undergraduate"] and p["degree_level"]["status"] == "stated"
    assert p["topik_level"] == {"values": [], "status": "missing", "evidence": ""}
    assert p["academic_status"]["status"] == "scope_default"
    assert "applicant" not in p["academic_status"]["values"]
    assert aaes.known_values(p) == {"campus": ["erica"], "degree_level": ["undergraduate"]}


def test_admission_question_states_applicant():
    p = profile("How do I apply to the graduate school at Seoul campus?")
    assert p["academic_status"]["values"] == ["applicant"] and p["academic_status"]["status"] == "stated"


def test_history_is_remembered_and_the_latest_statement_wins():
    p = profile("Can I work part-time now?", history=["I'm at ERICA on a D-4 visa.", "I changed my visa to D-2 last week."])
    assert p["visa"]["values"] == ["D-2"] and p["visa"]["status"] == "remembered"
    assert p["campus"]["status"] == "remembered"
    p = profile("I'm on a D-2 now, can I work?", history=["I hold a D-4 visa."])
    assert p["visa"] == {"values": ["D-2"], "status": "stated", "evidence": "D-2"}


def test_stale_memory_is_kept_with_status_stale():
    p = profile("Can I work part-time?", remembered={"visa": {"values": ["D-4"], "status": "stale"}})
    assert p["visa"]["values"] == ["D-4"] and p["visa"]["status"] == "stale"
    assert aaes.known_values(p)["visa"] == ["D-4"]


# ---------------------------------------------------------------- step 2: labels and the soft penalty


def test_labels_unknown_is_never_unconditioned_and_campus_always_counts():
    seoul = {"campus": ["seoul"]}
    plain = ChunkCondition(campus=["seoul"]).to_dict()
    assert aaes.label_chunk(plain, "unconditioned", seoul) == "unconditioned"
    assert aaes.label_chunk(plain, "unknown", seoul) == "unknown"
    erica_only = ChunkCondition(campus=["erica"]).to_dict()
    assert aaes.label_chunk(erica_only, "unknown", seoul) == "conflicting"
    assert aaes.label_chunk(erica_only, "unconditioned", seoul) == "conflicting"
    national = ChunkCondition(scope="national", campus=["seoul", "erica"]).to_dict()
    assert aaes.label_chunk(national, "unconditioned", seoul) == "unconditioned"


def test_labels_scope_default_and_condition_sets():
    applicant_only = ChunkCondition(campus=["seoul"], constraints={"academic_status": ["applicant"]}).to_dict()
    enrolled_only = ChunkCondition(campus=["seoul"], constraints={"academic_status": ["enrolled"]}).to_dict()
    assert aaes.label_chunk(applicant_only, "conditioned", {"campus": ["seoul"]}) == "conflicting"
    assert aaes.label_chunk(enrolled_only, "conditioned", {"campus": ["seoul"]}) == "open"
    hiea = ChunkCondition(campus=["seoul"], any_of=[{"topik_level": ["1", "2", "3", "4", "5", "6"]}, {"english_track": ["yes"]}]).to_dict()
    english_track = {"campus": ["seoul"], "english_track": ["yes"], "topik_level": ["none"]}
    assert aaes.label_chunk(hiea, "conditioned", english_track) == "compatible"
    korean_track = {"campus": ["seoul"], "english_track": ["no"], "topik_level": ["none"]}
    assert aaes.label_chunk(hiea, "conditioned", korean_track) == "conflicting"


def test_soft_penalty_only_lowers_conflicting_and_outdated():
    assert aaes.penalized_score(2.0, "compatible", False, lam=1.5, mu=0.5) == 2.0
    assert aaes.penalized_score(2.0, "unknown", False, lam=1.5, mu=0.5) == 2.0
    assert aaes.penalized_score(2.0, "conflicting", False, lam=1.5, mu=0.5) == 0.5
    assert aaes.penalized_score(2.0, "open", True, lam=1.5, mu=0.5) == 1.5
    assert aaes.penalized_score(2.0, "conflicting", True, lam=1.5, mu=0.5) == 0.0


# ---------------------------------------------------------------- steps 3 + 4: the three spec examples


def _part_time_chunks():
    """ERICA part-time work table: the cap depends on the Korean-language level, for every year."""
    years = ["1", "2", "3", "4"]
    return [
        chunk("cap25", scope="national", constraints={"degree_level": ["undergraduate"], "year": years, "topik_level": ["3", "4", "5", "6"]}),
        chunk("cap10", scope="national", constraints={"degree_level": ["undergraduate"], "year": years, "topik_level": ["none", "1", "2"]}),
    ]


def test_erica_part_time_work_branches_on_language_status_only():
    p = profile("I'm an ERICA undergrad. How many hours can I work part-time?")
    chunks = _part_time_chunks()
    ig_year, outcomes_year = aaes.information_gain("year", chunks, p)
    assert ig_year == 0 and len(set(map(frozenset, outcomes_year.values()))) == 1
    ig_topik, outcomes_topik = aaes.information_gain("topik_level", chunks, p)
    # 7 TOPIK values: 4 map to {cap25}, 3 to {cap10}  ->  H(4/7, 3/7)
    assert ig_topik == pytest.approx(-(4 / 7) * math.log2(4 / 7) - (3 / 7) * math.log2(3 / 7))
    assert outcomes_topik["3"] == ["cap25"] and outcomes_topik["none"] == ["cap10"]
    d = aaes.decide(chunks, p)
    assert d["action"] == "CONDITIONAL"
    assert d["branch_attributes"] == ["topik_level"]
    assert d["branches"]["topik_level"]["ig"] == pytest.approx(ig_topik)
    assert "year" not in d["branch_attributes"] and "campus" not in d["branch_attributes"]
    assert d["unknown_condition_evidence"] is False


def test_unconditioned_fee_answers():
    p = profile("How much is the dormitory application fee at ERICA?")
    d = aaes.decide([chunk("fee", status="unconditioned")], p)
    assert d["action"] == "ANSWER" and d["branch_attributes"] == [] and d["support"] == ["fee"]
    assert d["unknown_condition_evidence"] is False
    assert aaes.with_caveat("It is 30,000 won [E1].", d) == "It is 30,000 won [E1]."


def test_seoul_student_asking_for_the_ansan_office_abstains():
    p = profile("I'm a Seoul campus student. Where is the international office in Ansan?")
    d = aaes.decide([chunk("ansan_office", status="unconditioned", campus=["erica"])], p)
    assert d["action"] == "ABSTAIN" and d["reason"] == "not_applicable" and d["support"] == []
    message = aaes.render_action(d, p)
    assert "Seoul" in message and "OIA" in message


def test_no_evidence_abstains():
    d = aaes.decide([], profile("Is there a bus to Jeju?"))
    assert d["action"] == "ABSTAIN" and d["reason"] == "no_evidence"


# ---------------------------------------------------------------- policy table: every action


def test_clarify_when_more_than_three_branches():
    p = profile("Which orientation session should I attend at ERICA?")
    chunks = [chunk(f"y{y}", constraints={"degree_level": ["undergraduate"], "year": [y]}) for y in "1234"]
    p["degree_level"] = {"values": ["undergraduate"], "status": "stated", "evidence": "undergrad"}
    d = aaes.decide(chunks, p)
    assert d["action"] == "CLARIFY" and d["clarify_attribute"] == "year"
    message = aaes.render_action(d, p)
    assert message.count("?") == 1 and "year" in message.lower()


def test_clarify_when_branches_need_different_procedures():
    p = profile("How do I extend my alien registration card appointment with the university office?")
    chunks = [chunk("seoul_proc", doc="seoul_doc", campus=["seoul"]), chunk("erica_proc", doc="erica_doc", campus=["erica"])]
    d = aaes.decide(chunks, p)
    assert d["branch_attributes"] == ["campus"]
    assert d["action"] == "CLARIFY" and d["clarify_attribute"] == "campus"


def test_conditional_on_campus_when_both_branches_share_one_document():
    p = profile("When is the tuition payment period?")
    chunks = [chunk("seoul_row", doc="calendar", campus=["seoul"]), chunk("erica_row", doc="calendar", campus=["erica"])]
    d = aaes.decide(chunks, p)
    assert d["action"] == "CONDITIONAL" and d["branch_attributes"] == ["campus"]


def test_scope_default_never_branches_on_applicant():
    p = profile("I'm at Seoul. How do I get a certificate of enrollment?")
    chunks = [chunk("enrolled", doc="cert", campus=["seoul"], constraints={"academic_status": ["enrolled"]}),
              chunk("leave", doc="cert", campus=["seoul"], constraints={"academic_status": ["leave_of_absence"]})]  # fmt: skip
    d = aaes.decide(chunks, p)
    assert d["action"] == "CONDITIONAL" and d["branch_attributes"] == ["academic_status"]
    assert "applicant" not in d["branches"]["academic_status"]["outcomes"]


def test_confirm_when_a_stale_value_decides_the_answer():
    p = profile("Can I work part-time?", remembered={"campus": {"values": ["erica"], "status": "remembered"},
                                                     "visa": {"values": ["D-4"], "status": "stale"}})  # fmt: skip
    chunks = [chunk("d2", scope="national", constraints={"visa": ["D-2"]}), chunk("d4", scope="national", constraints={"visa": ["D-4"]})]
    d = aaes.decide(chunks, p)
    assert d["action"] == "CONFIRM" and d["confirm_attribute"] == "visa"
    message = aaes.render_action(d, p)
    assert "D-4" in message and message.count("?") == 1


def test_stale_value_that_does_not_matter_answers():
    p = profile("Can I work part-time?", remembered={"visa": {"values": ["D-4"], "status": "stale"}})
    d = aaes.decide([chunk("any", scope="national", status="unconditioned")], p)
    assert d["action"] == "ANSWER" and d["confirm_attribute"] is None


def test_always_clarify_variant_a3():
    p = profile("I'm an ERICA undergrad. How many hours can I work part-time?")
    chunks = [chunk("only", scope="national", constraints={"degree_level": ["undergraduate"], "year": ["1", "2", "3", "4"]})]
    assert aaes.decide(chunks, p)["action"] == "ANSWER"  # year does not change the answer
    assert aaes.decide(chunks, p, policy="always_clarify")["action"] == "CLARIFY"


# ---------------------------------------------------------------- unknown condition status (A23)


def test_unknown_evidence_still_answers_with_the_caveat_and_flag():
    p = profile("What documents do I need for the ERICA dormitory?")
    d = aaes.decide([chunk("dorm", status="unknown")], p)
    assert d["action"] == "ANSWER" and d["unknown_condition_evidence"] is True
    assert aaes.with_caveat("Bring your passport [E1].", d) == (
        "Bring your passport [E1].\n\nThis may depend on your situation; please confirm with the OIA office.")
    assert aaes.UNKNOWN_CAVEAT == "This may depend on your situation; please confirm with the OIA office."


def test_unknown_conflicting_chunk_is_not_support():
    p = profile("I'm at Seoul. What documents do I need for the dormitory?")
    d = aaes.decide([chunk("seoul_dorm", campus=["seoul"], status="unconditioned"), chunk("erica_dorm", status="unknown")], p)
    assert d["support"] == ["seoul_dorm"] and d["unknown_condition_evidence"] is False


# ---------------------------------------------------------------- temporal rule (A6 switches it off)


def test_outdated_support_is_dropped_when_a_newer_version_exists():
    p = profile("How much is the national health insurance premium?")
    chunks = [chunk("nhi_2025", doc="old", scope="national", status="unconditioned", superseded=True),
              chunk("nhi_2026", doc="new", scope="national", status="unconditioned")]  # fmt: skip
    assert aaes.decide(chunks, p)["support"] == ["nhi_2026"]
    assert aaes.decide(chunks, p, temporal=False)["support"] == ["nhi_2025", "nhi_2026"]
    assert aaes.decide(chunks[:1], p)["support"] == ["nhi_2025"]  # only an old version: still used
