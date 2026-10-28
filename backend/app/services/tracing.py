"""Helpers that keep trace payloads JSON-safe and bounded."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def vector_preview(vector: list[float], head: int = 8) -> dict[str, Any]:
    """Summary shown instead of a full embedding."""
    return {"dimension": len(vector), "norm": round(math.sqrt(sum(v * v for v in vector)), 6),
            "preview": [round(v, 5) for v in vector[:head]]}  # fmt: skip


def bound(value: Any, max_string: int = 4000, max_items: int = 50) -> Any:
    """Recursively convert to JSON-safe data, truncating long strings and lists with explicit markers."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): bound(v, max_string, max_items) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [bound(v, max_string, max_items) for v in value[:max_items]]
        if len(value) > max_items:
            items.append({"_truncated": f"{len(value) - max_items} more items"})
        return items
    if isinstance(value, str) and len(value) > max_string:
        return value[:max_string] + f"… [truncated {len(value) - max_string} chars]"
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
