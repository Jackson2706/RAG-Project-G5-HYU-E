"""Prepared-corpus eligibility, including identical Qdrant and postfilter semantics."""
import pytest
from qdrant_client import models

from app.rag.blocks.metadata_filtering.metadata_postfiltering.candidate_postfilter import CandidateMetadataPostfilter
from app.rag.blocks.metadata_filtering.metadata_prefiltering.qdrant_prefilter import QdrantMetadataPrefilter
from app.rag.blocks.query_processing.query_understanding.stated_criteria import StatedCriteria
from app.rag.blocks.retrieval.dense_retrieval.qdrant_cosine import to_qdrant_filter
from app.rag.registry import validate_config
from app.rag.schemas import Candidate, FilterCriteria, metadata_values


def test_prepared_fields_use_and_between_fields_or_within_fields():
    predicate = FilterCriteria(campus=" SEOUL ", academic_level="undergraduate", student_category="international",
                               department="architecture, computer-science", topic="scholarships, tuition",
                               academic_year="2027", term="spring").to_filter(include_unknown=False)
    valid = dict(campus="SEOUL", academic_level="[undergraduate, graduate]", student_category="international",
                 department="architecture", topic="scholarships", academic_year="2027", term="spring")
    assert predicate.matches(valid)
    assert predicate.matches({**valid, "department": "computer-science", "topic": "tuition"})
    for field, value in [("campus", "ERICA"), ("academic_level", "graduate"), ("term", "fall"), ("academic_year", "2026")]:
        assert not predicate.matches({**valid, field: value})
    unknown = {k: v for k, v in valid.items() if k != "student_category"}
    assert not predicate.matches(unknown)  # English content alone is not international status.


def test_shared_scope_is_explicit_and_switchable():
    criteria = FilterCriteria(campus="SEOUL", department="architecture", college="engineering")
    predicate = criteria.to_filter(include_unknown=False)
    assert predicate.matches(dict(campus="ALL", department="ALL", college="ALL"))
    assert not predicate.matches(dict(campus="SEOUL", college="engineering"))
    assert not predicate.matches(dict(campus="SEOUL", department="ALL", college="music"))
    assert not criteria.to_filter(False, include_shared_scope=False).matches(dict(campus="ALL", department="ALL", college="ALL"))
    assert FilterCriteria(topic=" , ").to_filter() is None


def test_degree_discussed_is_distinct_from_degree_offered():
    row = dict(degree_level="[masters, phd, combined]", available_degree_levels="[masters, phd]")
    assert FilterCriteria(degree_level="combined").to_filter(False).matches(row)
    assert not FilterCriteria(available_degree_levels="combined").to_filter(False).matches(row)
    assert not FilterCriteria(academic_year="2027").to_filter(False).matches(dict(retrieved_on="2026-11-12"))


@pytest.mark.anyio
async def test_registry_controls_build_all_criteria_without_guessing(services):
    supplied = {"campus": "SEOUL", "academic_level": "undergraduate", "student_category": "international",
                "department": "architecture", "college": "engineering", "topic": "scholarships",
                "term": "spring", "academic_year": "2027", "degree_level": "masters",
                "available_degree_levels": "masters", "admission_route": "international_admissions", "effective_date": "2027-03-01"}
    config = validate_config({"query_understanding": {"method": "stated_criteria", "params": supplied},
                              "metadata_prefiltering": {"method": "qdrant_prefilter"},
                              "metadata_postfiltering": {"method": "candidate_postfilter"}})
    analysis = await StatedCriteria(config['query_understanding']['params'], services).analyze("ERICA graduate tuition")
    assert analysis.criteria.conditions() == supplied  # The question must not override explicit controls.


@pytest.mark.anyio
@pytest.mark.parametrize('include_unknown', [False, True])
@pytest.mark.parametrize('include_shared_scope', [False, True])
async def test_qdrant_prefilter_and_postfilter_agree_for_real_metadata_shapes(db, services, include_unknown, include_shared_scope):
    # A college-qualified rule with missing department must not become ALL in strict mode.
    metadata = [
        dict(campus='SEOUL', academic_level='undergraduate', department='architecture', topic='scholarships'),
        dict(campus='ALL', academic_level='[undergraduate, graduate]', department='ALL', topic='scholarships'),
        dict(campus='ERICA', academic_level='undergraduate', department='architecture', topic='scholarships'),
        dict(campus='SEOUL', academic_level='graduate', department='architecture', topic='scholarships'),
        dict(campus='SEOUL', academic_level='undergraduate', college='engineering', topic='scholarships'),
        dict(campus='SEOUL', academic_level='undergraduate', department='architecture', topic='tuition'),
    ]
    db.qdrant.create_collection(db.collection, vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
    db.qdrant.upsert(db.collection, points=[models.PointStruct(id=i, vector=[1., 0.], payload={k:metadata_values(v) for k,v in m.items()}) for i,m in enumerate(metadata)])
    db.documents.insert_many([dict(doc_id=str(i), metadata=m) for i,m in enumerate(metadata)])
    criteria = FilterCriteria(campus='SEOUL', academic_level='undergraduate', department='architecture', topic='scholarships')
    params = dict(include_unknown=include_unknown, include_campus_wide=True, include_shared_scope=include_shared_scope)
    predicate = await QdrantMetadataPrefilter(params, services).build_filter(criteria)
    points, _ = db.qdrant.scroll(db.collection, scroll_filter=to_qdrant_filter(predicate), limit=100)
    pre_ids = {str(p.id) for p in points}
    expected = {'0'} | ({'1'} if include_shared_scope else set()) | ({'4'} if include_unknown else set())
    assert pre_ids == expected
    candidates = [Candidate(rank=i+1, chunk_id=str(i), doc_id=str(i), score=1.) for i in range(len(metadata))]
    post = await CandidateMetadataPostfilter(params, services).filter_candidates(candidates, criteria)
    assert {c.doc_id for c in post.kept} == pre_ids
    assert [c.rank for c in post.kept] == list(range(1,len(expected)+1))
    assert len(post.removed) == len(metadata)-len(expected)
    assert all(r.reason for r in post.removed)


@pytest.mark.anyio
@pytest.mark.parametrize("include_unknown", [False, True])
async def test_offered_degree_requires_positive_evidence_in_both_backends(db, services, include_unknown):
    metadata = [dict(available_degree_levels='[masters, combined]'), dict(available_degree_levels='[]'), {}, dict(available_degree_levels='masters')]
    db.qdrant.create_collection(db.collection, vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
    db.qdrant.upsert(db.collection, points=[models.PointStruct(id=i, vector=[1., 0.], payload={k:metadata_values(v) for k,v in m.items()}) for i,m in enumerate(metadata)])
    db.documents.insert_many([dict(doc_id=str(i), metadata=m) for i,m in enumerate(metadata)])
    criteria = FilterCriteria(available_degree_levels='combined')
    predicate = criteria.to_filter(include_unknown=include_unknown)
    points, _ = db.qdrant.scroll(db.collection, scroll_filter=to_qdrant_filter(predicate), limit=100)
    assert {p.id for p in points} == {0}
    params = dict(include_unknown=include_unknown, include_campus_wide=True, include_shared_scope=True)
    candidates = [Candidate(rank=i+1, chunk_id=str(i), doc_id=str(i), score=1.) for i in range(len(metadata))]
    result = await CandidateMetadataPostfilter(params, services).filter_candidates(candidates, criteria)
    assert [c.doc_id for c in result.kept] == ['0']
