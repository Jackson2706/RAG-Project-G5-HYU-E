from __future__ import annotations

from copy import deepcopy

from labeling.personas import load_personas, validate_personas


def test_real_personas_pass():
    assert validate_personas(load_personas()) == []


def test_personas_reject_value_outside_vocabulary():
    personas = load_personas()
    personas[0]["gold_profile"]["campus"] = "mars"
    assert any("outside vocabulary v1" in error for error in validate_personas(personas))


def test_personas_reject_missing_profile_attribute():
    personas = load_personas()
    personas[0]["gold_profile"].pop("visa")
    assert any("gold_profile is missing visa" in error for error in validate_personas(personas))


def test_personas_reject_set_without_english_track_students():
    personas = deepcopy(load_personas())
    for persona in personas:
        persona["gold_profile"]["english_track"] = "no"
    assert any("at least 2 English-track" in error for error in validate_personas(personas))
