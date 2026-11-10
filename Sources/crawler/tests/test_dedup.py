from crawler.dedup import deduplicate


def record(doc_id, text, campus="seoul", date="2025-01-01"):
    return {
        "doc_id": doc_id,
        "source_uri": f"https://example.test/{doc_id}",
        "site": campus,
        "campus": campus,
        "post_date": date,
        "effective_date": None,
        "text": text,
        "warnings": [],
        "aliases": [],
        "version_family_id": None,
        "superseded_by": None,
    }


def test_exact_duplicate_becomes_alias_and_keeps_both_campuses():
    records = deduplicate([
        record("b", "Same   policy text", "erica", "2026-01-01"),
        record("a", "Same policy text", "seoul", "2025-01-01"),
    ])
    assert len(records) == 1
    assert records[0]["doc_id"] == "a"
    assert records[0]["aliases"] == [{
        "doc_id": "b",
        "source_uri": "https://example.test/b",
        "site": "erica",
        "campus": "erica",
    }]


def test_near_duplicate_versions_form_family_and_supersede_older():
    common = " ".join(f"policyword{index}" for index in range(400))
    older = record("old", f"{common} Applies in 2025. The fee is 76,390 won.", date="2025-01-01")
    newer = record("new", f"{common} Applies in 2026. The fee is 79,320 won.", date="2026-01-01")
    records = {item["doc_id"]: item for item in deduplicate([older, newer])}
    assert records["old"]["version_family_id"] == records["new"]["version_family_id"]
    assert records["old"]["superseded_by"] == "new"
    assert records["new"]["superseded_by"] is None


def test_unrelated_texts_do_not_form_family():
    records = deduplicate([
        record("a", "Visa extension forms and immigration office hours."),
        record("b", "Scholarship grades and tuition waiver details."),
    ])
    assert all(item["version_family_id"] is None for item in records)

