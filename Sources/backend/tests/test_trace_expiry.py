"""Stored trace retention and local deletion, using mongomock without Docker."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.database import Database
from app.main import create_app
from app.rag.pipeline import run_ingestion
from app.rag.presets import PRESETS_BY_ID
from app.rag.registry import validate_config
from app.rag.schemas import Services


@pytest.fixture
def trace_db(db, settings, monkeypatch):
    monkeypatch.setattr("app.database.get_settings", lambda: settings)
    return Database(mongomock.MongoClient(tz_aware=True)["test_traces"], db.qdrant, "test_chunks")


@pytest.fixture
def trace_stores(trace_db):
    tagged = trace_db.for_index("hyu_tagged")
    tagged.save_manifest({"applicability": {"vocabulary_version": "v1"}})
    smoke = trace_db.for_index("hyu_smoke")
    smoke.save_manifest({"corpus": {"smoke_slice": True}})
    return [trace_db, tagged, smoke]


def test_trace_ttl_setting_defaults_and_environment(monkeypatch):
    monkeypatch.delenv("TRACE_TTL_DAYS", raising=False)
    assert Settings(_env_file=None).trace_ttl_days == 30
    monkeypatch.setenv("TRACE_TTL_DAYS", "7")
    assert Settings(_env_file=None).trace_ttl_days == 7
    monkeypatch.setenv("TRACE_TTL_DAYS", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_ttl_index_uses_configured_days_and_is_idempotent(trace_db, settings, monkeypatch):
    settings.trace_ttl_days = 7
    command = Mock()
    monkeypatch.setattr(trace_db.mongo, "command", command)
    trace_db.create_indexes()
    trace_db.create_indexes()
    assert trace_db.traces.index_information()["expires_from_1"]["expireAfterSeconds"] == 7 * 86400
    command.assert_not_called()


@pytest.mark.parametrize("previous_ttl", [86400, None])
def test_existing_expiry_is_updated_with_collmod(trace_db, previous_ttl, monkeypatch):
    options = {} if previous_ttl is None else {"expireAfterSeconds": previous_ttl}
    trace_db.traces.create_index("expires_from", name="existing_expiry", **options)
    trace_db.traces.insert_one({"request_id": "keep", "created_at": datetime.now(UTC)})
    command = Mock(return_value={"ok": 1})
    monkeypatch.setattr(trace_db.mongo, "command", command)
    trace_db.create_indexes()
    command.assert_called_once_with({"collMod": "traces", "index": {
        "name": "existing_expiry", "expireAfterSeconds": 30 * 86400}})
    assert trace_db.traces.count_documents({}) == 1
    assert "existing_expiry" in trace_db.traces.index_information()


def test_backfill_parses_iso_and_bson_dates_and_counts_invalid(trace_db, caplog):
    created = (datetime.now(UTC) - timedelta(hours=1)).replace(microsecond=0)
    rows = [
        {"request_id": "iso", "created_at": created.isoformat()},
        {"request_id": "z", "created_at": created.isoformat().replace("+00:00", "Z")},
        {"request_id": "offset", "created_at": created.astimezone(timezone(timedelta(hours=9))).isoformat()},
        {"request_id": "naive", "created_at": created.replace(tzinfo=None).isoformat()},
        {"request_id": "date", "created_at": created},
        {"request_id": "existing", "created_at": "invalid", "expires_from": created},
        {"request_id": "invalid", "created_at": "invalid"},
        {"request_id": "number", "created_at": 123},
        {"request_id": "null", "created_at": None},
        {"request_id": "missing"},
    ]
    trace_db.traces.insert_many([dict(row) for row in rows])
    trace_db.create_indexes()
    stored = {row["request_id"]: row for row in trace_db.traces.find({}, {"_id": 0})}
    for row in rows[:6]:
        assert stored[row["request_id"]] == {**row, "expires_from": created}
    for row in rows[6:]:
        assert stored[row["request_id"]] == row
    assert "4 traces have unparseable created_at; left untouched" in caplog.text


def test_save_trace_stores_utc_bson_date_without_changing_input(trace_db):
    trace_db.create_indexes()
    trace = {"request_id": "new", "created_at": datetime.now(UTC).isoformat()}
    before = datetime.now(UTC).replace(microsecond=0)
    trace_db.save_trace(trace)
    stored = trace_db.get_trace("new")
    assert stored["created_at"] == trace["created_at"]
    assert isinstance(stored["expires_from"], datetime)
    assert stored["expires_from"].utcoffset() == timedelta(0)
    assert before <= stored["expires_from"] <= datetime.now(UTC)
    assert "expires_from" not in trace


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "testclient"])
def test_local_delete_returns_count_and_keeps_other_collections(trace_db, trace_stores, ollama, host):
    for store in trace_stores:
        store.save_trace({"request_id": "one", "created_at": datetime.now(UTC).isoformat()})
        store.save_trace({"request_id": "two", "created_at": datetime.now(UTC).isoformat()})
        store.documents.insert_one({"doc_id": "keep"})
        store.chunks.insert_one({"chunk_id": "keep", "doc_id": "keep"})
    unrelated = trace_db.mongo.client["unrelated"]["traces"]
    unrelated.insert_one({"request_id": "keep"})
    with TestClient(create_app(db=trace_db, ollama=ollama), client=(host, 50000)) as api:
        assert api.get("/api/traces").json() == {"count": 6, "stores": {
            "default": 2, "hyu_smoke": 2, "hyu_tagged": 2}}
        response = api.delete("/api/traces")
        assert response.status_code == 200 and response.json() == {"deleted": 6}
        assert api.get("/api/traces").json() == {"count": 0, "stores": {
            "default": 0, "hyu_smoke": 0, "hyu_tagged": 0}}
        assert api.get("/api/traces/one").status_code == 404
        assert api.delete("/api/traces").json() == {"deleted": 0}
    for store in trace_stores:
        assert store.traces.count_documents({}) == 0
        assert store.documents.count_documents({}) == store.chunks.count_documents({}) == 1
        assert "expires_from_1" in store.traces.index_information()
    assert trace_stores[1].get_manifest()["applicability"] == {"vocabulary_version": "v1"}
    assert trace_stores[2].get_manifest()["corpus"] == {"smoke_slice": True}
    assert unrelated.count_documents({}) == 1


@pytest.mark.parametrize("host", ["192.0.2.1", "localhost"])
def test_remote_client_cannot_count_or_delete_traces(trace_db, trace_stores, ollama, host):
    for store in trace_stores:
        store.save_trace({"request_id": "keep", "created_at": datetime.now(UTC).isoformat()})
    with TestClient(create_app(db=trace_db, ollama=ollama), client=(host, 50000)) as api:
        for method in (api.get, api.delete):
            response = method("/api/traces", headers={"X-Forwarded-For": "127.0.0.1"})
            assert response.status_code == 403
    assert all(store.traces.count_documents({}) == 1 for store in trace_stores)


def test_startup_backfills_and_expires_traces_in_every_store(trace_db, trace_stores, settings, ollama):
    settings.trace_ttl_days = 7
    recent = (datetime.now(UTC) - timedelta(hours=1)).replace(microsecond=0)
    expired = recent - timedelta(days=8)
    for store in trace_stores:
        store.traces.insert_many([
            {"request_id": "iso", "created_at": recent.isoformat()},
            {"request_id": "date", "created_at": recent},
            {"request_id": "old", "created_at": expired.isoformat()},
        ])
        store.save_trace({"request_id": "saved", "created_at": recent.isoformat()})
        store.traces.update_one({"request_id": "saved"}, {"$set": {"expires_from": expired}})
    with TestClient(create_app(db=trace_db, ollama=ollama)):
        for store in trace_stores:
            assert store.traces.index_information()["expires_from_1"]["expireAfterSeconds"] == 7 * 86400
            assert store.count_traces() == 2
            assert store.get_trace("old") is None and store.get_trace("saved") is None
            assert store.get_trace("iso")["expires_from"] == store.get_trace("date")["expires_from"] == recent


def test_index_chat_is_counted_and_deleted_without_restart(trace_db, corpus, settings, ollama, monkeypatch):
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    with TestClient(create_app(db=trace_db, ollama=ollama)) as api:
        indexed = trace_db.for_index("hyu_tagged")
        preset = PRESETS_BY_ID["B0_BASIC_DENSE_RAG"]
        run_ingestion(corpus, validate_config(preset["stages"]), Services(db=indexed, ollama=ollama, settings=settings))
        indexed.manifests.update_one({"_id": "manifest"}, {"$set": {"applicability": {"vocabulary_version": "v1"}}})
        listed = {p["id"]: p for p in api.get("/api/pipeline/presets").json()["presets"]}
        assert listed[preset["id"]]["enabled"]
        response = api.post("/api/chat", json={"question": "How do I register for courses?",
                            "index_id": indexed.index_id, "stages": preset["stages"]})
        assert response.status_code == 200
        trace = response.json()
        assert trace["status"] == "completed", trace["error"]
        assert indexed.get_trace(trace["request_id"]) is not None
        assert trace_db.count_traces() == 0
        assert api.get("/api/traces").json() == {"count": 1, "stores": {"default": 0, "hyu_tagged": 1}}
        assert api.delete("/api/traces").json() == {"deleted": 1}
        assert indexed.get_trace(trace["request_id"]) is None
