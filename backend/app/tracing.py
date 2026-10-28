"""Execution tracing: what each stage received, returned, and how long it took.

Every update is sent to `emit`, which streams it to the browser (the Execution tab).
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


def to_jsonable(value: Any) -> Any:
    """Turn dataclasses (Candidate, Evidence, …) into plain dicts/lists for JSON."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)  # e.g. Path


class Tracer:
    def __init__(self, request_id: str, emit: Callable[[dict], None]) -> None:
        self.request_id = request_id
        self.emit = emit
        self.stages: list[dict] = []

    def _send(self, record: dict) -> None:
        self.emit({"type": "stage", "request_id": self.request_id, "stage": dict(record)})

    @contextmanager
    def stage(self, stage_id: str, name: str, method_id: str, method_name: str, input: Any, params: dict):
        """Record one stage that really runs:

            with tracer.stage(...) as record:
                result = ...the work...
                record["output"] = to_jsonable(result)
        """
        record = {"stage_id": stage_id, "name": name, "method_id": method_id, "method_name": method_name, "status": "running",
                  "input": to_jsonable(input), "output": None, "params": dict(params), "summary": "", "duration_ms": None, "error": None}  # fmt: skip
        self.stages.append(record)
        self._send(record)
        start = time.perf_counter()
        try:
            yield record
            record["status"] = "completed"
        except Exception as exc:
            record["status"], record["error"] = "failed", f"{exc.__class__.__name__}: {exc}"
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
            self._send(record)

    def skip(self, stage_id: str, name: str, reason: str) -> None:
        """Record a stage that did NOT run (switched off, not implemented, or not needed)."""
        record = {"stage_id": stage_id, "name": name, "method_id": None, "method_name": None, "status": "skipped",
                  "input": None, "output": None, "params": {}, "summary": reason, "duration_ms": None, "error": None}  # fmt: skip
        self.stages.append(record)
        self._send(record)
