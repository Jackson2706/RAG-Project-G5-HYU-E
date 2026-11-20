"""HYU scheduling, resume and deadlines on synthetic cases, without Ollama or databases."""

import asyncio
import json
import sys
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from evaluation import runner


@pytest.fixture
def setup_run(tmp_path, monkeypatch):
    args = Namespace(suite="hyu", split="dev", dry_run=False, smoke=False, resume=False, force=False,
                     confirm_frozen=False, reason=None, case_major=True, stop_at=None)
    run = runner.Run.__new__(runner.Run)
    run.args, run.run_id, run.split = args, "fixture", "dev"
    run.dir, run.raw = tmp_path, tmp_path / "raw"
    run.status_file, run.status = tmp_path / "status.json", {}
    run.offline, run.online, run.generation = {}, {}, {}
    run.hyu = {"index": "fixture", "generation": {}}
    run.settings = SimpleNamespace(hyu_index_id="fixture")
    run.ollama = SimpleNamespace(list_models=AsyncMock(return_value=[]))
    run.db = SimpleNamespace(index_id="fixture", chunks=SimpleNamespace(find=Mock(return_value=[])),
                             check=lambda: {"mongodb": {"ok": True}, "qdrant": {"ok": True}})
    run.db.for_index = lambda index: run.db
    tasks = [runner.Task("hyu", preset, "dev", "-", preset) for preset in ("A", "B")]
    cases = [{"case_id": cid, "snapshot_id": "synthetic"} for cid in ("case1", "case2")]
    calls = []

    async def fake_case(case, config, services, documents, lookup):
        calls.append((case["case_id"], config["preset"]))
        return {"qid": case["case_id"], "status": "completed", "behavior": "answer", "error": None}

    monkeypatch.setattr(runner, "Run", lambda args: run)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(runner, "build_plan", lambda *args: tasks)
    monkeypatch.setattr(runner, "check_run", Mock())
    monkeypatch.setattr(runner, "check_task", lambda *args: ("READY", ""))
    monkeypatch.setattr(runner, "write_manifest", AsyncMock())
    reports = Mock()
    monkeypatch.setattr(runner, "write_reports", reports)
    monkeypatch.setattr(runner, "preset_config", lambda preset, *args: {"preset": preset})
    monkeypatch.setattr(runner.hyu_suite, "load_cases", lambda split: cases)
    monkeypatch.setattr(runner.hyu_suite, "snapshot_doc_ids", lambda snapshot: {})
    monkeypatch.setattr(runner.hyu_suite, "snapshot_dir", lambda snapshot: tmp_path / "snapshot")
    monkeypatch.setattr(runner, "run_hyu_case", fake_case)
    return SimpleNamespace(run=run, args=args, tasks=tasks, calls=calls, reports=reports)


@pytest.mark.parametrize("case_major, expected", [
    (True, [("case1", "A"), ("case1", "B"), ("case2", "A"), ("case2", "B")]),
    (False, [("case1", "A"), ("case2", "A"), ("case1", "B"), ("case2", "B")]),
])
def test_run_order_and_completed_status(setup_run, case_major, expected):
    s = setup_run
    s.args.case_major = case_major
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == expected
    assert all(info["status"] == "COMPLETED" and info["queries"] == 2 for info in s.run.status.values())
    s.reports.assert_called_once_with(s.run.dir)


def test_resume_skips_completed_pairs_and_retries_failed_records(setup_run):
    s = setup_run
    s.args.resume = True
    for task in s.tasks:
        runner.append(s.run.raw_file(task), {"qid": "case1", "status": "completed"})
        runner.append(s.run.raw_file(task), {"qid": "case2", "status": "completed" if task.preset == "A" else "failed"})
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == [("case2", "B")]
    assert [len(runner.load_jsonl(s.run.raw_file(t))) for t in s.tasks] == [2, 3]
    assert all(info["status"] == "COMPLETED" and info["queries"] == 2 for info in s.run.status.values())


@pytest.mark.parametrize("case_major", [True, False])
def test_past_deadline_runs_nothing_and_writes_stopped_status(setup_run, case_major, capsys):
    s = setup_run
    s.args.case_major = case_major
    s.args.stop_at = datetime(2000, 1, 1, tzinfo=UTC)
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == []
    status = json.loads(s.run.status_file.read_text())
    assert len(status) == 2
    for info in status.values():
        assert info["status"] == "STOPPED" and info["queries"] == 0
        assert datetime.fromisoformat(info["stopped_at"]) >= s.args.stop_at
    assert "STOP_AT reached after 0 complete cases" in capsys.readouterr().out
    s.reports.assert_called_once_with(s.run.dir)


def test_deadline_crossed_mid_case_finishes_all_presets(setup_run, monkeypatch, capsys):
    s = setup_run
    deadline = datetime(2040, 1, 1, tzinfo=UTC)
    now = [deadline - timedelta(seconds=1)]
    monkeypatch.setattr(runner, "datetime", SimpleNamespace(now=lambda tz: now[0]))
    s.args.stop_at = deadline
    fake_case = runner.run_hyu_case

    async def cross_deadline(*args):
        record = await fake_case(*args)
        now[0] = deadline  # A finishes at the deadline; B must still finish this same case.
        return record

    monkeypatch.setattr(runner, "run_hyu_case", cross_deadline)
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == [("case1", "A"), ("case1", "B")]
    assert [runner.read_done(s.run.raw_file(t)) for t in s.tasks] == [{"case1"}, {"case1"}]
    assert all(info["status"] == "STOPPED" and info["queries"] == 1 and info["stopped_at"] == deadline.isoformat()
               for info in s.run.status.values())
    assert "STOP_AT reached after 1 complete cases" in capsys.readouterr().out
    s.reports.assert_called_once_with(s.run.dir)


def test_resume_of_all_done_cases_remains_completed_after_deadline(setup_run, capsys):
    s = setup_run
    s.args.resume = True
    s.args.stop_at = datetime(2000, 1, 1, tzinfo=UTC)
    for task in s.tasks:
        for cid in ("case1", "case2"):
            runner.append(s.run.raw_file(task), {"qid": cid, "status": "completed"})
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == []
    assert all(info["status"] == "COMPLETED" and "stopped_at" not in info for info in s.run.status.values())
    assert "STOP_AT reached" not in capsys.readouterr().out


def test_case_major_respects_each_tasks_query_limit(setup_run):
    s = setup_run
    s.tasks[0].query_limit = 1
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert s.calls == [("case1", "A"), ("case1", "B"), ("case2", "B")]
    assert [s.run.status[t.key]["queries"] for t in s.tasks] == [1, 2]
    assert all(info["status"] == "COMPLETED" for info in s.run.status.values())


@pytest.mark.parametrize("force", [False, True])
def test_existing_results_are_preserved_unless_forced(setup_run, force):
    s = setup_run
    s.args.force = force
    for task in s.tasks:
        runner.append(s.run.raw_file(task), {"qid": "old", "status": "completed"})
    assert asyncio.run(runner.main_async(s.args)) == 0
    assert len(s.calls) == (4 if force else 0)
    assert [runner.read_done(s.run.raw_file(t)) for t in s.tasks] == ([{"case1", "case2"}] * 2 if force else [{"old"}] * 2)


@pytest.mark.parametrize("error, status", [(LookupError("missing model"), "BLOCKED"), (RuntimeError("bad trace"), "FAILED")])
def test_one_tasks_exception_does_not_block_other_presets(setup_run, monkeypatch, error, status):
    s = setup_run
    fake_case = runner.run_hyu_case

    async def fail_a(case, config, *args):
        if config["preset"] == "A":
            raise error
        return await fake_case(case, config, *args)

    monkeypatch.setattr(runner, "run_hyu_case", fail_a)
    assert asyncio.run(runner.main_async(s.args)) == 1
    assert s.calls == [("case1", "B"), ("case2", "B")]
    assert s.run.status[s.tasks[0].key]["status"] == status
    assert s.run.status[s.tasks[1].key]["status"] == "COMPLETED"
    s.reports.assert_called_once_with(s.run.dir)


def test_shared_case_helper_preserves_history_oracle_and_record(monkeypatch):
    case = {"case_id": "C", "question": "Q?", "session_history": [{"role": "user", "text": "I'm at ERICA."}],
            "stated_profile": {"campus": "erica"}, "gold_evidence": [{"doc_id": "D", "char_start": 0, "char_end": 4}]}
    documents = {"D": {"text": "Gold evidence."}}
    config = {"query_understanding": {"method": "profile_understanding"}}
    trace = {"status": "completed", "error": None, "stages": [], "action": "ANSWER", "outcome": "answered", "answer": "Yes."}
    fake_rag = AsyncMock(return_value=trace)
    monkeypatch.setattr(runner, "run_rag", fake_rag)
    services, lookup = object(), lambda ids: {}
    record = asyncio.run(runner.run_hyu_case(case, config, services, documents, lookup))
    assert record == runner.hyu_suite.trace_record(case, trace, lookup)
    fake_rag.assert_awaited_once_with("Q?", config, services, save_trace=False, history=["I'm at ERICA."],
                                     oracle=runner.hyu_suite.oracle_for(case, documents))


@pytest.mark.parametrize("flags", [
    ["--suite", "hyu", "--stop-at", "2026-11-21T12:00:00"],
    ["--suite", "hyu", "--stop-at", "not-a-time"],
    ["--case-major"],
    ["--suite", "offline", "--stop-at", "2026-11-21T12:00:00+09:00"],
])
def test_invalid_flags_are_rejected_before_execution(monkeypatch, flags):
    monkeypatch.setattr(sys, "argv", ["runner", *flags])
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("flags, case_major, stop_at", [
    ([], False, None),
    (["--case-major", "--stop-at", "2026-11-21T12:00:00+09:00"], True, datetime.fromisoformat("2026-11-21T12:00:00+09:00")),
])
def test_cli_defaults_and_offset_deadline(monkeypatch, flags, case_major, stop_at):
    fake_main = AsyncMock(return_value=0)
    monkeypatch.setattr(runner, "main_async", fake_main)
    monkeypatch.setattr(sys, "argv", ["runner", "--suite", "hyu", *flags])
    assert runner.main() == 0
    args = fake_main.await_args.args[0]
    assert args.case_major == case_major and args.stop_at == stop_at
